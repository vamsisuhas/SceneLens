#!/usr/bin/env python3
"""FastAPI application for SceneLens search API."""

import os
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
import uvicorn
from minio.error import S3Error

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.blip2_search import get_blip2_search_engine
from pipeline.minio_storage import MinIOStorage
from minio import Minio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MinIO client
minio_client = Minio(
    "localhost:9000",
    access_key="scenelens",
    secret_key="scenelens_dev123",
    secure=False
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


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SceneLens BLIP-2 Video Search API - Enhanced Accuracy",
        "version": "2.0.0",
        "search_engine": "BLIP-2 (Vision-Language Model)",
        "endpoints": {
            "search_on_demand": "/search/on-demand?q=<query>&top_k=<number>&frame_interval=<seconds> (BLIP-2)",
            "search_specific_video": "/search/video/{video_id}?q=<query>&top_k=<number> (BLIP-2)",
            "legacy_blip2_search": "/search/blip2/{video_id}?q=<query>&top_k=<number>&frame_interval=<seconds>",
            "get_video_file": "/video/{video_id}/file",
            "upload_video": "/upload-video/",
            "process_video": "/process-video/",
            "check_minio_videos": "/check-minio-videos",
            "database_info": "/database",
            "health": "/health",
            "docs": "/docs",
        }
    }

@app.get("/search/on-demand", response_model=SearchResponse)
async def search_on_demand(
    q: str = Query(..., description="Search query text"),
    top_k: int = Query(10, description="Number of results to return", ge=1, le=50),
    frame_interval: float = Query(1.0, description="Frame extraction interval in seconds", ge=0.1, le=2.0),
    use_existing_first: bool = Query(True, description="Search existing keyframes first")
):
    """On-demand search endpoint using BLIP-2 for better accuracy."""
    try:
        # Use BLIP-2 search for better accuracy
        from backend.blip2_search import get_blip2_search_engine
        blip2_engine = get_blip2_search_engine()
        
        # Get all videos and search across them
        all_videos = blip2_engine.minio_storage.list_videos()
        all_results = []
        
        for video in all_videos:
            if len(all_results) >= top_k:
                break
                
            video_results = blip2_engine.search_video_with_blip2(
                video_id=video['id'],
                query=q,
                top_k=max((top_k - len(all_results)) * 2, 10),
                frame_interval=frame_interval
            )
            all_results.extend(video_results)
        
        # Sort by score and limit to top_k
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        all_results = all_results[:top_k]
        
        return SearchResponse(
            query=q,
            results=[SearchResult(**result) for result in all_results],
            total_results=len(all_results),
            search_type="blip2_on_demand"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BLIP-2 search failed: {str(e)}")


@app.get("/search/video/{video_id}", response_model=SearchResponse)
async def search_specific_video(
    video_id: str,
    q: str = Query(..., description="Search query text"),
    top_k: int = Query(10, description="Number of results to return", ge=1, le=50),
    frame_interval: float = Query(0.1, description="Frame extraction interval in seconds", ge=0.1, le=2.0)
):
    """Search within a specific video using BLIP-2 for better accuracy."""
    try:
        # Use BLIP-2 search for better accuracy
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
            search_type="blip2_video_specific"
        )
    except Exception as e:
        logger.error(f"BLIP-2 video search failed: {e}")
        raise HTTPException(status_code=500, detail=f"BLIP-2 video search failed: {str(e)}")


@app.get("/search/blip2/{video_id}", response_model=SearchResponse)
async def search_video_with_blip2(
    video_id: str,
    q: str = Query(..., description="Search query text"),
    top_k: int = Query(10, description="Number of results to return", ge=1, le=50),
    frame_interval: float = Query(0.5, description="Frame extraction interval in seconds", ge=0.1, le=2.0)
):
    """Search within a specific video using BLIP-2 for intelligent analysis."""
    try:
        blip2_search_engine = get_blip2_search_engine()
        
        # Perform BLIP-2 based search
        results = blip2_search_engine.search_video_with_blip2(
            query=q,
            video_id=video_id,
            top_k=top_k,
            frame_interval=frame_interval
        )
        
        return SearchResponse(
            query=q,
            results=results,
            total_results=len(results),
            search_type="blip2_based"
        )
    except Exception as e:
        logger.error(f"BLIP-2 search failed: {e}")
        raise HTTPException(status_code=500, detail=f"BLIP-2 search failed: {str(e)}")


