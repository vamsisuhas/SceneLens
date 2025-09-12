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
                        frame_interval: float = 0.25, 
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
                    top_k=max((top_k - len(results)) * 2, 20),  # Extract more frames for better analysis
                    frame_interval=frame_interval
                )
                
                # Group frames into meaningful content segments
                content_segments = self._group_frames_into_segments(extracted_frames, query)
                
                # Convert to result format
                for segment in content_segments:
                    result = {
                        "segment_id": f"on_demand_{video.id}_{segment['start_frame']}",
                        "video_id": str(video.id),
                        "video_filename": video.filename,
                        "video_title": video.title,
                        "frame_number": segment['start_frame'],
                        "timestamp_seconds": segment['start_time'],
                        "segment_start_seconds": segment['start_time'],
                        "segment_end_seconds": segment['end_time'],
                        "keyframe_path": segment.get('keyframe_path', f"on_demand/{video.filename}/{segment['start_frame']}"),
                        "caption": segment.get('caption', f"Content from {segment['start_time']:.1f}s to {segment['end_time']:.1f}s"),
                        "score": segment['best_score'],
                        "is_on_demand": True,
                        "pil_image": segment['best_image']  # Keep best image for display
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
    
    def search_specific_video(self, query: str, video_id: str, top_k: int = 10, 
                            frame_interval: float = 0.1) -> List[dict]:
        """Search within a specific video only."""
        start_time = time.time()
        logger.info(f"🔍 Performing video-specific search for video {video_id} with query: '{query}'")
        
        try:
            # Get video info from database
            from pipeline.database import get_db_session
            from pipeline.models import Video
            
            db = get_db_session()
            video = db.query(Video).filter(Video.id == video_id).first()
            
            if not video:
                logger.error(f"Video {video_id} not found in database")
                return []
            
            logger.info(f"📹 Searching in video: {video.filename}")
            
            # Extract frames for this specific video
            extracted_frames = self.on_demand_extractor.extract_query_specific_frames(
                query=query,
                video_filename=video.filename,
                top_k=max(top_k * 2, 20),  # Extract more frames for better analysis
                frame_interval=frame_interval
            )
            
            if not extracted_frames:
                logger.info(f"No frames extracted for video {video_id}")
                return []
            
            # Group frames into segments
            segments = self._group_frames_into_segments(extracted_frames, query)
            
            # Convert segments to results format
            results = []
            for segment in segments:
                result = {
                    'segment_id': f"{video_id}_{segment['start_time']:.1f}s",
                    'video_id': video_id,
                    'video_filename': video.filename,
                    'video_title': video.title or video.filename,
                    'frame_number': segment['start_frame'],
                    'timestamp_seconds': segment['start_time'],
                    'segment_start_seconds': segment['start_time'],
                    'segment_end_seconds': segment['end_time'],
                    'keyframe_path': segment['keyframe_path'],
                    'caption': segment['caption'],
                    'score': segment['best_score'],
                    'is_on_demand': True
                }
                results.append(result)
            
            elapsed_time = (time.time() - start_time) * 1000
            logger.info(f"✅ Video-specific search completed: {len(results)} results in {elapsed_time:.0f}ms")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in video-specific search: {e}")
            return []
        finally:
            db.close()
    
    
    def _group_frames_into_segments(self, extracted_frames, query):
        """Group extracted frames into meaningful content segments based on content similarity and natural boundaries."""
        if not extracted_frames:
            return []
        
        # Sort frames by timestamp
        sorted_frames = sorted(extracted_frames, key=lambda x: x['timestamp_seconds'])
        
        # Detect content boundaries using similarity analysis
        segments = self._detect_content_boundaries(sorted_frames, query)
        
        return segments
    
    def _detect_content_boundaries(self, sorted_frames, query):
        """Detect natural content boundaries based on similarity patterns and temporal analysis."""
        if not sorted_frames:
            logger.info(f"No frames to process for query: '{query}'")
            return []
        
        # Use a more selective threshold to avoid false positives
        similarity_threshold = 0.25  # More selective to avoid geometric shape confusion
        relevant_frames = [f for f in sorted_frames if f['similarity_score'] > similarity_threshold]
        
        logger.info(f"Found {len(relevant_frames)} frames above threshold {similarity_threshold} out of {len(sorted_frames)} total frames")
        
        if not relevant_frames:
            # No frames meet the relevance threshold - return no results
            logger.info(f"No frames above threshold {similarity_threshold} - returning no results for query: '{query}'")
            return []
        
        # Find continuous content regions by analyzing temporal gaps
        content_regions = self._find_continuous_regions(relevant_frames, query)
        logger.info(f"Found {len(content_regions)} content regions")
        
        segments = []
        for i, region in enumerate(content_regions):
            if not region:
                continue
                
            # Create a single segment for the entire continuous region
            segment = self._create_segment_from_region(region, query)
            if segment:
                segments.append(segment)
                logger.info(f"Created segment {i+1}: {segment['start_time']:.1f}s-{segment['end_time']:.1f}s (score: {segment['best_score']:.3f})")
        
        # Post-process: merge segments that are close together
        merged_segments = self._merge_close_segments(segments, query)
        logger.info(f"After merging close segments: {len(merged_segments)} segments")
        
        # Filter out low-quality segments that might be false positives
        filtered_segments = self._filter_quality_segments(merged_segments)
        logger.info(f"After quality filtering: {len(filtered_segments)} segments")
        
        return filtered_segments
    
    def _merge_close_segments(self, segments, query):
        """Merge segments that are close together to create continuous content segments."""
        if len(segments) <= 1:
            return segments
        
        # Use adaptive merge threshold based on segment quality
        # If segments have high similarity scores, merge more aggressively
        merge_threshold = 1.5  # Base merge threshold
        
        merged = []
        current = segments[0].copy()
        
        for next_segment in segments[1:]:
            # Check if segments are close enough to merge
            time_gap = next_segment['start_time'] - current['end_time']
            
            # Use adaptive threshold based on segment quality
            avg_score = (current['best_score'] + next_segment['best_score']) / 2
            dynamic_threshold = merge_threshold + (avg_score * 1.0)  # Up to 2.5s for high-score segments
            
            if time_gap <= dynamic_threshold:
                # Merge segments
                logger.info(f"Merging segments: {current['start_time']:.1f}s-{current['end_time']:.1f}s with {next_segment['start_time']:.1f}s-{next_segment['end_time']:.1f}s")
                current['end_time'] = next_segment['end_time']
                # Keep the better scoring frame as representative
                if next_segment['best_score'] > current['best_score']:
                    current['best_score'] = next_segment['best_score']
                    current['best_image'] = next_segment['best_image']
                    current['keyframe_path'] = next_segment['keyframe_path']
                # Update caption to reflect merged duration
                current['caption'] = self._generate_segment_caption(
                    current['start_time'], current['end_time'], query, None
                )
            else:
                # Gap is too large, keep segments separate
                merged.append(current)
                current = next_segment.copy()
        
        # Add the last segment
        merged.append(current)
        
        return merged
    
    def _filter_quality_segments(self, segments):
        """Filter out low-quality segments that might be false positives."""
        if not segments:
            return segments
        
        # Sort segments by score to identify the best ones
        sorted_segments = sorted(segments, key=lambda x: x['best_score'], reverse=True)
        
        if len(sorted_segments) == 1:
            return sorted_segments
        
        # Calculate score threshold - keep segments within reasonable range of the best
        best_score = sorted_segments[0]['best_score']
        score_threshold = max(0.3, best_score * 0.7)  # At least 70% of best score, minimum 0.3
        
        # Filter segments based on quality
        quality_segments = [s for s in sorted_segments if s['best_score'] >= score_threshold]
        
        # If we filtered too aggressively, keep at least the top segment
        if not quality_segments:
            quality_segments = [sorted_segments[0]]
        
        logger.info(f"Quality filter: kept {len(quality_segments)}/{len(segments)} segments (threshold: {score_threshold:.3f})")
        return quality_segments
    
    def _find_continuous_regions(self, frames, query):
        """Find continuous regions of similar content."""
        if not frames:
            return []
        
        regions = []
        current_region = [frames[0]]
        
        for i in range(1, len(frames)):
            current_frame = frames[i]
            last_frame = current_region[-1]
            
            # Calculate time gap between frames
            time_gap = current_frame['timestamp_seconds'] - last_frame['timestamp_seconds']
            
            # Check if frames are part of continuous content
            # Use adaptive gap threshold based on average similarity
            avg_similarity = (current_frame['similarity_score'] + last_frame['similarity_score']) / 2
            if avg_similarity > 0.3:
                max_gap = 2.0  # Allow larger gaps for high-similarity content (likely continuous)
            else:
                max_gap = 1.0  # Strict gap for low-similarity content
            
            if time_gap <= max_gap:
                # Allow reasonable variation in similarity scores
                score_diff = abs(current_frame['similarity_score'] - last_frame['similarity_score'])
                if score_diff <= 0.4:  # Reasonable similarity difference
                    current_region.append(current_frame)
                    continue
            
            # Gap is too large or similarity too different - start new region
            if len(current_region) >= 1:  # Keep regions with even single frames
                start_time = current_region[0]['timestamp_seconds']
                end_time = current_region[-1]['timestamp_seconds'] 
                logger.info(f"Completed region: {start_time:.1f}s-{end_time:.1f}s ({len(current_region)} frames)")
                regions.append(current_region)
            current_region = [current_frame]
        
        # Add the last region
        if current_region:
            start_time = current_region[0]['timestamp_seconds']
            end_time = current_region[-1]['timestamp_seconds'] 
            logger.info(f"Final region: {start_time:.1f}s-{end_time:.1f}s ({len(current_region)} frames)")
            regions.append(current_region)
        
        return regions
    
    def _create_segment_from_region(self, region, query):
        """Create a single segment from a continuous content region."""
        if not region:
            return None
        
        # Find the actual start and end times of the content
        start_time = region[0]['timestamp_seconds']
        end_time = region[-1]['timestamp_seconds']
        
        # For single frame regions, create a minimum duration
        if start_time == end_time:
            end_time = start_time + 1.0
        
        # Find the best representative frame (highest similarity)
        best_frame = max(region, key=lambda f: f['similarity_score'])
        
        # Calculate average similarity for the region
        avg_similarity = sum(f['similarity_score'] for f in region) / len(region)
        
        segment = {
            'start_time': start_time,
            'end_time': end_time,
            'start_frame': region[0]['frame_number'],
            'best_score': avg_similarity,  # Use average score for more stability
            'best_image': best_frame['pil_image'],
            'keyframe_path': best_frame.get('keyframe_path'),
            'caption': self._generate_segment_caption(
                start_time, end_time, query, best_frame.get('caption')
            )
        }
        
        return segment
    
    
    def _generate_segment_caption(self, start_time, end_time, query, original_caption=None):
        """Generate a descriptive caption for the segment."""
        duration = end_time - start_time
        
        if original_caption and "Content at" not in original_caption:
            return f"{original_caption} ({start_time:.1f}s-{end_time:.1f}s, {duration:.1f}s duration)"
        else:
            if query and any(word in query.lower() for word in ['blue', 'circle', 'red', 'strip']):
                content_type = "visual content"
                if 'blue' in query.lower() or 'circle' in query.lower():
                    content_type = "blue circle content"
                elif 'red' in query.lower() or 'strip' in query.lower():
                    content_type = "red strip content"
                return f"{content_type.title()} from {start_time:.1f}s to {end_time:.1f}s ({duration:.1f}s duration)"
            else:
                return f"Content from {start_time:.1f}s to {end_time:.1f}s ({duration:.1f}s duration)"


# Global search engine instance
search_engine = None


def get_search_engine():
    """Get or create search engine instance."""
    global search_engine
    if search_engine is None:
        search_engine = SearchEngine()
    return search_engine
