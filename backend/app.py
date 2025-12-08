#!/usr/bin/env python3
"""FastAPI application for SceneLens search API."""

import os
import logging
import threading
import time
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
import uvicorn
from minio.error import S3Error

import sys
import os
import subprocess
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.blip2_search import get_blip2_search_engine
from backend.action_search import get_action_search_engine
from minio_storage import MinIOStorage
from minio import Minio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MinIO client with explicit region
minio_client = Minio(
    "127.0.0.1:9000",
    access_key="scenelens",
    secret_key="scenelens_dev123",
    secure=False,
    region="us-east-1"
)

# Initialize MinIO storage
bucket_name = "scenelens"
minio_storage = MinIOStorage(minio_client, bucket_name)


# Pydantic models
class SearchResult(BaseModel):
    segment_id: str
    video_id: str
    video_filename: Optional[str]
    video_title: Optional[str]
    frame_number: int
    timestamp_seconds: float
    segment_start_seconds: Optional[float] = None
    segment_end_seconds: Optional[float] = None
    keyframe_path: str
    caption: Optional[str]
    score: float
    is_on_demand: Optional[bool] = False


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int
    search_type: str


class PriorityObject(BaseModel):
    object: str
    priority: int  # Simple numeric priority: 1, 2, 3, 4, etc.


class MultiObjectSearchRequest(BaseModel):
    objects: List[PriorityObject]
    top_k: int = 20
    frame_interval: float = 0.5


# Create FastAPI app
app = FastAPI(
    title="SceneLens Search API",
    description="Semantic search API for video frames using CLIP and BLIP-2",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def validate_video_format(video_path: str, original_filename: str) -> bool:
    """
    Log video file information and accept any file.
    """
    try:
        # Check video format using file command for logging
        result = subprocess.run(['file', video_path], capture_output=True, text=True)
        file_info = result.stdout
        
        logger.info(f"Uploading video: {original_filename} - Format: {file_info}")
        return True
            
    except Exception as e:
        logger.error(f"Error checking video format: {e}")
        return True  # Accept anyway


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SceneLens BLIP-2 Video Search API - Enhanced Accuracy",
        "version": "2.0.0",
        "search_engine": "BLIP-2 (Vision-Language Model)",
        "endpoints": {
            "search_video": "/search/video/{video_id}?q=<query>&top_k=<number> (InstructBLIP Object Detection)",
            "search_action": "/search/action/{video_id}?q=<action_query> (X-CLIP Action Detection)",
            "search_object_action": "/search/object-action/{video_id}?object_query=<obj>&action_query=<act> (Two-Stage)",
            "search_multi_object": "/search/multi-object/{video_id} (POST) - Multi-object priority search",
            "analyze_video_auto": "/analyze-video-auto/{video_id} (POST) - Automatic video analysis with clustering",
            "summarize_segments": "/summarize-segments/ (POST) - Generate BLIP-2 summaries for segments",
            "cluster_segments": "/cluster-segments/ (POST) - Cluster segments by summaries",
            "get_video_file": "/video/{video_id}/file",
            "get_image": "/image/{path}",
            "upload_video": "/upload-video/",
            "process_video": "/process-video/",
            "check_minio_videos": "/check-minio-videos",
            "health": "/health",
            "docs": "/docs"
        }
    }

@app.get("/search/video/{video_id}", response_model=SearchResponse)
async def search_specific_video(
    video_id: str,
    q: str = Query(..., description="Search query text"),
    top_k: int = Query(10, description="Number of results to return", ge=1, le=50),
    frame_interval: float = Query(0.1, description="Frame extraction interval in seconds", ge=0.1)
):
    """Search within a specific video using BLIP-2 for object detection."""
    try:
        # Use BLIP-2 search for object detection
        from backend.blip2_search import get_blip2_search_engine
        blip2_engine = get_blip2_search_engine()
        
        results = blip2_engine.search_video_with_blip2(
            video_id=video_id,
            query=q,
            top_k=top_k,
            frame_interval=frame_interval
        )
        
        return SearchResponse(
            query=q,
            results=results,
            total_results=len(results),
            search_type="blip2_object_detection"
        )
    except Exception as e:
        logger.error(f"BLIP-2 video search failed: {e}")
        raise HTTPException(status_code=500, detail=f"BLIP-2 video search failed: {str(e)}")