@app.get("/video/{video_id}/file")
async def get_video_file(video_id: str):
    """Get video file for playback."""
    try:
        from fastapi.responses import StreamingResponse
        import io
        
        # Get video metadata from MinIO storage
        video = minio_storage.get_video_metadata(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        try:
            # Get video data from MinIO
            video_data = minio_client.get_object(bucket_name, f"videos/{video['filename']}")
            video_bytes = video_data.read()
            
            # Return video as streaming response
            return StreamingResponse(
                io.BytesIO(video_bytes),
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"inline; filename={video['filename']}",
                    "Accept-Ranges": "bytes"
                }
            )
                
        except Exception as e:
            logger.error(f"Error serving video file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to serve video: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Error getting video file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get video file: {str(e)}")


@app.get("/image/{path:path}")
async def get_image(path: str):
    """Serve image files (keyframes) from MinIO."""
    try:
        
        # Security: ensure path is within allowed directories or contains frames
        allowed_dirs = ["data/frames", "frames", "artifacts"]
        if not any(path.startswith(d) for d in allowed_dirs) and "frames/" not in path and "query_extracted/" not in path:
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
    """Endpoint to upload video to MinIO."""
    try:
        # Save uploaded file temporarily
        file_location = f"/tmp/{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Upload to MinIO
        minio_client.fput_object(bucket_name, f"videos/{file.filename}", file_location)
        
        # Clean up temp file
        os.remove(file_location)
        
        return {"message": f"Uploaded {file.filename} to MinIO.", "filename": file.filename}
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
        return {
            "status": "healthy",
            "blip2_model_loaded": blip2_engine.model is not None,
            "minio_storage_connected": blip2_engine.minio_storage is not None,
            "search_type": "blip2_vlm"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "search_type": "blip2_vlm"
        }

@app.get("/database")
async def get_database_info():
    """Get MinIO storage information and statistics."""
    try:
        # Get statistics from MinIO storage
        stats = minio_storage.get_database_stats()
        
        # Get recent videos
        all_videos = minio_storage.list_videos()
        recent_videos = all_videos[:5]  # Get first 5 (already sorted by date)
        videos_data = []
        for video in recent_videos:
            videos_data.append({
                "id": video['id'],
                "filename": video['filename'],
                "title": video.get('title', ''),
                "duration_seconds": video.get('duration_seconds', 0),
                "fps": video.get('fps', 0),
                "resolution": f"{video.get('width', 0)}x{video.get('height', 0)}",
                "file_size_bytes": video.get('file_size_bytes', 0),
                "created_at": video.get('created_at', '')
            })
        
        # Get recent search logs
        recent_logs = minio_storage.get_search_logs(limit=5)
        logs_data = []
        for log in recent_logs:
            logs_data.append({
                "id": log['id'],
                "query": log['query'],
                "results_count": log['results_count'],
                "response_time_ms": log['response_time_ms'],
                "created_at": log['timestamp']
            })
        
        return {
            "database": "MinIO Object Storage",
            "statistics": {
                "total_videos": stats['videos'],
                "total_search_logs": stats['search_logs'],
                "total_segments": stats['segments']
            },
            "recent_videos": videos_data,
            "recent_search_logs": logs_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage query failed: {str(e)}")


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
        reload=True,
        reload_excludes=["minio_data/*", "*.log", "*.tmp"],
        log_level="info"
    )

if __name__ == "__main__":
    main()