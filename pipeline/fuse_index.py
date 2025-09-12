#!/usr/bin/env python3
"""Fuse captions and embeddings into searchable index."""

import os
import sys
import argparse
import json
import numpy as np
from pathlib import Path
import faiss

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.database import get_db_session
from pipeline.models import Segment


def build_faiss_index(embeddings_file, captions_file=None, output_dir="faiss"):
    """Build FAISS index from embeddings and update database."""
    embeddings_file = Path(embeddings_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not embeddings_file.exists():
        raise FileNotFoundError(f"Embeddings file not found: {embeddings_file}")
    
    print(f"Loading embeddings from: {embeddings_file}")
    with open(embeddings_file, "r") as f:
        embeddings_data = json.load(f)
    
    if not embeddings_data:
        raise ValueError("No embeddings found in file")
    
    # Load captions if provided
    captions_data = {}
    if captions_file:
        captions_file = Path(captions_file)
        if captions_file.exists():
            print(f"Loading captions from: {captions_file}")
            with open(captions_file, "r") as f:
                captions_list = json.load(f)
            # Convert to dict for lookup
            captions_data = {item["image_path"]: item for item in captions_list}
    
    # Prepare embeddings for FAISS
    embeddings = []
    image_paths = []
    
    for item in embeddings_data:
        embedding = np.array(item["embedding"], dtype=np.float32)
        embeddings.append(embedding)
        image_paths.append(item["image_path"])
    
    embeddings_array = np.vstack(embeddings)
    dimension = embeddings_array.shape[1]
    
    print(f"Building FAISS index with {len(embeddings)} vectors of dimension {dimension}")
    
    # Create FAISS index
    # Using IVF (Inverted File) index for better performance with larger datasets
    if len(embeddings) < 1000:
        # For small datasets, use brute force
        index = faiss.IndexFlatIP(dimension)  # Inner Product (cosine similarity)
    else:
        # For larger datasets, use IVF
        nlist = min(100, len(embeddings) // 10)  # Number of clusters
        quantizer = faiss.IndexFlatIP(dimension)
        index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
        
        # Train the index
        print("Training FAISS index...")
        index.train(embeddings_array)
    
    # Add vectors to index
    print("Adding vectors to index...")
    index.add(embeddings_array)
    
    # Save index
    index_file = output_dir / "keyframes.index"
    faiss.write_index(index, str(index_file))
    print(f"✅ FAISS index saved to: {index_file}")
    
    # Save metadata mapping
    metadata = {
        "index_to_path": image_paths,
        "dimension": dimension,
        "total_vectors": len(embeddings),
    }
    
    metadata_file = output_dir / "metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"✅ Metadata saved to: {metadata_file}")
    
    # Update database with embedding indices and captions
    db = get_db_session()
    try:
        updated_count = 0
        for i, image_path in enumerate(image_paths):
            segment = db.query(Segment).filter(Segment.keyframe_path == image_path).first()
            if segment:
                segment.embedding_index = i
                
                # Update caption if we have it and it's not already set
                if image_path in captions_data and not segment.caption:
                    caption_info = captions_data[image_path]
                    segment.caption = caption_info["caption"]
                    segment.caption_confidence = caption_info.get("confidence", 1.0)
                
                updated_count += 1
        
        db.commit()
        print(f"✅ Updated {updated_count} segments in database")
        
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
    
    return {
        "index_file": str(index_file),
        "metadata_file": str(metadata_file),
        "total_vectors": len(embeddings),
        "dimension": dimension,
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build searchable index from embeddings")
    parser.add_argument("embeddings_file", help="Path to embeddings JSON file")
    parser.add_argument("--captions", help="Path to captions JSON file (optional)")
    parser.add_argument("--output-dir", default="faiss",
                       help="Output directory for FAISS index")
    
    args = parser.parse_args()
    
    try:
        result = build_faiss_index(args.embeddings_file, args.captions, args.output_dir)
        print(f"✅ Index building complete!")
        print(f"   Vectors: {result['total_vectors']}")
        print(f"   Dimension: {result['dimension']}")
        print(f"   Index: {result['index_file']}")
        print(f"   Metadata: {result['metadata_file']}")
        
    except Exception as e:
        print(f"❌ Index building failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