@app.get("/search/action/{video_id}", response_model=SearchResponse)
async def search_action(
    video_id: str,
    q: str = Query(..., description="Action query (e.g., 'drone landing', 'person running')"),
    top_k: int = Query(10, description="Number of results to return", ge=1, le=50),
    clip_duration: float = Query(20.0, description="Temporal window duration in seconds", ge=1.0, le=60.0),
    overlap: float = Query(10.0, description="Overlap between windows in seconds", ge=0.0, le=30.0),
    num_frames: int = Query(8, description="Frames per clip for X-CLIP", ge=4, le=16)
):
    """Search for actions in a video using X-CLIP temporal analysis."""
    try:
        action_engine = get_action_search_engine()
        
        results = action_engine.search_action(
            video_id=video_id,
            action_query=q,
            clip_duration=clip_duration,
            overlap=overlap,
            num_frames=num_frames,
            top_k=top_k,
            base_segments=None  # Full video search
        )
        
        return SearchResponse(
            query=q,
            results=results,
            total_results=len(results),
            search_type="xclip_action_detection"
        )
    except Exception as e:
        logger.error(f"X-CLIP action search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Action search failed: {str(e)}")


@app.get("/search/object-action/{video_id}", response_model=SearchResponse)
async def search_object_then_action(
    video_id: str,
    object_query: str = Query(..., description="Object to detect (e.g., 'person', 'car', 'drone')"),
    action_query: str = Query(..., description="Action to detect (e.g., 'running', 'landing', 'jumping')"),
    top_k: int = Query(10, description="Number of final results to return", ge=1, le=50),
    frame_interval: float = Query(0.1, description="Frame interval for object detection", ge=0.1),
    num_frames: int = Query(8, description="Frames per clip for action detection", ge=4, le=16)
):
    """
    Two-stage search: First detect objects with InstructBLIP, then detect actions in those segments with X-CLIP.
    Example: object_query='person', action_query='running' -> Find people who are running
    """
    try:
        # Stage 1: Object detection with InstructBLIP
        logger.info(f"Stage 1: Searching for object '{object_query}'")
        blip2_engine = get_blip2_search_engine()
        
        object_results = blip2_engine.search_video_with_blip2(
            video_id=video_id,
            query=object_query,
            top_k=50,  # Get more candidates for action filtering
            frame_interval=frame_interval
        )
        
        if not object_results:
            return SearchResponse(
                query=f"{object_query} + {action_query}",
                results=[],
                total_results=0,
                search_type="two_stage_object_action_no_objects"
            )
        
        logger.info(f"Stage 1 complete: Found {len(object_results)} segments with '{object_query}'")
        
        # Stage 2: Action detection with X-CLIP on object segments
        logger.info(f"Stage 2: Searching for action '{action_query}' in detected segments")
        action_engine = get_action_search_engine()
        
        action_results = action_engine.search_action(
            video_id=video_id,
            action_query=action_query,
            clip_duration=20.0,  # Use default for two-stage
            overlap=10.0,
            num_frames=num_frames,
            top_k=top_k,
            base_segments=object_results  # Only search in object-detected segments
        )
        
        # Enhance captions to show both object and action
        for result in action_results:
            result['caption'] = f"{object_query} {action_query} (confidence: {result['score']:.2f})"
        
        logger.info(f"Stage 2 complete: Found {len(action_results)} segments with '{action_query}'")
        
        return SearchResponse(
            query=f"{object_query} {action_query}",
            results=action_results,
            total_results=len(action_results),
            search_type="two_stage_object_action"
        )
        
    except Exception as e:
        logger.error(f"Two-stage search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Two-stage search failed: {str(e)}")


# Pydantic models for multi-object priority search
class PriorityObject(BaseModel):
    object: str
    priority: int  # Simple numeric priority: 1, 2, 3, 4, etc.


class MultiObjectSearchRequest(BaseModel):
    objects: List[PriorityObject]
    top_k: int = 20
    frame_interval: float = 0.5


