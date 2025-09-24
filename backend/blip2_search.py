#!/usr/bin/env python3
"""BLIP-2 based video search engine for intelligent frame analysis."""

import os
import sys
import time
import logging
from typing import List, Dict, Optional
from PIL import Image
import cv2
import torch
import requests
from io import BytesIO
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minio_storage import MinIOStorage
from minio import Minio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BLIP2SearchEngine:
    """BLIP-2 based search engine for intelligent video frame analysis."""
    
    def __init__(self):
        self.blip2_model = None
        self.blip2_processor = None
        self.minio_client = None
        self.minio_storage = None
        self.bucket_name = "scenelens"
        self._initialize_models()
        self._initialize_minio()
    
    def _initialize_models(self):
        """Initialize BLIP-2 model for VLM-based search."""
        try:
            logger.info("🔄 Loading BLIP-2 model for intelligent search...")
            
            from transformers import InstructBlipProcessor, InstructBlipForConditionalGeneration
            
            # Use InstructBLIP which is more stable and designed for Q&A
            model_name = "Salesforce/instructblip-vicuna-7b"
            
            self.blip2_processor = InstructBlipProcessor.from_pretrained(model_name)
            self.blip2_model = InstructBlipForConditionalGeneration.from_pretrained(
                model_name,
                torch_dtype=torch.float16,
                device_map="auto",
                low_cpu_mem_usage=True
            )
            
            logger.info("✅ BLIP-2 model loaded successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to load BLIP-2 model: {e}")
            # Fallback to a simpler approach if BLIP-2 fails
            self.blip2_model = None
            self.blip2_processor = None
    
    def _initialize_minio(self):
        """Initialize MinIO client."""
        try:
            self.minio_client = Minio(
                "localhost:9000",
                access_key="scenelens",
                secret_key="scenelens_dev123",
                secure=False
            )
            self.minio_storage = MinIOStorage(self.minio_client, self.bucket_name)
            logger.info("✅ MinIO client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize MinIO: {e}")
    
    def _save_frame_to_minio(self, frame_info: Dict, video_filename: str) -> str:
        """Save a single frame to MinIO and return the path."""
        try:
            # Convert PIL image to bytes
            img_byte_arr = BytesIO()
            frame_info['pil_image'].save(img_byte_arr, format='JPEG', quality=85)
            img_byte_arr.seek(0)
            
            # Generate filename similar to on-demand extractor
            timestamp = frame_info['timestamp_seconds']
            frame_number = frame_info['frame_number']
            video_stem = Path(video_filename).stem
            
            frame_filename = f"frame_{frame_number:06d}_t{timestamp:.2f}s_blip2.jpg"
            minio_path = f"frames/{video_stem}/blip2_extracted/{frame_filename}"
            
            # Upload to MinIO
            self.minio_client.put_object(
                self.bucket_name,
                minio_path,
                img_byte_arr,
                length=len(img_byte_arr.getvalue()),
                content_type="image/jpeg"
            )
            
            logger.info(f"💾 Saved BLIP2 frame to MinIO: {minio_path}")
            return minio_path
            
        except Exception as e:
            logger.error(f"❌ Failed to save BLIP2 frame to MinIO: {e}")
            # Return a fallback path
            return f"frames/{Path(video_filename).stem}/blip2_extracted/fallback.jpg"
    
    def search_video_with_blip2(self, query: str, video_id: str, top_k: int = 10, 
                               frame_interval: float = 0.5) -> List[Dict]:
        """
        Search video using BLIP-2 based frame analysis.
        
        Args:
            query: Search query text
            video_id: Video ID to search
            top_k: Number of results to return
            frame_interval: Frame extraction interval in seconds
            
        Returns:
            List of search results with BLIP-2 analyzed segments
        """
        if not self.blip2_model:
            logger.error("BLIP-2 model not available")
            return []
        
        start_time = time.time()
        results = []
        
        try:
            # Store frame interval for grouping logic
            self.frame_interval = frame_interval
            
            # Get video from MinIO storage
            video = self.minio_storage.get_video_metadata(video_id)
            if not video:
                logger.error(f"Video {video_id} not found")
                return []
            
            logger.info(f"🔍 BLIP-2 search for '{query}' in video: {video['filename']}")
            
            # Extract frames from video
            frames = self._extract_frames_from_video(video, frame_interval)
            logger.info(f"📹 Extracted {len(frames)} frames for BLIP-2 analysis")
            
            # Analyze frames with BLIP-2
            relevant_segments = self._analyze_frames_with_blip2(frames, query)
            logger.info(f"🎯 BLIP-2 found {len(relevant_segments)} relevant segments")
            
            # Convert to result format
            for i, segment in enumerate(relevant_segments[:top_k]):
                # Save frame to MinIO and get the actual path
                if segment.get('pil_image'):
                    frame_info = {
                        'pil_image': segment['pil_image'],
                        'timestamp_seconds': segment['timestamp_seconds'],
                        'frame_number': segment['frame_number']
                    }
                    keyframe_path = self._save_frame_to_minio(frame_info, video['filename'])
                else:
                    keyframe_path = f"blip2/{video['filename']}/{segment['frame_number']}"
                
                result = {
                    "segment_id": f"blip2_{video['id']}_{segment['frame_number']}",
                    "video_id": video['id'],
                    "video_filename": video['filename'],
                    "video_title": video.get('title', ''),
                    "frame_number": segment['frame_number'],
                    "timestamp_seconds": segment['timestamp_seconds'],
                    "segment_start_seconds": segment['start_time'],
                    "segment_end_seconds": segment['end_time'],
                    "keyframe_path": keyframe_path,
                    "caption": segment['blip2_description'],
                    "score": segment['confidence'],
                    "is_blip2": True,
                    "is_on_demand": True
                }
                results.append(result)
            
            # Log search
            elapsed_time = (time.time() - start_time) * 1000
            self._log_search(query, len(results), elapsed_time)
            
            logger.info(f"✅ BLIP-2 search completed: {len(results)} results in {elapsed_time:.0f}ms")
            return results
            
        except Exception as e:
            logger.error(f"❌ BLIP-2 search failed: {e}")
            return []
    
    def _extract_frames_from_video(self, video: Dict, frame_interval: float) -> List[Dict]:
        """Extract frames from video for BLIP-2 analysis."""
        frames = []
        
        try:
            # Get video from MinIO
            video_path = f"videos/{video['filename']}"
            video_data = self.minio_client.get_object(self.bucket_name, video_path)
            video_bytes = video_data.read()
            
            # Save to temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_file.write(video_bytes)
                temp_video_path = temp_file.name
            
            # Open video with OpenCV
            cap = cv2.VideoCapture(temp_video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Handle invalid FPS values
            if fps <= 0 or fps is None:
                logger.warning(f"Invalid FPS ({fps}), using default 30 FPS")
                fps = 30.0
            
            frame_interval_frames = max(1, int(fps * frame_interval))
            logger.info(f"Video FPS: {fps}, Frame interval: {frame_interval_frames} frames")
            
            frame_number = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_number % frame_interval_frames == 0:
                    timestamp = frame_number / fps
                    
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)
                    
                    frames.append({
                        'frame_number': frame_number,
                        'timestamp_seconds': timestamp,
                        'pil_image': pil_image,
                        'video_filename': video['filename']
                    })
                
                frame_number += 1
            
            cap.release()
            os.unlink(temp_video_path)  # Clean up temp file
            
        except Exception as e:
            logger.error(f"Failed to extract frames: {e}")
        
        return frames
    
    def _analyze_frames_with_blip2(self, frames: List[Dict], query: str) -> List[Dict]:
        """Analyze frames using BLIP-2 to find relevant segments."""
        relevant_segments = []
        
        for frame in frames:
            try:
                # Use InstructBLIP for proper question-answering
                question = f"Does this image show {query}?"
                
                # Process image and question with InstructBLIP
                inputs = self.blip2_processor(
                    images=frame['pil_image'],
                    text=question,
                    return_tensors="pt"
                ).to(self.blip2_model.device)
                
                # Generate answer with InstructBLIP
                with torch.no_grad():
                    output = self.blip2_model.generate(
                        **inputs,
                        max_new_tokens=20,
                        do_sample=False,
                        temperature=0.0
                    )
                
                # Decode response
                blip_response = self.blip2_processor.decode(output[0], skip_special_tokens=True)
                
                # Extract just the answer part (remove the question)
                if question in blip_response:
                    blip_response = blip_response.split(question)[-1].strip()
                
                # Check if frame is relevant
                if self._is_frame_relevant(blip_response, query):
                    confidence = self._calculate_confidence(blip_response)
                    
                    # Create segment spanning the frame interval
                    frame_interval = getattr(self, 'frame_interval', 1.0)
                    segment = {
                        'frame_number': frame['frame_number'],
                        'timestamp_seconds': frame['timestamp_seconds'],
                        'start_time': frame['timestamp_seconds'],
                        'end_time': frame['timestamp_seconds'] + frame_interval,
                        'blip2_description': blip_response,
                        'confidence': confidence,
                        'pil_image': frame['pil_image'],
                        'keyframe_path': f"blip2/{frame['video_filename']}/{frame['frame_number']}"
                    }
                    relevant_segments.append(segment)
                    
                    logger.info(f"🎯 BLIP found match at {frame['timestamp_seconds']:.1f}s: {blip_response}")
                
            except Exception as e:
                logger.error(f"BLIP-2 analysis failed for frame {frame['frame_number']}: {e}")
                continue
        
        # Sort by timestamp (chronological order) for better temporal understanding
        relevant_segments.sort(key=lambda x: x['timestamp_seconds'])
        
        # Group nearby segments with adaptive gap based on frame interval
        frame_interval = self.frame_interval if hasattr(self, 'frame_interval') else 1.0
        max_gap = max(frame_interval * 1.5, 2.0)  # Allow gaps up to 1.5x frame interval
        grouped_segments = self._group_nearby_segments(relevant_segments, max_gap=max_gap)
        
        return grouped_segments
    
    def _is_frame_relevant(self, blip2_response: str, query: str) -> bool:
        """Check if BLIP-2 response indicates the frame is relevant to the query."""
        response_lower = blip2_response.lower()
        
        # Strong positive indicators (BLIP-2 typically gives clear yes/no answers)
        strong_positive = ['yes', 'yes.', 'yes,', 'yes it', 'yes it does', 'yes it shows', 'yes, it', 'yes, it does']
        strong_negative = ['no', 'no.', 'no,', 'no it', 'no it does not', 'no it does not show', 'no, it', 'no, it does not']
        
        # Check for explicit yes/no answers first
        has_strong_positive = any(pos in response_lower for pos in strong_positive)
        has_strong_negative = any(neg in response_lower for neg in strong_negative)
        
        if has_strong_positive and not has_strong_negative:
            return True
        if has_strong_negative:
            return False
        
        # Fallback to general indicators
        positive_indicators = ['shows', 'contains', 'displays', 'has', 'includes', 'is', 'showing']
        negative_indicators = ['does not', "doesn't", 'not visible', 'not present', 'not', 'none']
        
        positive_count = sum(1 for indicator in positive_indicators if indicator in response_lower)
        negative_count = sum(1 for indicator in negative_indicators if indicator in response_lower)
        
        # Check if query terms appear in the response
        query_terms = query.lower().split()
        query_in_response = any(term in response_lower for term in query_terms)
        
        # Frame is relevant if:
        # 1. More positive than negative indicators, OR
        # 2. Query terms appear in response and no strong negative indicators
        return (positive_count > negative_count) or (query_in_response and negative_count == 0)
    
    def _calculate_confidence(self, blip2_response: str) -> float:
        """Calculate confidence score based on BLIP-2 response."""
        response_lower = blip2_response.lower()
        
        # Base confidence
        confidence = 0.5
        
        # Increase confidence for strong positive indicators
        if 'yes' in response_lower:
            confidence += 0.3
        if 'clearly' in response_lower or 'definitely' in response_lower:
            confidence += 0.2
        if 'exactly' in response_lower or 'precisely' in response_lower:
            confidence += 0.1
        
        # Decrease confidence for uncertainty
        if 'maybe' in response_lower or 'possibly' in response_lower:
            confidence -= 0.2
        if 'unclear' in response_lower or 'hard to see' in response_lower:
            confidence -= 0.3
        
        return max(0.0, min(1.0, confidence))
    
    def _group_nearby_segments(self, segments: List[Dict], max_gap: float = 2.0) -> List[Dict]:
        """Group nearby segments to avoid duplicates."""
        if not segments:
            return []
        
        grouped = []
        current_group = [segments[0]]
        
        for segment in segments[1:]:
            # Check if segment is close to current group
            last_segment = current_group[-1]
            time_gap = segment['timestamp_seconds'] - last_segment['timestamp_seconds']
            
            if time_gap <= max_gap:
                # Add to current group
                current_group.append(segment)
            else:
                # Save current group and start new one
                grouped_segment = self._merge_segment_group(current_group)
                grouped.append(grouped_segment)
                current_group = [segment]
        
        # Add the last group
        if current_group:
            grouped_segment = self._merge_segment_group(current_group)
            grouped.append(grouped_segment)
        
        return grouped
    
    def _merge_segment_group(self, segments: List[Dict]) -> Dict:
        """Merge a group of nearby segments into one."""
        if len(segments) == 1:
            return segments[0]
        
        # Use the segment with highest confidence as the main one
        best_segment = max(segments, key=lambda x: x['confidence'])
        
        # Extend the time range to cover all segments
        start_time = min(s['start_time'] for s in segments)
        end_time = max(s['end_time'] for s in segments)
        
        merged = best_segment.copy()
        merged['start_time'] = start_time
        merged['end_time'] = end_time
        merged['blip2_description'] = f"Multiple instances found: {best_segment['blip2_description']}"
        
        return merged
    
    def _log_search(self, query: str, results_count: int, response_time_ms: float):
        """Log search query and results."""
        try:
            self.minio_storage.store_search_log(
                query=query,
                results_count=results_count,
                response_time_ms=response_time_ms,
                search_type="blip2_based"
            )
        except Exception as e:
            logger.error(f"Failed to log search: {e}")


# Global BLIP-2 search engine instance
blip2_search_engine = None

def get_blip2_search_engine():
    """Get or create BLIP-2 search engine instance."""
    global blip2_search_engine
    if blip2_search_engine is None:
        blip2_search_engine = BLIP2SearchEngine()
    return blip2_search_engine
