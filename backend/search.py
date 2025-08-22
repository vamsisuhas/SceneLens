"""Search functionality for SceneLens."""

import json
import time
from pathlib import Path
from typing import List, Optional
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.database import get_db_session
from pipeline.models import Segment, Video, SearchLog


class SearchEngine:
    """Semantic search engine for video frames."""
    
    def __init__(self, faiss_index_path="faiss/keyframes.index", 
                 metadata_path="faiss/metadata.json",
                 model_name="clip-ViT-B-32"):
        """Initialize the search engine."""
        self.faiss_index_path = Path(faiss_index_path)
        self.metadata_path = Path(metadata_path)
        
        # Load FAISS index
        if self.faiss_index_path.exists():
            self.index = faiss.read_index(str(self.faiss_index_path))
            print(f"Loaded FAISS index with {self.index.ntotal} vectors")
        else:
            self.index = None
            print(f"FAISS index not found: {self.faiss_index_path}")
        
        # Load metadata
        if self.metadata_path.exists():
            with open(self.metadata_path, "r") as f:
                self.metadata = json.load(f)
            print(f"Loaded metadata for {len(self.metadata['index_to_path'])} items")
        else:
            self.metadata = {"index_to_path": []}
            print(f" Metadata not found: {self.metadata_path}")
        
        # Load text encoder
        try:
            self.text_encoder = SentenceTransformer(model_name)
            print(f"Loaded text encoder: {model_name}")
        except Exception as e:
            print(f"Failed to load text encoder: {e}")
            self.text_encoder = None
    
    def search(self, query: str, top_k: int = 10) -> List[dict]:
        """Search for frames matching the text query."""
        start_time = time.time()
        
        if not self.index or not self.text_encoder:
            return []
        
        try:
            # Encode query text
            query_embedding = self.text_encoder.encode(query, convert_to_numpy=True)
            query_embedding = query_embedding.astype(np.float32).reshape(1, -1)
            
            # Search FAISS index
            scores, indices = self.index.search(query_embedding, top_k)
            
            # Get database session
            db = get_db_session()
            results = []
            
            try:
                for score, idx in zip(scores[0], indices[0]):
                    if idx >= 0 and idx < len(self.metadata["index_to_path"]):
                        image_path = self.metadata["index_to_path"][idx]
                        
                        # Get segment info from database
                        segment = db.query(Segment).filter(
                            Segment.keyframe_path == image_path
                        ).first()
                        
                        if segment:
                            # Get video info
                            video = db.query(Video).filter(Video.id == segment.video_id).first()
                            
                            result = {
                                "segment_id": str(segment.id),
                                "video_id": str(segment.video_id),
                                "video_filename": video.filename if video else None,
                                "video_title": video.title if video else None,
                                "frame_number": segment.frame_number,
                                "timestamp_seconds": segment.timestamp_seconds,
                                "keyframe_path": segment.keyframe_path,
                                "caption": segment.caption,
                                "score": float(score),
                            }
                            results.append(result)
                
                # Log search
                response_time_ms = int((time.time() - start_time) * 1000)
                search_log = SearchLog(
                    query=query,
                    results_count=len(results),
                    response_time_ms=response_time_ms
                )
                db.add(search_log)
                db.commit()
                
            finally:
                db.close()
            
            return results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def search_by_caption(self, query: str, top_k: int = 10) -> List[dict]:
        """Search for frames by caption text (SQL text search)."""
        db = get_db_session()
        results = []
        
        try:
            # Simple text search in captions
            segments = db.query(Segment).join(Video).filter(
                Segment.caption.ilike(f"%{query}%")
            ).limit(top_k).all()
            
            for segment in segments:
                result = {
                    "segment_id": str(segment.id),
                    "video_id": str(segment.video_id),
                    "video_filename": segment.video.filename,
                    "video_title": segment.video.title,
                    "frame_number": segment.frame_number,
                    "timestamp_seconds": segment.timestamp_seconds,
                    "keyframe_path": segment.keyframe_path,
                    "caption": segment.caption,
                    "score": 1.0,  # Text match doesn't have similarity score
                }
                results.append(result)
        
        finally:
            db.close()
        
        return results


# Global search engine instance
search_engine = None


def get_search_engine():
    """Get or create search engine instance."""
    global search_engine
    if search_engine is None:
        search_engine = SearchEngine()
    return search_engine