@app.post("/search/multi-object/{video_id}", response_model=SearchResponse)
async def search_multi_object_priority(
    video_id: str,
    request: MultiObjectSearchRequest
):
    """
    Multi-object priority search: Search for multiple objects with priority weights.
    Higher priority numbers = more important (e.g., priority 5 > priority 1).
    Results are combined with weighted scoring based on priorities.
    """
    try:
        if not request.objects:
            raise HTTPException(status_code=400, detail="At least one object is required")
        
        logger.info(f"Multi-object priority search for video {video_id}")
        logger.info(f"Objects: {[(obj.object, obj.priority) for obj in request.objects]}")
        
        from backend.blip2_search import get_blip2_search_engine
        blip2_engine = get_blip2_search_engine()
        
        # Search for each object
        all_object_results = {}
        for priority_obj in request.objects:
            obj_name = priority_obj.object
            priority = priority_obj.priority
            
            logger.info(f"Searching for '{obj_name}' with priority {priority}")
            
            results = blip2_engine.search_video_with_blip2(
                video_id=video_id,
                query=obj_name,
                top_k=50,  # Get more results to combine
                frame_interval=request.frame_interval
            )
            
            # Store results with priority
            all_object_results[obj_name] = {
                'results': results,
                'priority': priority
            }
        
        # Combine results with weighted scoring
        # Create time-based segments and aggregate scores
        combined_segments = {}
        
        for obj_name, obj_data in all_object_results.items():
            priority = obj_data['priority']
            results = obj_data['results']
            
            for result in results:
                # Get segment time range
                start_time = result.get('segment_start_seconds', result.get('timestamp_seconds', 0))
                end_time = result.get('segment_end_seconds', start_time + 2.0)
                score = result.get('score', 0.5)
                
                # Create segment key (rounded to nearest second for grouping)
                segment_key = int(start_time)
                
                if segment_key not in combined_segments:
                    combined_segments[segment_key] = {
                        'segment_start': start_time,
                        'segment_end': end_time,
                        'objects_detected': [],
                        'weighted_score': 0.0,
                        'raw_scores': [],
                        'priorities': [],
                        'details': []
                    }
                
                # Add weighted score: base_score * priority
                weighted_contribution = score * priority
                combined_segments[segment_key]['weighted_score'] += weighted_contribution
                combined_segments[segment_key]['objects_detected'].append(obj_name)
                combined_segments[segment_key]['raw_scores'].append(score)
                combined_segments[segment_key]['priorities'].append(priority)
                combined_segments[segment_key]['details'].append(result)
                
                # Update segment bounds
                combined_segments[segment_key]['segment_start'] = min(
                    combined_segments[segment_key]['segment_start'], start_time
                )
                combined_segments[segment_key]['segment_end'] = max(
                    combined_segments[segment_key]['segment_end'], end_time
                )
        
        # Convert to result format - use weighted_score directly as the score
        final_results = []
        for segment_key, segment_data in sorted(combined_segments.items()):
            # Get video info for metadata
            video = minio_storage.get_video_metadata(video_id)
            if not video:
                continue
            
            # Create caption showing detected objects
            objects_str = ", ".join(segment_data['objects_detected'])
            priority_str = ", ".join([f"{obj}(P{segment_data['priorities'][i]})" 
                                     for i, obj in enumerate(segment_data['objects_detected'])])
            
            # Use first result's keyframe path (or combine if needed)
            keyframe_path = segment_data['details'][0].get('keyframe_path', '') if segment_data['details'] else ''
            
            result = {
                'segment_id': f"multi_{segment_key}_{len(final_results)}",
                'video_id': video_id,
                'video_filename': video.get('filename', ''),
                'video_title': video.get('title', ''),
                'frame_number': int(segment_data['segment_start'] * 30),  # Approximate
                'timestamp_seconds': segment_data['segment_start'],
                'segment_start_seconds': segment_data['segment_start'],
                'segment_end_seconds': segment_data['segment_end'],
                'keyframe_path': keyframe_path,
                'caption': f"Objects: {objects_str} | Priorities: {priority_str}",
                'score': segment_data['weighted_score'],  # Use weighted_score directly as score
                'objects_detected': segment_data['objects_detected'],
                'object_priorities': segment_data['priorities'],
                'raw_scores': segment_data['raw_scores'],
                'is_on_demand': True
            }
            final_results.append(result)
        
        # Sort by score (weighted_score) descending
        final_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Take top_k
        final_results = final_results[:request.top_k]
        
        # Create query string for response
        query_str = " + ".join([f"{obj.object}(P{obj.priority})" for obj in request.objects])
        
        logger.info(f"Multi-object search completed: {len(final_results)} combined results")
        
        return SearchResponse(
            query=query_str,
            results=final_results,
            total_results=len(final_results),
            search_type="multi_object_priority"
        )
        
    except Exception as e:
        logger.error(f"Multi-object priority search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Multi-object search failed: {str(e)}")


class SummarizeSegmentsRequest(BaseModel):
    segments: List[Dict]
    video_id: str


