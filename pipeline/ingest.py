#!/usr/bin/env python3
"""Video ingestion script for SceneLens."""

import os
import sys
import argparse
import cv2
from pathlib import Path
from tqdm import tqdm

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.database import get_db_session, init_db
from pipeline.models import Video
from pipeline.keyframe import extract_keyframes
from pipeline.captions import generate_captions_for_frames
from pipeline.vision_embed import generate_embeddings_for_frames
from minio import Minio
import tempfile
import uuid


def get_video_info(video_path):
    """Extract video metadata using OpenCV."""
    cap = cv2.VideoCapture(str(video_path))
    
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0
    file_size = os.path.getsize(video_path)
    
    cap.release()
    
    return {
        "fps": fps,
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "file_size_bytes": file_size,
    }


def ingest_video(video_path, output_dir="data/videos"):
    """Ingest a video file into the system."""
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    print(f"Ingesting video: {video_path}")
    
    # Copy video to output directory with standard name
    output_path = output_dir / f"{video_path.stem}.mp4"
    
    # Skip conversion if input and output are the same
    if video_path.resolve() == output_path.resolve():
        print(f"Video already in correct location: {output_path}")
    else:
        # Use ffmpeg to ensure standard format
        import subprocess
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-c:v", "libx264", "-c:a", "aac",
            "-y", str(output_path)  # -y to overwrite
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"Video converted and saved to: {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}")
            raise
        except FileNotFoundError:
            print("ERROR: ffmpeg not found. Please install ffmpeg.")
            print("  macOS: brew install ffmpeg")
            print("  Ubuntu: sudo apt install ffmpeg")
            print("  Windows: Download from https://ffmpeg.org/")
            sys.exit(1)
    
    # Get video metadata
    try:
        video_info = get_video_info(output_path)
        print(f"Video info: {video_info}")
    except Exception as e:
        print(f"Warning: Could not extract video info: {e}")
        video_info = {}
    
    # Store in database
    init_db()
    db = get_db_session()
    try:
        video = Video(
            filename=output_path.name,
            title=video_path.stem.replace("_", " ").title(),
            **video_info
        )
        db.add(video)
        db.commit()
        print(f"Video record created in database with ID: {video.id}")
        return video.id
    except Exception as e:
        db.rollback()
        print(f"Database error: {e}")
        raise
    finally:
        db.close()


class VideoIngestPipeline:
    """Complete video processing pipeline."""
    
    def __init__(self):
        self.minio_client = Minio(
            "localhost:9000",
            access_key="scenelens",
            secret_key="scenelens_dev123",
            secure=False
        )
        self.bucket_name = "scenelens"
    
    def process_video_from_minio(self, filename: str, minio_path: str) -> str:
        """Process a video that's already uploaded to MinIO."""
        print(f"Processing video from MinIO: {minio_path}")
        
        # Download video from MinIO to temp location
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            try:
                self.minio_client.fget_object(self.bucket_name, minio_path, temp_video.name)
                video_path = temp_video.name
            except Exception as e:
                print(f"Failed to download video from MinIO: {e}")
                return None
        
        try:
            # Get video metadata
            video_info = get_video_info(video_path)
            print(f"Video info: {video_info}")
            
            # Store video in database
            init_db()
            db = get_db_session()
            
            try:
                # Create video record
                video = Video(
                    filename=filename,
                    title=Path(filename).stem.replace("_", " ").title(),
                    **video_info
                )
                db.add(video)
                db.commit()
                video_id = video.id
                print(f"Video record created with ID: {video_id}")
                
                # Extract keyframes
                print("Extracting keyframes...")
                keyframes_dir = f"data/frames/{Path(filename).stem}"
                os.makedirs(keyframes_dir, exist_ok=True)
                keyframes = extract_keyframes(video_path, keyframes_dir, interval_seconds=1.0)
                
                # Generate captions for keyframes
                print("Generating captions...")
                captions = generate_captions_for_frames(keyframes_dir)
                
                # Generate embeddings and store segments
                print("Generating embeddings...")
                generate_embeddings_for_frames(keyframes_dir)
                
                print(f"✅ Video processing completed for: {filename}")
                return video_id
                
            except Exception as e:
                db.rollback()
                print(f"Database error during processing: {e}")
                return None
            finally:
                db.close()
                
        finally:
            # Clean up temp file
            if os.path.exists(video_path):
                os.remove(video_path)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Ingest video files into SceneLens")
    parser.add_argument("video_path", help="Path to input video file")
    parser.add_argument("--output-dir", default="data/videos", 
                       help="Output directory for processed videos")
    
    args = parser.parse_args()
    
    try:
        video_id = ingest_video(args.video_path, args.output_dir)
        print(f"Video ingestion complete! Video ID: {video_id}")
    except Exception as e:
        print(f"Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
