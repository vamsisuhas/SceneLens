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

from backend.search import get_search_engine
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

# Ensure bucket exists
bucket_name = "scenelens"
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)


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
        "message": "SceneLens On-Demand Video Search API",
        "version": "1.0.0",
        "endpoints": {
            "search_on_demand": "/search/on-demand?q=<query>&top_k=<number>&frame_interval=<seconds>",
            "search_specific_video": "/search/video/{video_id}?q=<query>&top_k=<number>",
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
    """On-demand search endpoint using dynamic frame extraction."""
    try:
        search_engine = get_search_engine()
        results = search_engine.search_on_demand(
            q, top_k, frame_interval, use_existing_first
        )
        
        return SearchResponse(
            query=q,
            results=[SearchResult(**result) for result in results],
            total_results=len(results),
            search_type="on_demand"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"On-demand search failed: {str(e)}")


@app.get("/search/video/{video_id}", response_model=SearchResponse)
async def search_specific_video(
    video_id: str,
    q: str = Query(..., description="Search query text"),
    top_k: int = Query(10, description="Number of results to return", ge=1, le=50),
    frame_interval: float = Query(0.1, description="Frame extraction interval in seconds", ge=0.1, le=2.0)
):
    """Search within a specific video only."""
    try:
        search_engine = get_search_engine()
        
        # Perform search with video_id filter
        results = search_engine.search_specific_video(
            query=q,
            video_id=video_id,
            top_k=top_k,
            frame_interval=frame_interval
        )
        
        return SearchResponse(
            query=q,
            results=results,
            total_results=len(results),
            search_type="video_specific"
        )
    except Exception as e:
        logger.error(f"Video-specific search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Video search failed: {str(e)}")

@app.get("/video/{video_id}/file")
async def get_video_file(video_id: str):
    """Get video file for playback."""
    try:
        from pipeline.database import get_db_session
        from pipeline.models import Video
        from fastapi.responses import StreamingResponse
        import io
        
        db = get_db_session()
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        try:
            # Get video data from MinIO
            video_data = minio_client.get_object(bucket_name, f"videos/{video.filename}")
            video_bytes = video_data.read()
            
            # Return video as streaming response
            return StreamingResponse(
                io.BytesIO(video_bytes),
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"inline; filename={video.filename}",
                    "Accept-Ranges": "bytes"
                }
            )
                
        except Exception as e:
            logger.error(f"Error serving video file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to serve video: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Error getting video file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get video file: {str(e)}")
    finally:
        db.close()


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
    """Ultra-lightweight video processing - just store basic metadata."""
    try:
        filename = request.get("filename")
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        # Import database functions
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from pipeline.database import get_db_session
        from pipeline.models import Video
        from datetime import datetime
        
        logger.info(f"Storing video metadata: {filename}")
        
        # Get MinIO object info without downloading
        video_path = f"videos/{filename}"
        
        try:
            # Get object stats from MinIO (no download needed)
            obj_stat = minio_client.stat_object(bucket_name, video_path)
            file_size = obj_stat.size
            
            # Store in database with minimal metadata
            db = get_db_session()
            
            # Check if video already exists
            existing_video = db.query(Video).filter(Video.filename == filename).first()
            if existing_video:
                video_id = existing_video.id
                logger.info(f"Video already exists with ID: {video_id}")
            else:
                # Create new video record with basic info
                video = Video(
                    filename=filename,
                    title=filename.split('.')[0],  # Use filename without extension as title
                    duration_seconds=0,  # Will be determined during search
                    fps=0,  # Will be determined during search
                    width=0,  # Will be determined during search
                    height=0,  # Will be determined during search
                    file_size_bytes=file_size,
                    created_at=datetime.utcnow()
                )
                
                db.add(video)
                db.commit()
                video_id = video.id
                logger.info(f"Created new video record with ID: {video_id}")
            
            db.close()
            
            return {
                "message": f"Video {filename} uploaded successfully!",
                "video_id": video_id,
                "filename": filename,
                "file_size": file_size,
                "status": "ready_for_search",
                "note": "Video stored - processing will happen on first search"
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
    search_engine = get_search_engine()
    return {
        "status": "healthy",
        "text_encoder_loaded": search_engine.text_encoder is not None,
        "on_demand_extractor_loaded": search_engine.on_demand_extractor is not None,
        "search_type": "prompt_driven"
    }

@app.get("/database")
async def get_database_info():
    """Get PostgreSQL database information and statistics."""
    try:
        from pipeline.database import get_db_session
        from pipeline.models import Video, SearchLog
        
        db = get_db_session()
        
        # Get counts
        video_count = db.query(Video).count()
        log_count = db.query(SearchLog).count()
        
        # Get recent videos
        recent_videos = db.query(Video).order_by(Video.created_at.desc()).limit(5).all()
        videos_data = []
        for video in recent_videos:
            videos_data.append({
                "id": str(video.id),
                "filename": video.filename,
                "title": video.title,
                "duration_seconds": video.duration_seconds,
                "fps": video.fps,
                "resolution": f"{video.width}x{video.height}",
                "file_size_bytes": video.file_size_bytes,
                "created_at": video.created_at.isoformat()
            })
        
        # Get recent search logs
        recent_logs = db.query(SearchLog).order_by(SearchLog.created_at.desc()).limit(5).all()
        logs_data = []
        for log in recent_logs:
            logs_data.append({
                "id": str(log.id),
                "query": log.query,
                "results_count": log.results_count,
                "response_time_ms": log.response_time_ms,
                "created_at": log.created_at.isoformat()
            })
        
        db.close()
        
        return {
            "database": "PostgreSQL",
            "statistics": {
                "total_videos": video_count,
                "total_search_logs": log_count
            },
            "recent_videos": videos_data,
            "recent_search_logs": logs_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@app.get("/check-minio-videos")
async def check_minio_videos():
    """Check which videos are actually available in MinIO."""
    try:
        from pipeline.database import get_db_session
        from pipeline.models import Video
        
        db = get_db_session()
        all_videos = db.query(Video).all()
        
        video_status = []
        for video in all_videos:
            try:
                # Try to get object info from MinIO
                video_path = f"videos/{video.filename}"
                obj_stat = minio_client.stat_object(bucket_name, video_path)
                status = "available"
                minio_size = obj_stat.size
            except Exception as e:
                status = f"missing: {str(e)}"
                minio_size = 0
            
            video_status.append({
                "id": str(video.id),
                "filename": video.filename,
                "db_size": video.file_size_bytes,
                "minio_size": minio_size,
                "status": status,
                "minio_path": f"videos/{video.filename}"
            })
        
        db.close()
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
        log_level="info"
    )

if __name__ == "__main__":
    main()