@app.post("/summarize-segments/")
async def summarize_segments_with_blip2(request: SummarizeSegmentsRequest):
    """
    Summarize video segments using BLIP-2 and return summaries for clustering.
    """
    try:
        from backend.blip2_search import get_blip2_search_engine
        from backend.video_chunker import extract_keyframe_from_window
        import tempfile
        import cv2
        import torch
        
        blip2_engine = get_blip2_search_engine()
        video_id = request.video_id
        segments = request.segments
        
        # Get video metadata
        video = minio_storage.get_video_metadata(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Download video temporarily
        video_obj = minio_client.get_object(bucket_name, f"videos/{video['filename']}")
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            tmp_file.write(video_obj.read())
            tmp_video_path = tmp_file.name
        
        summarized_segments = []
        
        for seg in segments:
            try:
                start_time = seg.get('segment_start_seconds', seg.get('timestamp_seconds', 0))
                end_time = seg.get('segment_end_seconds', start_time + 2.0)
                
                # Extract keyframe from segment
                keyframe = extract_keyframe_from_window(tmp_video_path, start_time, end_time)
                
                # Generate summary with BLIP-2
                # Use InstructBLIP to describe the image
                question = "Describe what is happening in this image in detail."
                
                inputs = blip2_engine.blip2_processor(
                    images=keyframe,
                    text=question,
                    return_tensors="pt"
                ).to(blip2_engine.blip2_model.device)
                
                with torch.no_grad():
                    output = blip2_engine.blip2_model.generate(
                        **inputs,
                        max_new_tokens=50,
                        do_sample=False,
                        temperature=0.0
                    )
                
                summary = blip2_engine.blip2_processor.decode(output[0], skip_special_tokens=True)
                if question in summary:
                    summary = summary.split(question)[-1].strip()
                
                # Add summary to segment
                seg_copy = seg.copy()
                seg_copy['blip2_summary'] = summary
                summarized_segments.append(seg_copy)
                
            except Exception as e:
                logger.error(f"Failed to summarize segment: {e}")
                # Add segment without summary
                seg_copy = seg.copy()
                seg_copy['blip2_summary'] = "Summary unavailable"
                summarized_segments.append(seg_copy)
        
        # Cleanup
        try:
            os.remove(tmp_video_path)
        except:
            pass
        
        return {
            "summarized_segments": summarized_segments,
            "total_segments": len(summarized_segments)
        }
        
    except Exception as e:
        logger.error(f"Segment summarization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")


@app.post("/analyze-video-auto/{video_id}")
async def analyze_video_automatically(
    video_id: str,
    segment_duration: float = Query(5.0, description="Duration of each segment in seconds"),
    overlap: float = Query(1.0, description="Overlap between consecutive segments in seconds")
):
    """
    Automatically analyze entire video: extract segments, generate BLIP-2 summaries, and cluster.
    No keywords required - fully automatic analysis.
    """
    try:
        from backend.blip2_search import get_blip2_search_engine
        from backend.video_chunker import VideoChunker, extract_keyframe_from_window
        from sentence_transformers import SentenceTransformer
        from sklearn.cluster import KMeans
        from sklearn.manifold import TSNE
        import tempfile
        import torch
        import numpy as np
        
        logger.info(f"Auto-analyzing video {video_id} with segment_duration={segment_duration}s")
        
        # Get video metadata
        video = minio_storage.get_video_metadata(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        video_duration = video.get('duration_seconds', 100)
        
        # Download video temporarily
        video_obj = minio_client.get_object(bucket_name, f"videos/{video['filename']}")
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            tmp_file.write(video_obj.read())
            tmp_video_path = tmp_file.name
        
        try:
            # Initialize chunker
            chunker = VideoChunker(tmp_video_path)
            
            # Generate temporal windows
            windows = chunker.get_temporal_windows(
                clip_duration=segment_duration,
                overlap=overlap
            )
            
            logger.info(f"Generated {len(windows)} temporal windows")
            
            # Initialize BLIP-2
            blip2_engine = get_blip2_search_engine()
            
            # Process each window: extract keyframe and generate summary
            segments_with_summaries = []
            
            for idx, window in enumerate(windows):
                try:
                    # Extract keyframe from middle of window
                    mid_time = (window.start_time + window.end_time) / 2.0
                    keyframe = extract_keyframe_from_window(tmp_video_path, window.start_time, window.end_time)
                    
                    # Generate BLIP-2 summary
                    question = "Describe what is happening in this image in detail."
                    
                    inputs = blip2_engine.blip2_processor(
                        images=keyframe,
                        text=question,
                        return_tensors="pt"
                    ).to(blip2_engine.blip2_model.device)
                    
                    with torch.no_grad():
                        output = blip2_engine.blip2_model.generate(
                            **inputs,
                            max_new_tokens=50,
                            do_sample=False,
                            temperature=0.0
                        )
                    
                    summary = blip2_engine.blip2_processor.decode(output[0], skip_special_tokens=True)
                    if question in summary:
                        summary = summary.split(question)[-1].strip()
                    
                    segments_with_summaries.append({
                        'segment_id': f"auto_{idx}",
                        'segment_start_seconds': window.start_time,
                        'segment_end_seconds': window.end_time,
                        'timestamp_seconds': mid_time,
                        'duration': window.end_time - window.start_time,
                        'blip2_summary': summary,
                        'window_id': window.window_id
                    })
                    
                    if (idx + 1) % 10 == 0:
                        logger.info(f"Processed {idx + 1}/{len(windows)} segments")
                        
                except Exception as e:
                    logger.error(f"Failed to process window {window}: {e}")
                    continue
            
            chunker.release()
            
            if not segments_with_summaries:
                raise HTTPException(status_code=500, detail="No segments could be processed")
            
            logger.info(f"Generated {len(segments_with_summaries)} summaries, now clustering...")
            
            # Cluster based on summaries
            summaries = [s['blip2_summary'] for s in segments_with_summaries]
            
            # Generate embeddings
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embeddings = model.encode(summaries)
            
            # Automatically determine optimal number of clusters
            num_segments = len(segments_with_summaries)
            
            if num_segments < 2:
                actual_n_clusters = 1
                cluster_labels = np.array([0] * num_segments)
            elif num_segments < 4:
                actual_n_clusters = 2
                kmeans = KMeans(n_clusters=actual_n_clusters, random_state=42, n_init=10)
                cluster_labels = kmeans.fit_predict(embeddings)
            else:
                # Try different numbers of clusters and pick the best using silhouette score
                from sklearn.metrics import silhouette_score
                
                # Determine reasonable range: between 2 and sqrt(n/2) or max 15
                max_clusters = min(15, max(2, int(np.sqrt(num_segments / 2))))
                min_clusters = 2
                
                best_score = -1
                best_n_clusters = 2
                best_labels = None
                
                logger.info(f"Testing cluster numbers from {min_clusters} to {max_clusters} for {num_segments} segments")
                
                for n in range(min_clusters, max_clusters + 1):
                    try:
                        kmeans = KMeans(n_clusters=n, random_state=42, n_init=10)
                        labels = kmeans.fit_predict(embeddings)
                        score = silhouette_score(embeddings, labels)
                        
                        if score > best_score:
                            best_score = score
                            best_n_clusters = n
                            best_labels = labels
                            
                        logger.info(f"  n_clusters={n}: silhouette_score={score:.3f}")
                    except Exception as e:
                        logger.warning(f"Failed to compute silhouette for n_clusters={n}: {e}")
                        continue
                
                actual_n_clusters = best_n_clusters
                cluster_labels = best_labels
                logger.info(f"Selected {actual_n_clusters} clusters with silhouette score {best_score:.3f}")
            
            # Add cluster IDs to segments
            for i, seg in enumerate(segments_with_summaries):
                seg['cluster_id'] = int(cluster_labels[i])
            
            # Calculate cluster statistics and keywords using KeyBERT
            cluster_stats = {}
            
            # Initialize KeyBERT for keyword extraction
            try:
                from keybert import KeyBERT
                # Use the same sentence transformer model we use for clustering
                kw_model = KeyBERT(model='all-MiniLM-L6-v2')
                logger.info("KeyBERT initialized for keyword extraction")
            except ImportError:
                logger.warning("KeyBERT not available, falling back to simple extraction")
                kw_model = None
            
            for cluster_id in range(actual_n_clusters):
                cluster_segs = [s for s in segments_with_summaries if s['cluster_id'] == cluster_id]
                if cluster_segs:
                    cluster_summaries = [s['blip2_summary'] for s in cluster_segs]
                    
                    # Combine all summaries for this cluster
                    combined_text = ' '.join(cluster_summaries)
                    
                    # Extract keywords using KeyBERT if available
                    if kw_model and combined_text.strip():
                        try:
                            # Extract keywords: get top 5 keywords with scores
                            # Use keyphrase_ngram_range to get both single words and phrases
                            keywords_with_scores = kw_model.extract_keywords(
                                combined_text,
                                keyphrase_ngram_range=(1, 2),  # Single words and 2-word phrases
                                stop_words='english',
                                top_n=5,
                                use_mmr=True,  # Use Maximal Marginal Relevance for diversity
                                diversity=0.5
                            )
                            # Extract just the keywords (first element of each tuple)
                            keywords = [kw[0] for kw in keywords_with_scores if kw[1] > 0.1]  # Filter by score threshold
                            
                            logger.info(f"Cluster {cluster_id}: KeyBERT extracted {len(keywords)} keywords: {keywords}")
                        except Exception as e:
                            logger.warning(f"KeyBERT extraction failed for cluster {cluster_id}: {e}, using fallback")
                            keywords = []
                    else:
                        # Fallback: simple extraction if KeyBERT not available
                        from collections import Counter
                        import re
                        
                        all_text = combined_text.lower()
                        words = re.findall(r'\b[a-z]{3,}\b', all_text)
                        word_counts = Counter(words)
                        
                        stop_words = {
                            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 
                            'is', 'are', 'was', 'were', 'this', 'that', 'these', 'those', 'there', 'their', 
                            'they', 'what', 'which', 'where', 'when', 'who', 'how', 'has', 'have', 'had',
                            'can', 'could', 'would', 'should', 'may', 'might', 'must', 'will', 'shall',
                            'from', 'into', 'onto', 'upon', 'over', 'under', 'above', 'below', 'between',
                            'during', 'while', 'before', 'after', 'through', 'across', 'around', 'about',
                            'being', 'been', 'does', 'did', 'done', 'doing', 'get', 'got', 'gets',
                            'image', 'picture', 'photo', 'showing', 'shows', 'shown', 'see', 'seen', 'saw'
                        }
                        
                        filtered_words = [(word, count) for word, count in word_counts.most_common(20) 
                                         if word not in stop_words and len(word) >= 3]
                        keywords = [word for word, count in filtered_words[:5]]
                    
                    # Get representative summary
                    cluster_stats[int(cluster_id)] = {
                        'count': len(cluster_segs),
                        'keywords': keywords if keywords else [],  # Ensure it's a list
                        'representative_summary': cluster_summaries[0] if cluster_summaries else ''
                    }
                    
                    logger.info(f"Cluster {cluster_id}: {len(cluster_segs)} segments, keywords: {keywords}")
            
            # Generate 2D projection for visualization
            if len(embeddings) > 1:
                tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(embeddings)-1))
                embeddings_2d = tsne.fit_transform(embeddings)
                
                for i, seg in enumerate(segments_with_summaries):
                    seg['x'] = float(embeddings_2d[i][0])
                    seg['y'] = float(embeddings_2d[i][1])
            else:
                for seg in segments_with_summaries:
                    seg['x'] = 0.0
                    seg['y'] = 0.0
            
            logger.info(f"Auto-analysis complete: {len(segments_with_summaries)} segments in {actual_n_clusters} clusters")
            
            return {
                "segments": segments_with_summaries,
                "cluster_statistics": cluster_stats,
                "n_clusters": actual_n_clusters,
                "video_duration": video_duration,
                "total_segments": len(segments_with_summaries)
            }
            
        finally:
            # Cleanup
            try:
                os.remove(tmp_video_path)
            except:
                pass
        
    except Exception as e:
        logger.error(f"Auto-analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Auto-analysis failed: {str(e)}")


