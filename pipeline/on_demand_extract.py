#!/usr/bin/env python3
"""On-demand keyframe extraction based on search queries."""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import tempfile
import os
from sentence_transformers import SentenceTransformer
from PIL import Image
import io
from transformers import pipeline

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.database import get_db_session
from pipeline.models import Video, Segment
from minio import Minio

# Configure logging
logger = logging.getLogger(__name__)


class OnDemandExtractor:
    """Extract keyframes from video based on search queries."""
    
    def __init__(self, model_name="clip-ViT-B-32"):
        """Initialize the extractor with CLIP model."""
        self.text_encoder = SentenceTransformer(model_name)
        
        # Disable caption generator for performance
        self.caption_generator = None
        logger.info("📝 Caption generation disabled - using fallback captions")
        
        self.minio_client = Minio(
            "localhost:9000",
            access_key="scenelens",
            secret_key="scenelens_dev123",
            secure=False
        )
        self.bucket_name = "scenelens"
    
    def extract_query_specific_frames(self, query: str, video_filename: str, 
                                    top_k: int = 10, frame_interval: float = 0.25) -> List[Dict]:
        """
        Extract frames from video that match the search query.
        
        Args:
            query: Search query text
            video_filename: Name of video file in MinIO
            top_k: Number of top matching frames to return
            frame_interval: Initial sampling interval (will be refined based on content)
        
        Returns:
            List of matching frame information
        """
        logger.info(f"🔍 Extracting frames for query: '{query}' from video: {video_filename}")
        
        # Download video from MinIO to temp location
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            try:
                self.minio_client.fget_object(self.bucket_name, f"videos/{video_filename}", temp_video.name)
                video_path = temp_video.name
            except Exception as e:
                logger.error(f"❌ Failed to download video from MinIO: {e}")
                return []
        
        try:
            # Extract frames at high frequency for initial sampling
            all_frames = self._extract_frames_at_interval(video_path, frame_interval)
            logger.info(f"📹 Extracted {len(all_frames)} frames for analysis")
            
            # Encode query
            query_embedding = self.text_encoder.encode(query, convert_to_numpy=True)
            
            # Calculate similarity for each frame
            similarities = []
            for frame_info in all_frames:
                # Encode frame
                frame_embedding = self.text_encoder.encode(frame_info['pil_image'], convert_to_numpy=True)
                
                # Calculate cosine similarity
                similarity = np.dot(query_embedding, frame_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(frame_embedding)
                )
                
                similarities.append({
                    'frame_info': frame_info,
                    'similarity': similarity
                })
            
            # Sort by similarity
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Smart selection: Take top frames but ensure temporal diversity
            selected_frames = self._select_temporally_diverse_frames(similarities, top_k)
            
            logger.info(f"✅ Selected {len(selected_frames)} most relevant frames")
            
            # Convert to result format
            results = []
            for item in selected_frames:
                frame_info = item['frame_info']
                
                # Save frame to MinIO for display
                frame_path = self._save_frame_to_minio(frame_info, video_filename)
                
                # Generate caption for the frame
                caption = self._generate_caption(frame_info['pil_image'])
                
                results.append({
                    'timestamp_seconds': frame_info['timestamp'],
                    'frame_number': frame_info['frame_number'],
                    'similarity_score': float(item['similarity']),
                    'pil_image': frame_info['pil_image'],
                    'keyframe_path': frame_path,  # Add the saved path
                    'caption': caption  # Add the generated caption
                })
            
            return results
            
        finally:
            # Clean up temp file
            os.unlink(video_path)
    
    def _extract_frames_at_interval(self, video_path: str, interval_seconds: float) -> List[Dict]:
        """Extract frames from video at specified interval."""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Calculate frame interval
        frame_interval = max(1, int(fps * interval_seconds))
        
        frames = []
        frame_number = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Extract frame at interval
            if frame_number % frame_interval == 0:
                timestamp = frame_number / fps
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Convert to PIL Image for CLIP
                pil_image = Image.fromarray(frame_rgb)
                
                frames.append({
                    'frame_number': frame_number,
                    'timestamp': timestamp,
                    'pil_image': pil_image,
                    'cv2_frame': frame
                })
            
            frame_number += 1
        
        cap.release()
        return frames
    
    def _select_temporally_diverse_frames(self, similarities: List[Dict], top_k: int) -> List[Dict]:
        """
        Select frames that are both relevant and temporally diverse.
        This ensures we get frames from different parts of the video.
        """
        if len(similarities) <= top_k:
            return similarities[:top_k]
        
        selected = []
        timestamps = []
        
        for item in similarities:
            timestamp = item['frame_info']['timestamp']
            
            # Check if this frame is temporally distant from already selected frames
            is_diverse = True
            for selected_time in timestamps:
                if abs(timestamp - selected_time) < 0.5:  # At least 0.5s apart
                    is_diverse = False
                    break
            
            if is_diverse:
                selected.append(item)
                timestamps.append(timestamp)
                
                if len(selected) >= top_k:
                    break
        
        # If we don't have enough diverse frames, add more from top results
        if len(selected) < top_k:
            for item in similarities:
                if item not in selected:
                    selected.append(item)
                    if len(selected) >= top_k:
                        break
        
        return selected
    
    def save_extracted_frames(self, frames: List[Dict], video_filename: str) -> List[str]:
        """Save extracted frames to MinIO and return paths."""
        video_stem = Path(video_filename).stem
        saved_paths = []
        
        for i, frame_info in enumerate(frames):
            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            frame_info['pil_image'].save(img_byte_arr, format='JPEG', quality=85)
            img_byte_arr.seek(0)
            
            # Generate filename
            timestamp = frame_info['timestamp_seconds']
            frame_filename = f"frame_{frame_info['frame_number']:06d}_t{timestamp:.2f}s_query.jpg"
            minio_path = f"frames/{video_stem}/query_extracted/{frame_filename}"
            
            # Upload to MinIO
            try:
                self.minio_client.put_object(
                    self.bucket_name,
                    minio_path,
                    img_byte_arr,
                    length=len(img_byte_arr.getvalue()),
                    content_type="image/jpeg"
                )
                saved_paths.append(minio_path)
                logger.info(f"💾 Saved frame to MinIO: {minio_path}")
            except Exception as e:
                logger.error(f"❌ Failed to save frame: {e}")
        
        return saved_paths

    def _save_frame_to_minio(self, frame_info: Dict, video_filename: str) -> str:
        """Save a single frame to MinIO and return the path."""
        try:
            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            frame_info['pil_image'].save(img_byte_arr, format='JPEG', quality=85)
            img_byte_arr.seek(0)
            
            # Generate filename
            timestamp = frame_info['timestamp']
            frame_number = frame_info['frame_number']
            video_stem = Path(video_filename).stem
            
            frame_filename = f"frame_{frame_number:06d}_t{timestamp:.2f}s_query.jpg"
            minio_path = f"frames/{video_stem}/query_extracted/{frame_filename}"
            
            # Upload to MinIO
            self.minio_client.put_object(
                self.bucket_name,
                minio_path,
                img_byte_arr,
                length=len(img_byte_arr.getvalue()),
                content_type="image/jpeg"
            )
            
            logger.info(f"💾 Saved prompt-driven frame to MinIO: {minio_path}")
            return minio_path
            
        except Exception as e:
            logger.error(f"❌ Failed to save frame to MinIO: {e}")
            # Return a fallback path
            return f"frames/{Path(video_filename).stem}/query_extracted/fallback.jpg"

    def _generate_caption(self, pil_image: Image.Image) -> str:
        """Generate a caption for the given image."""
        if self.caption_generator is None:
            return "A video frame"
        
        try:
            # Generate caption
            result = self.caption_generator(pil_image)
            caption = result[0]['generated_text']
            
            # Clean up the caption
            caption = caption.strip()
            if caption.endswith('.'):
                caption = caption[:-1]
            
            return caption
        except Exception as e:
            logger.warning(f"⚠️ Caption generation failed: {e}")
            return "A video frame"


def get_on_demand_extractor():
    """Get or create on-demand extractor instance."""
    return OnDemandExtractor()
