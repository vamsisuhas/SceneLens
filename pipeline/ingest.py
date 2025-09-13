#!/usr/bin/env python3
"""Video ingestion script for SceneLens - On-demand approach."""

import os
import sys
import argparse
import cv2
from pathlib import Path

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.minio_storage import MinIOStorage
from minio import Minio
import tempfile


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


def store_video_metadata(filename: str, video_path: str) -> str:
    """Store video metadata in MinIO - lightweight approach for on-demand processing."""
    print(f"Storing metadata for video: {filename}")
    
    try:
        # Get video metadata
        video_info = get_video_info(video_path)
        print(f"Video info: {video_info}")
        
        # Initialize MinIO storage
        minio_client = Minio(
            "localhost:9000",
            access_key="scenelens",
            secret_key="scenelens_dev123",
            secure=False
        )
        minio_storage = MinIOStorage(minio_client, "scenelens")
        
        # Create video record
        video_data = {
            "filename": filename,
            "title": Path(filename).stem.replace("_", " ").title(),
            **video_info
        }
        
        video_id = minio_storage.store_video_metadata(video_data)
        print(f"✅ Video metadata stored with ID: {video_id}")
        print("🔍 Video is ready for on-demand search - no pre-processing needed!")
        return video_id
            
    except Exception as e:
        print(f"Error processing video metadata: {e}")
        return None


def main():
    """Main entry point - lightweight video metadata storage."""
    parser = argparse.ArgumentParser(description="Store video metadata for SceneLens on-demand search")
    parser.add_argument("video_path", help="Path to input video file")
    parser.add_argument("--output-dir", default="data/videos", 
                       help="Output directory for processed videos")
    
    args = parser.parse_args()
    
    try:
        # Use the legacy ingest_video function for backward compatibility
        video_id = ingest_video(args.video_path, args.output_dir)
        print(f"✅ Video metadata storage complete! Video ID: {video_id}")
        print("🔍 Video is now ready for on-demand search!")
    except Exception as e:
        print(f"❌ Metadata storage failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