@app.post("/cluster-segments/")
async def cluster_segments_by_summary(request: dict):
    """
    Cluster segments based on BLIP-2 summaries using sentence embeddings.
    """
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.cluster import KMeans
        import numpy as np
        
        segments = request.get('segments', [])
        n_clusters = request.get('n_clusters', 3)
        
        if not segments:
            raise HTTPException(status_code=400, detail="No segments provided")
        
        # Extract summaries
        summaries = [seg.get('blip2_summary', '') for seg in segments]
        
        # Generate embeddings
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode(summaries)
        
        # Cluster
        if len(segments) < n_clusters:
            n_clusters = len(segments)
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings)
        
        # Add cluster labels to segments
        clustered_segments = []
        for i, seg in enumerate(segments):
            seg_copy = seg.copy()
            seg_copy['cluster_id'] = int(cluster_labels[i])
            clustered_segments.append(seg_copy)
        
        # Calculate cluster statistics
        cluster_stats = {}
        for cluster_id in range(n_clusters):
            cluster_segs = [s for s in clustered_segments if s.get('cluster_id') == cluster_id]
            if cluster_segs:
                cluster_summaries = [s.get('blip2_summary', '') for s in cluster_segs]
                # Find most common words in cluster summaries
                all_words = ' '.join(cluster_summaries).lower().split()
                from collections import Counter
                word_counts = Counter(all_words)
                # Filter out common stop words and short words
                stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'was', 'were', 'this', 'that', 'these', 'those'}
                common_words = [word for word, count in word_counts.most_common(10) 
                              if len(word) > 3 and word not in stop_words]
                
                cluster_stats[int(cluster_id)] = {
                    'count': len(cluster_segs),
                    'keywords': common_words[:5] if common_words else ['no', 'keywords']
                }
        
        return {
            "clustered_segments": clustered_segments,
            "cluster_statistics": cluster_stats,
            "n_clusters": n_clusters
        }
        
    except Exception as e:
        logger.error(f"Clustering failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


@app.get("/video/{video_id}/file")
@app.head("/video/{video_id}/file")
async def get_video_file_simple(video_id: str, request: Request):
    """Download video from MinIO and serve as static file - simplest approach."""
    try:
        # Get video metadata
        video = minio_storage.get_video_metadata(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Download video from MinIO to temp file
        temp_path = f"/tmp/video_{video_id}.mp4"
        video_path = f"videos/{video['filename']}"
        
        # For HEAD requests, get file info without downloading
        if request.method == "HEAD":
            try:
                stat = minio_client.stat_object(bucket_name, video_path)
                return Response(
                    headers={
                        "Content-Length": str(stat.size),
                        "Content-Type": "video/mp4",
                        "Accept-Ranges": "bytes",
                        "Access-Control-Allow-Origin": "*"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to get video stats from MinIO: {e}")
                raise HTTPException(status_code=404, detail=f"Video not found: {str(e)}")
        
        # For GET requests, download and serve the file
        try:
            minio_client.fget_object(bucket_name, video_path, temp_path)
        except Exception as e:
            logger.error(f"Failed to download video from MinIO: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to access video: {str(e)}")
        
        # Serve as static file
        return FileResponse(
            temp_path,
            media_type="video/mp4",
            filename=video['filename'],
            headers={
                "Access-Control-Allow-Origin": "*",
                "Accept-Ranges": "bytes"
            }
        )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving video file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to serve video: {str(e)}")


@app.get("/image/{path:path}")
async def get_image(path: str):
    """Serve image files (keyframes) from MinIO."""
    try:
        
        # Security: ensure path is within allowed directories or contains frames
        allowed_dirs = ["data/frames", "frames", "artifacts", "blip2"]
        if not any(path.startswith(d) for d in allowed_dirs) and "frames/" not in path and "query_extracted/" not in path and "blip2/" not in path:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Try to get image from MinIO first
        try:
            # Convert various path formats to MinIO object path
            # Handle temporary paths like "/var/folders/.../frames/demo/demo/frame_000000_t0.00s.jpg"
            # and convert to "frames/demo/frame_000000_t0.00s.jpg"
            if "frames/" in path:
                # Extract the frames/... part from the path
                frames_index = path.find("frames/")
                minio_path = path[frames_index:]
                # Remove duplicate folder names if present (e.g., /video_name/video_name/ -> /video_name/)
                # Extract video name from path and fix duplicates
                path_parts = minio_path.split('/')
                if len(path_parts) >= 3 and path_parts[1] == path_parts[2]:
                    # Remove duplicate folder: frames/video_name/video_name/file.jpg -> frames/video_name/file.jpg
                    minio_path = '/'.join([path_parts[0]] + path_parts[2:])
            elif "blip2/" in path:
                # Legacy support for old BLIP2 paths like "blip2/military.mp4/0"
                # These should now be proper MinIO paths, but keep this for backward compatibility
                blip2_parts = path.split('/')
                if len(blip2_parts) >= 3:
                    video_filename = blip2_parts[1]  # e.g., "military.mp4"
                    frame_number = int(blip2_parts[2])  # e.g., 0
                    video_stem = Path(video_filename).stem
                    # Try to find the actual BLIP2 frame in MinIO
                    # Look for frames in blip2_extracted directory
                    minio_path = f"frames/{video_stem}/blip2_extracted/frame_{frame_number:06d}_t*_blip2.jpg"
                    # For now, use a simple fallback format
                    minio_path = f"frames/{video_stem}/blip2_extracted/frame_{frame_number:06d}.jpg"
                else:
                    raise HTTPException(status_code=400, detail="Invalid BLIP2 path format")
            else:
                # Convert local path to MinIO object path
                # e.g., "data/frames/demo/frame_000000_t0.00s.jpg" -> "frames/demo/frame_000000_t0.00s.jpg"
                minio_path = path.replace("data/", "")
            
            # Get image from MinIO
            image_data = minio_client.get_object(bucket_name, minio_path).read()
            
            # Determine content type based on file extension
            if path.endswith('.jpg') or path.endswith('.jpeg'):
                content_type = "image/jpeg"
            elif path.endswith('.png'):
                content_type = "image/png"
            else:
                content_type = "image/jpeg"  # default
            
            return Response(content=image_data, media_type=content_type)
            
        except S3Error as e:
            # If not found in MinIO, try local file as fallback
            if os.path.exists(path):
                return FileResponse(path)
            else:
                raise HTTPException(status_code=404, detail=f"Image not found in MinIO or locally: {path}")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to serve image: {str(e)}")


@app.post("/upload-video/")
async def upload_video(file: UploadFile = File(...)):
    """Endpoint to upload video to MinIO with video format validation."""
    try:
        # Check file extension - accept common video formats
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.mpeg', '.mpg', '.m4v')
        if not file.filename.lower().endswith(video_extensions):
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file extension. Supported video formats: {', '.join(video_extensions)}"
            )
        
        # Save uploaded file temporarily (same as legacy code)
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # Validate that it's actually a video file
        if not validate_video_format(temp_path, file.filename):
            os.remove(temp_path)
            raise HTTPException(
                status_code=400,
                detail="Invalid video format. The file does not appear to be a valid video file."
            )

        # Upload to MinIO (use video/mp4 as default like legacy code)
        minio_client.fput_object(bucket_name, f"videos/{file.filename}", temp_path, content_type="video/mp4")
        
        # Clean up temp file
        os.remove(temp_path)
        
        # Get extension for response
        ext = file.filename.lower().split('.')[-1]
        
        return {
            "message": f"Successfully uploaded {file.filename}",
            "filename": file.filename,
            "format": f"{ext.upper()} (validated)"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/process-video/")
async def process_video(request: dict):
    """Process video and store complete metadata."""
    try:
        filename = request.get("filename")
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        logger.info(f"Storing video metadata: {filename}")
        
        # Get MinIO object info without downloading
        video_path = f"videos/{filename}"
        
        try:
            # Get object stats from MinIO (no download needed)
            obj_stat = minio_client.stat_object(bucket_name, video_path)
            file_size = obj_stat.size
            
            # Check if video already exists
            existing_videos = minio_storage.list_videos()
            existing_video = next((v for v in existing_videos if v.get('filename') == filename), None)
            
            if existing_video:
                video_id = existing_video['id']
                logger.info(f"Video already exists with ID: {video_id}")
            else:
                # Download video temporarily to extract complete metadata
                import tempfile
                import cv2
                from pathlib import Path
                
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                    minio_client.fget_object(bucket_name, video_path, temp_file.name)
                    temp_video_path = temp_file.name
                
                try:
                    # Extract complete video metadata
                    cap = cv2.VideoCapture(temp_video_path)
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    duration = frame_count / fps if fps > 0 else 0
                    cap.release()
                    
                    # Create video record with complete metadata
                    video_data = {
                        "filename": filename,
                        "title": Path(filename).stem.replace("_", " ").title(),
                        "duration_seconds": duration,
                        "fps": fps,
                        "width": width,
                        "height": height,
                        "file_size_bytes": file_size
                    }
                    
                    video_id = minio_storage.store_video_metadata(video_data)
                    logger.info(f"Created new video record with ID: {video_id}")
                    
                finally:
                    # Clean up temp file
                    import os
                    if os.path.exists(temp_video_path):
                        os.unlink(temp_video_path)
            
            return {
                "message": f"Video {filename} uploaded successfully!",
                "video_id": video_id,
                "filename": filename,
                "file_size": file_size,
                "status": "ready_for_search",
                "note": "Video stored with complete metadata - ready for search"
            }
            
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to process video: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        blip2_engine = get_blip2_search_engine()
        action_engine = get_action_search_engine()
        return {
            "status": "healthy",
            "blip2_model_loaded": blip2_engine.blip2_model is not None,
            "xclip_model_loaded": action_engine.model is not None,
            "minio_storage_connected": blip2_engine.minio_storage is not None,
            "search_modes": ["object_detection", "action_detection", "two_stage"]
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }



@app.get("/check-minio-videos")
async def check_minio_videos():
    """Check which videos are actually available in MinIO."""
    try:
        # Get all videos from MinIO storage
        all_videos = minio_storage.list_videos()
        
        video_status = []
        for video in all_videos:
            try:
                # Try to get object info from MinIO
                video_path = f"videos/{video['filename']}"
                obj_stat = minio_client.stat_object(bucket_name, video_path)
                status = "available"
                minio_size = obj_stat.size
            except Exception as e:
                status = f"missing: {str(e)}"
                minio_size = 0
            
            video_status.append({
                "id": video['id'],
                "filename": video['filename'],
                "db_size": video.get('file_size_bytes', 0),
                "minio_size": minio_size,
                "status": status,
                "minio_path": f"videos/{video['filename']}"
            })
        
        return {"videos": video_status}
        
    except Exception as e:
        logger.error(f"Error checking MinIO videos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check videos: {str(e)}")


def main():
    """Main entry point for running the server."""
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload to avoid MinIO directory issues
        log_level="info"
    )

if __name__ == "__main__":
    main()