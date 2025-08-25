#!/usr/bin/env python3
"""FastAPI application for SceneLens search API."""

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
import uvicorn
from minio.error import S3Error

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.search import get_search_engine
from minio import Minio

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
    keyframe_path: str
    caption: Optional[str]
    score: float


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
        "message": "SceneLens Search API",
        "version": "1.0.0",
        "endpoints": {
            "search": "/search?q=<query>&top_k=<number>",
            "search_caption": "/search/caption?q=<query>&top_k=<number>",
            "database_info": "/database",
            "upload_video": "/upload-video/",
            "health": "/health",
            "docs": "/docs",
        }
    }


@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query text"),
    top_k: int = Query(10, description="Number of results to return", ge=1, le=100)
):
    """Semantic search endpoint using CLIP embeddings."""
    try:
        search_engine = get_search_engine()
        results = search_engine.search(q, top_k)
        
        return SearchResponse(
            query=q,
            results=[SearchResult(**result) for result in results],
            total_results=len(results),
            search_type="semantic"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/search/caption", response_model=SearchResponse)
async def search_caption(
    q: str = Query(..., description="Search query text"),
    top_k: int = Query(10, description="Number of results to return", ge=1, le=100)
):
    """Text search endpoint using caption matching."""
    try:
        search_engine = get_search_engine()
        results = search_engine.search_by_caption(q, top_k)
        
        return SearchResponse(
            query=q,
            results=[SearchResult(**result) for result in results],
            total_results=len(results),
            search_type="caption"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/image/{path:path}")
async def get_image(path: str):
    """Serve image files (keyframes) from MinIO."""
    try:
        
        # Security: ensure path is within allowed directories or contains frames
        allowed_dirs = ["data/frames", "frames", "artifacts"]
        if not any(path.startswith(d) for d in allowed_dirs) and "frames/" not in path:
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
        return {"message": f"Uploaded {file.filename} to MinIO."}
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    search_engine = get_search_engine()
    return {
        "status": "healthy",
        "faiss_loaded": search_engine.index is not None,
        "text_encoder_loaded": search_engine.text_encoder is not None,
        "total_vectors": search_engine.index.ntotal if search_engine.index else 0,
    }


@app.get("/database")
async def get_database_info():
    """Get PostgreSQL database information and statistics."""
    try:
        from pipeline.database import get_db_session
        from pipeline.models import Video, Segment, SearchLog
        
        db = get_db_session()
        
        # Get counts
        video_count = db.query(Video).count()
        segment_count = db.query(Segment).count()
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
        
        # Get recent segments
        recent_segments = db.query(Segment).order_by(Segment.created_at.desc()).limit(5).all()
        segments_data = []
        for segment in recent_segments:
            segments_data.append({
                "id": str(segment.id),
                "video_id": str(segment.video_id),
                "frame_number": segment.frame_number,
                "timestamp_seconds": segment.timestamp_seconds,
                "keyframe_path": segment.keyframe_path,
                "caption": segment.caption,
                "created_at": segment.created_at.isoformat()
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
                "total_segments": segment_count,
                "total_search_logs": log_count
            },
            "recent_videos": videos_data,
            "recent_segments": segments_data,
            "recent_search_logs": logs_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

def upload_image_to_minio(file_path, object_name):
    """Uploads an image to MinIO."""
    try:
        minio_client.fput_object(
            bucket_name, object_name, file_path
        )
        print(f"Image {object_name} uploaded successfully.")
    except Exception as e:
        print(f"Error uploading image: {e}")


def get_image_from_minio(object_name, download_path):
    """Retrieves an image from MinIO and saves it to the specified path."""
    try:
        minio_client.fget_object(
            bucket_name, object_name, download_path
        )
        print(f"Image {object_name} downloaded successfully to {download_path}.")
    except Exception as e:
        print(f"Error downloading image: {e}")

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