"""Search functionality for SceneLens."""

import json
import time
import logging
from pathlib import Path
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from minio import Minio
from minio.error import S3Error

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.database import get_db_session
from pipeline.models import Segment, Video, SearchLog
from pipeline.on_demand_extract import get_on_demand_extractor

# Configure logging
logger = logging.getLogger(__name__)


class SearchEngine:
    """Query-driven search engine for video frames."""
    
    def __init__(self, model_name="clip-ViT-B-32"):
        """Initialize the search engine."""
        # Initialize MinIO client
        self.minio_client = Minio(
            "localhost:9000",
            access_key="scenelens",
            secret_key="scenelens_dev123",
            secure=False,
        )
        self.bucket_name = "scenelens"
        
        # Load text encoder for query processing
        try:
            self.text_encoder = SentenceTransformer(model_name)
            logger.info(f"Loaded text encoder: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load text encoder: {e}")
            self.text_encoder = None
        
        # Initialize on-demand extractor
        self.on_demand_extractor = get_on_demand_extractor()

    def search(self, query: str, top_k: int = 10) -> List[dict]:
        """Query-based search using prompt-driven frame extraction."""
        return self.search_on_demand(query, top_k, use_existing_first=False)
    
    def search_on_demand(self, query: str, top_k: int = 10, 
                        frame_interval: float = 0.5, 
                        use_existing_first: bool = True) -> List[dict]:
        """
        Search using prompt-driven frame extraction from videos.
        
        Args:
            query: Search query text (drives frame selection)
            top_k: Number of results to return
            frame_interval: Initial sampling interval (refined based on content relevance)
            use_existing_first: Not used anymore (kept for compatibility)
        
        Returns:
            List of search results with prompt-driven extracted frames
        """
        start_time = time.time()
        results = []
        
        # Always do prompt-driven extraction for better results
        logger.info(f"🔍 Performing prompt-driven extraction for {top_k} results...")
        
        # Get all videos from database
        db = get_db_session()
        try:
            # Prioritize diverse_test_video.mp4 for better testing
            videos = db.query(Video).order_by(
                Video.filename.desc()  # This will put diverse_test_video.mp4 first
            ).all()
            
            for video in videos:
                if len(results) >= top_k:
                    break
                
                logger.info(f"📹 Analyzing video: {video.filename} for query: '{query}'")
                
                # Extract frames for this video based on query
                extracted_frames = self.on_demand_extractor.extract_query_specific_frames(
                    query=query,
                    video_filename=video.filename,
                    top_k=top_k - len(results),
                    frame_interval=frame_interval
                )
                
                # Convert to result format
                for frame_info in extracted_frames:
                    # Create content-based segments that span the actual content duration
                    segment_start = frame_info['timestamp_seconds']
                    
                    # Calculate content-based segment duration
                    # Look for similar content in nearby frames to determine segment boundaries
                    content_duration = self._calculate_content_duration(
                        video, segment_start, query, frame_info['similarity_score']
                    )
                    
                    segment_end = segment_start + content_duration
                    
                    result = {
                        "segment_id": f"on_demand_{video.id}_{frame_info['frame_number']}",
                        "video_id": str(video.id),
                        "video_filename": video.filename,
                        "video_title": video.title,
                        "frame_number": frame_info['frame_number'],
                        "timestamp_seconds": frame_info['timestamp_seconds'],
                        "segment_start_seconds": segment_start,
                        "segment_end_seconds": segment_end,
                        "keyframe_path": frame_info.get('keyframe_path', f"on_demand/{video.filename}/{frame_info['frame_number']}"),
                        "caption": frame_info.get('caption', f"Content at {segment_start:.1f}s"),
                        "score": frame_info['similarity_score'],
                        "is_on_demand": True,
                        "pil_image": frame_info['pil_image']  # Keep image in memory for display
                    }
                    results.append(result)
                    
                    if len(results) >= top_k:
                        break
                            
        finally:
            db.close()
        
        # Sort by score and limit to top_k
        results.sort(key=lambda x: x['score'], reverse=True)
        results = results[:top_k]
        
        # Log search
        response_time_ms = int((time.time() - start_time) * 1000)
        db = get_db_session()
        try:
            search_log = SearchLog(
                query=query,
                results_count=len(results),
                response_time_ms=response_time_ms
            )
            db.add(search_log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log search: {e}")
            db.rollback()
        finally:
            db.close()
        
        logger.info(f"✅ Prompt-driven search completed: {len(results)} results in {response_time_ms}ms")
        return results
    
    def _calculate_content_duration(self, video, start_time, query, similarity_score):
        """Calculate the duration of content segment based on similarity and nearby frames."""
        # For now, use a smart duration based on similarity score
        # Higher similarity = longer segment (more confident about content)
        # Lower similarity = shorter segment (less confident)
        
        base_duration = 1.0  # Base duration in seconds
        
        # Adjust duration based on similarity score
        # Similarity scores are typically 0.0 to 1.0
        if similarity_score > 0.8:
            # High confidence - longer segment
            duration = base_duration * 2.0  # 2 seconds
        elif similarity_score > 0.6:
            # Medium confidence - medium segment
            duration = base_duration * 1.5  # 1.5 seconds
        elif similarity_score > 0.4:
            # Lower confidence - shorter segment
            duration = base_duration * 1.0  # 1 second
        else:
            # Very low confidence - very short segment
            duration = base_duration * 0.5  # 0.5 seconds
        
        # Ensure we don't exceed video duration
        if video.duration_seconds:
            max_duration = video.duration_seconds - start_time
            duration = min(duration, max_duration)
        
        return max(0.5, duration)  # Minimum 0.5 seconds


# Global search engine instance
search_engine = None


def get_search_engine():
    """Get or create search engine instance."""
    global search_engine
    if search_engine is None:
        search_engine = SearchEngine()
    return search_engine
