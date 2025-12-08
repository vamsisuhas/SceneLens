#!/usr/bin/env python3
"""X-CLIP based action search engine for temporal video understanding."""

import os
import sys
import time
import logging
import tempfile
from typing import List, Dict, Optional
from PIL import Image
import torch
import numpy as np
from pathlib import Path
from io import BytesIO
import cv2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minio_storage import MinIOStorage
from minio import Minio
from backend.video_chunker import VideoChunker, extract_keyframe_from_window

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_CLIP_DURATION = 20.0
DEFAULT_OVERLAP = 10.0
DEFAULT_NUM_FRAMES = 8  # Fixed by X-CLIP model architecture (positional embeddings)
DEFAULT_TOP_K = 10
JPEG_QUALITY = 85


class ActionSearchEngine:
    """X-CLIP based action detection engine."""
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None
        self.minio_client = None
        self.minio_storage = None
        self.bucket_name = "scenelens"
        self.blip2_engine = None  # For verification
        self._initialize_models()
        self._initialize_minio()
        self._initialize_blip2_verifier()
    
    def _initialize_models(self):
        """Initialize X-CLIP model for video-text similarity."""
        logger.info("🔄 Loading X-CLIP pretrained model for action detection...")
        
        from transformers.models.x_clip import XCLIPProcessor, XCLIPModel
        
        model_name = "microsoft/xclip-base-patch16"
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        
        self.processor = XCLIPProcessor.from_pretrained(model_name)
        self.model = XCLIPModel.from_pretrained(model_name).to(self.device)
        self.model.eval()
        
        
        logger.info("✅ X-CLIP model loaded successfully!")
    
    
    def _initialize_minio(self):
        """Initialize MinIO client."""
        try:
            self.minio_client = Minio(
                "127.0.0.1:9000",
                access_key="scenelens",
                secret_key="scenelens_dev123",
                secure=False,
                region="us-east-1"
            )
            self.minio_storage = MinIOStorage(self.minio_client, self.bucket_name)
            logger.info("✅ MinIO client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize MinIO: {e}")
    
    def _initialize_blip2_verifier(self):
        """Initialize BLIP-2 engine for verification (reuse existing instance)."""
        try:
            from backend.blip2_search import get_blip2_search_engine
            self.blip2_engine = get_blip2_search_engine()
            logger.info("✅ BLIP-2 verifier initialized (reusing existing model)")
        except Exception as e:
            logger.warning(f"⚠️ BLIP-2 verifier not available: {e}. Verification disabled.")
            self.blip2_engine = None
    
    def _compute_similarity(self, frames: List[Image.Image], text: str) -> float:
        """Compute similarity between video frames and text using X-CLIP."""
        from torch.nn import functional as F
        import numpy as np
        
        # Ensure RGB format for all frames
        frames = [f.convert("RGB") if isinstance(f, Image.Image) else Image.fromarray(f).convert("RGB") for f in frames]
        
        # X-CLIP processor in transformers 4.36.2 uses 'images' parameter (not 'videos')
        video_inputs = self.processor(images=frames, return_tensors="pt")
        text_inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        
        # X-CLIP expects shape: (batch, num_frames, channels, height, width)
        # New processor returns batched videos directly; add batch dim only if needed
        pixel_values = video_inputs['pixel_values']
        logger.info(f"[XCLIP DEBUG] pixel_values shape BEFORE reshape: {tuple(pixel_values.shape)}")
        if pixel_values.dim() == 4:
            pixel_values = pixel_values.unsqueeze(0)
        
        input_ids = text_inputs['input_ids']
        attention_mask = text_inputs['attention_mask']
        
        # Move to device
        pixel_values = pixel_values.to(self.device)
        input_ids = input_ids.to(self.device)
        attention_mask = attention_mask.to(self.device)
        
        logger.info(f"[XCLIP] pixel_values shape = {tuple(pixel_values.shape)}")
        
        with torch.no_grad():
            # Forward pass through model
            outputs = self.model(
                pixel_values=pixel_values,
                input_ids=input_ids,
                attention_mask=attention_mask,
                return_dict=True
            )
            
            # Extract embeddings
            video_features = outputs.video_embeds
            text_features = outputs.text_embeds
            
            # Normalize features
            video_features = F.normalize(video_features, dim=-1)
            text_features = F.normalize(text_features, dim=-1)
            
            # Compute cosine similarity
            # Both are shape (1, 512), so we compute dot product
            similarity = (video_features * text_features).sum(dim=-1).squeeze()
            
            # Scale to [0, 1]
            similarity = (similarity + 1) / 2.0
        
        return float(similarity.cpu())
    
    
    def _extract_frames_every_n_seconds(self, video_path: str, start_time: float, end_time: float, interval: float = 2.0) -> List[Image.Image]:
        """
        Extract frames every N seconds from a video segment.
        Returns list of PIL Images.
        """
        frames = []
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        current_time = start_time
        while current_time <= end_time:
            frame_number = int(current_time * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            
            if ret:
                # Convert BGR to RGB and then to PIL Image
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                frames.append(pil_image)
            
            current_time += interval
        
        cap.release()
        return frames
    
    def _verify_action_with_blip2(self, video_path: str, segment_start: float, segment_end: float, action_query: str) -> tuple:
        """
        Verify if action is present in segment by checking frames every 2 seconds.
        Returns (is_valid: bool, explanation: str)
        If ANY frame shows the action, segment is valid.
        """
        if not self.blip2_engine or not self.blip2_engine.blip2_model:
            # If BLIP-2 not available, accept all (fallback)
            return True, "Verification disabled"
        
        try:
            # Extract frames every 2 seconds from the segment
            frames = self._extract_frames_every_n_seconds(video_path, segment_start, segment_end, interval=2.0)
            
            if not frames:
                logger.warning(f"No frames extracted from segment {segment_start:.1f}s-{segment_end:.1f}s")
                return False, "No frames extracted"
            
            logger.info(f"🔍 Verifying {len(frames)} frames from {segment_start:.1f}s-{segment_end:.1f}s")
            
            # Ask BLIP-2 for each frame
            question = f"Is there {action_query} in this image? Answer yes or no."
            verified_frames = 0
            all_responses = []
            
            for idx, frame in enumerate(frames):
                # Process with InstructBLIP
                inputs = self.blip2_engine.blip2_processor(
                    images=frame,
                    text=question,
                    return_tensors="pt"
                ).to(self.blip2_engine.blip2_model.device)
                
                # Generate answer
                with torch.no_grad():
                    output = self.blip2_engine.blip2_model.generate(
                        **inputs,
                        max_new_tokens=30,
                        do_sample=False,
                        temperature=0.0
                    )
                
                # Decode response
                response = self.blip2_engine.blip2_processor.decode(output[0], skip_special_tokens=True)
                
                # Extract answer (remove question if present)
                if question in response:
                    response = response.split(question)[-1].strip()
                
                # Check for positive indicators
                response_lower = response.lower()
                is_match = any(word in response_lower for word in ['yes', 'visible', 'shows', 'there is'])
                
                if is_match:
                    verified_frames += 1
                    logger.info(f"   Frame {idx+1}/{len(frames)}: ✅ MATCH - {response}")
                else:
                    logger.info(f"   Frame {idx+1}/{len(frames)}: ❌ NO MATCH - {response}")
                
                all_responses.append(response)
            
            # If ANY frame matches, keep the segment
            is_valid = verified_frames > 0
            summary = f"{verified_frames}/{len(frames)} frames matched"
            
            logger.info(f"🔍 BLIP-2 Verification: '{action_query}' -> {summary} -> {'✅ PASS' if is_valid else '❌ FAIL'}")
            
            return is_valid, summary
            
        except Exception as e:
            logger.error(f"⚠️ CRITICAL: BLIP-2 verification failed: {e}")
            return False, f"Verification unavailable: {e}"  # Reject on error for safety
    
    def _save_keyframe_to_minio(self, keyframe: Image.Image, video_filename: str, 
                                segment_id: str, timestamp: float) -> str:
        """Save keyframe to MinIO and return the path."""
        try:
            img_byte_arr = BytesIO()
            keyframe.save(img_byte_arr, format='JPEG', quality=JPEG_QUALITY)
            img_byte_arr.seek(0)
            
            video_stem = Path(video_filename).stem
            frame_filename = f"segment_{segment_id}_t{timestamp:.2f}s_action.jpg"
            minio_path = f"frames/{video_stem}/action_segments/{frame_filename}"
            
            self.minio_client.put_object(
                self.bucket_name,
                minio_path,
                img_byte_arr,
                length=img_byte_arr.getbuffer().nbytes,
                content_type="image/jpeg"
            )
            
            return minio_path
            
        except Exception as e:
            logger.error(f"Failed to save keyframe to MinIO: {e}")
            return f"frames/{Path(video_filename).stem}/action_segments/fallback.jpg"
    
    def _apply_nms(self, segments, iou_threshold=0.3):
        """
        Apply Non-Maximum Suppression to remove overlapping segments.
        
        Args:
            segments: List of segment dictionaries
            iou_threshold: IoU threshold for considering segments as overlapping
        
        Returns:
            Filtered list of non-overlapping segments
        """
        if not segments:
            return segments
        
        # Sort by score (descending)
        sorted_segments = sorted(segments, key=lambda x: x['score'], reverse=True)
        
        kept_segments = []
        
        for seg in sorted_segments:
            # Check if this segment overlaps significantly with any kept segment
            overlap_found = False
            
            for kept_seg in kept_segments:
                # Calculate IoU (Intersection over Union)
                start_max = max(seg['segment_start_seconds'], kept_seg['segment_start_seconds'])
                end_min = min(seg['segment_end_seconds'], kept_seg['segment_end_seconds'])
                
                intersection = max(0, end_min - start_max)
                
                duration1 = seg['segment_end_seconds'] - seg['segment_start_seconds']
                duration2 = kept_seg['segment_end_seconds'] - kept_seg['segment_start_seconds']
                union = duration1 + duration2 - intersection
                
                iou = intersection / union if union > 0 else 0
                
                if iou > iou_threshold:
                    overlap_found = True
                    break
            
            if not overlap_found:
                kept_segments.append(seg)
        
        logger.info(f"📊 NMS: Reduced {len(segments)} segments to {len(kept_segments)} non-overlapping segments")
        return kept_segments
    
    def search_action(
        self,
        video_id: str,
        action_query: str,
        clip_duration: float = DEFAULT_CLIP_DURATION,
        overlap: float = DEFAULT_OVERLAP,
        num_frames: int = DEFAULT_NUM_FRAMES,
        top_k: int = DEFAULT_TOP_K,
        base_segments: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        Search for actions in video using InternVideo2.
        
        Args:
            video_id: Video ID in MinIO
            action_query: Action description (e.g., "drone landing")
            clip_duration: Duration of each temporal window in seconds
            overlap: Overlap between consecutive windows in seconds
            num_frames: Number of frames to sample per clip
            top_k: Number of top results to return
            base_segments: Optional pre-filtered segments from object detection
            
        Returns:
            List of action detection results with timestamps and scores
        """
        if not self.model:
            logger.error("InternVideo2 model not available")
            return []
        
        start_time = time.time()
        
        try:
            # Get video from MinIO
            video = self.minio_storage.get_video_metadata(video_id)
            if not video:
                logger.error(f"Video {video_id} not found")
                return []
            
            logger.info(f"🎬 Action search for '{action_query}' in video: {video['filename']}")
            
            # Download video to temporary file
            video_obj = self.minio_client.get_object(self.bucket_name, f"videos/{video['filename']}")
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
                tmp_file.write(video_obj.read())
                tmp_video_path = tmp_file.name
            
            logger.info(f"📁 Video downloaded to: {tmp_video_path}")
            
            # Initialize video chunker
            chunker = VideoChunker(tmp_video_path)
            
            # Get temporal windows
            windows = chunker.get_temporal_windows(
                clip_duration=clip_duration,
                overlap=overlap
            )
            
            logger.info(f"🔪 Split video into {len(windows)} overlapping windows")
            
            # Process each window
            window_scores = []
            for window in windows:
                logger.info(f"Processing {window}")
                
                # Extract frames from window
                frames = chunker.extract_frames_from_window(
                    window,
                    num_frames=num_frames,
                    return_pil=True
                )
                
                if len(frames) < num_frames:
                    logger.warning(f"Only got {len(frames)} frames from {window}")
                    continue
                
                # Compute similarity using InternVideo2
                similarity = self._compute_similarity(frames, action_query)
                
                window_scores.append({
                    'window': window,
                    'score': similarity,
                    'frames': frames
                })
                
                logger.info(f"  → Similarity: {similarity:.3f}")
            
            # Sort by score
            window_scores.sort(key=lambda x: x['score'], reverse=True)
            
            # === Adaptive score calibration (NumPy-only) ===
            import numpy as np

            scores = np.array([w["score"] for w in window_scores], dtype=np.float32)
            if scores.size > 1:
                mean = float(scores.mean())
                std = float(scores.std())
                if std > 0:
                    zs = (scores - mean) / std
                else:
                    zs = scores * 0.0
                probs = 1.0 / (1.0 + np.exp(-zs))
                for i, w in enumerate(window_scores):
                    w["score"] = float(probs[i])
            
            # Calculate score threshold based on score distribution
            if window_scores:
                top_score = window_scores[0]['score']
                score_threshold = top_score * 0.75  # Increased from 0.6 for higher precision
            else:
                score_threshold = 0
            
            # Aggregate overlapping windows to find continuous segments
            results = []
            used_windows = set()
            
            for i, item in enumerate(window_scores[:top_k]):
                window = item['window']
                score = item['score']
                
                if window.window_id in used_windows or score < score_threshold:
                    continue
                
                # Start a new segment with this window
                segment_start = window.start_time
                segment_end = window.end_time
                segment_scores = [score]
                used_windows.add(window.window_id)
                
                # Merge overlapping or adjacent windows with high scores
                for j, other_item in enumerate(window_scores):
                    other_window = other_item['window']
                    other_score = other_item['score']
                    
                    if other_window.window_id in used_windows:
                        continue
                    
                    # Check if windows are adjacent (window_id difference) or temporally overlapping
                    is_adjacent = abs(other_window.window_id - window.window_id) <= 1
                    
                    # Check for temporal overlap with the growing segment
                    temporally_overlaps = (
                        other_window.start_time < segment_end and 
                        other_window.end_time > segment_start
                    )
                    
                    # Merge if: (adjacent OR overlapping) AND high score
                    if (is_adjacent or temporally_overlaps) and other_score >= score_threshold:
                        segment_start = min(segment_start, other_window.start_time)
                        segment_end = max(segment_end, other_window.end_time)
                        segment_scores.append(other_score)
                        used_windows.add(other_window.window_id)
                
                # Calculate aggregate score
                avg_score = np.mean(segment_scores)
                
                # BLIP-2 Verification: Check frames every 2 seconds in segment
                # If ANY frame matches, keep the segment
                is_valid, verification_response = self._verify_action_with_blip2(
                    tmp_video_path, 
                    segment_start, 
                    segment_end, 
                    action_query
                )
                
                if not is_valid:
                    logger.info(f"⚠️ Segment rejected by BLIP-2: {segment_start:.1f}s-{segment_end:.1f}s (score={avg_score:.3f})")
                    continue  # Skip this segment
                
                # Extract keyframe from segment (for display)
                try:
                    keyframe = extract_keyframe_from_window(
                        tmp_video_path,
                        segment_start,
                        segment_end
                    )
                    
                    segment_id = f"action_{i:03d}"
                    mid_timestamp = (segment_start + segment_end) / 2.0
                    
                    keyframe_path = self._save_keyframe_to_minio(
                        keyframe,
                        video['filename'],
                        segment_id,
                        mid_timestamp
                    )
                    
                    results.append({
                        'segment_id': segment_id,
                        'video_id': video_id,
                        'video_filename': video['filename'],
                        'video_title': video.get('title', video['filename']),
                        'frame_number': int(mid_timestamp * chunker.fps),
                        'timestamp_seconds': mid_timestamp,
                        'segment_start_seconds': segment_start,
                        'segment_end_seconds': segment_end,
                        'keyframe_path': keyframe_path,
                        'caption': f"Action: {action_query}",
                        'score': float(avg_score),
                        'verification': verification_response,  # Add BLIP-2 response
                        'is_on_demand': False
                    })
                    
                    if len(results) >= top_k:
                        break
                        
                except Exception as e:
                    logger.error(f"Failed to extract keyframe for segment: {e}")
                    continue
            
            # Apply Non-Maximum Suppression to remove ALL overlapping segments
            # Use iou_threshold=0.0 to ensure zero tolerance for overlaps
            results = self._apply_nms(results, iou_threshold=0.0)
            
            # Sort results by timestamp (chronological order)
            results.sort(key=lambda x: x['segment_start_seconds'])
            
            # Cleanup
            chunker.release()
            try:
                os.remove(tmp_video_path)
            except:
                pass
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Action search completed in {elapsed:.2f}s - found {len(results)} segments")
            
            return results
            
        except Exception as e:
            logger.error(f"Action search failed: {e}", exc_info=True)
            return []


# Singleton instance
_action_search_engine = None

def get_action_search_engine() -> ActionSearchEngine:
    """Get or create the singleton ActionSearchEngine instance."""
    global _action_search_engine
    if _action_search_engine is None:
        _action_search_engine = ActionSearchEngine()
    return _action_search_engine

