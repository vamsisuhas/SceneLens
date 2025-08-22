#!/usr/bin/env python3
"""Vision embedding generation using CLIP."""

import os
import sys
import argparse
import json
import numpy as np
from pathlib import Path
import torch
from PIL import Image
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.database import get_db_session
from pipeline.models import Segment


class VisionEmbedder:
    """CLIP-based vision embedder."""
    
    def __init__(self, model_name="clip-ViT-B-32"):
        """Initialize the vision embedder."""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")
        
        print("Loading CLIP model...")
        self.model = SentenceTransformer(model_name, device=self.device)
        print("Model loaded successfully")
    
    def embed_image(self, image_path):
        """Generate embedding for a single image."""
        try:
            image = Image.open(image_path).convert("RGB")
            embedding = self.model.encode(image, convert_to_numpy=True)
            return embedding
        except Exception as e:
            print(f"Error embedding image {image_path}: {e}")
            return None
    
    def embed_text(self, text):
        """Generate embedding for text."""
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            print(f"Error embedding text '{text}': {e}")
            return None


def generate_embeddings_for_frames(frames_dir, output_file="artifacts/embeddings.json"):
    """Generate vision embeddings for all frames in a directory."""
    frames_dir = Path(frames_dir)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")
    
    # Find all image files
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    image_files = []
    
    if frames_dir.is_file():
        # Single image file
        if frames_dir.suffix.lower() in image_extensions:
            image_files = [frames_dir]
        else:
            raise ValueError(f"Not an image file: {frames_dir}")
    else:
        # Directory of images
        for ext in image_extensions:
            image_files.extend(frames_dir.glob(f"**/*{ext}"))
        image_files.sort()
    
    if not image_files:
        raise ValueError(f"No image files found in: {frames_dir}")
    
    print(f"Found {len(image_files)} images to embed")
    
    # Initialize embedder
    embedder = VisionEmbedder()
    
    # Generate embeddings
    results = []
    db = get_db_session()
    
    try:
        for image_path in tqdm(image_files, desc="Generating embeddings"):
            embedding = embedder.embed_image(image_path)
            
            if embedding is not None:
                try:
                    rel_path = str(image_path.relative_to(Path.cwd()))
                except ValueError:
                    rel_path = str(image_path)
                
                result = {
                    "image_path": rel_path,
                    "embedding": embedding.tolist(),  # Convert numpy array to list
                    "embedding_dim": embedding.shape[0]
                }
                results.append(result)
                
                # Update database - we'll set embedding_index when we build FAISS index
                segment = db.query(Segment).filter(Segment.keyframe_path == rel_path).first()
                if segment:
                    # We'll update embedding_index in fuse_index.py
                    pass
        
        # Save results to JSON
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
    
    print(f"Generated {len(results)} embeddings")
    print(f"Results saved to: {output_file}")
    
    if results:
        print(f"Embedding dimension: {results[0]['embedding_dim']}")
    
    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate vision embeddings for video frames")
    parser.add_argument("frames_path", help="Path to frames directory or single image")
    parser.add_argument("--output", default="artifacts/embeddings.json",
                       help="Output JSON file")
    
    args = parser.parse_args()
    
    try:
        results = generate_embeddings_for_frames(args.frames_path, args.output)
        print(f"Embedding generation complete! {len(results)} embeddings generated")
        
    except Exception as e:
        print(f"Embedding generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
