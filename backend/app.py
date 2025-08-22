#!/usr/bin/env python3
"""FastAPI application for SceneLens search API."""

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.search import get_search_engine


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
    """Serve image files (keyframes)."""
    try:
        # Security: ensure path is within allowed directories
        allowed_dirs = ["data/frames", "artifacts"]
        if not any(path.startswith(d) for d in allowed_dirs):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Image not found")
        
        return FileResponse(path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to serve image: {str(e)}")


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
