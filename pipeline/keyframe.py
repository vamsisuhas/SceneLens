#!/usr/bin/env python3
"""Keyframe extraction script for SceneLens."""

import os
import sys
import argparse
import cv2
import numpy as np
from pathlib import Path
from tqdm import tqdm

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.database import get_db_session
from pipeline.models import Video, Segment


def extract_keyframes(video_path, output_dir="data/frames", interval_seconds=2.0):
    """Extract keyframes from video at regular intervals."""
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    
    # Create output directory for this video
    video_frames_dir = output_dir / video_path.stem
    video_frames_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Extracting keyframes from: {video_path}")
    print(f"Output directory: {video_frames_dir}")
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"Video: {fps:.2f} FPS, {total_frames} frames, {duration:.2f}s")
    
    # Calculate frame interval
    frame_interval = int(fps * interval_seconds)
    if frame_interval == 0:
        frame_interval = 1
    
    keyframes = []
    frame_number = 0
    
    # Get video from database
    db = get_db_session()
    video_record = db.query(Video).filter(Video.filename == video_path.name).first()
    if not video_record:
        print(f"Warning: Video not found in database: {video_path.name}")
        db.close()
        video_record = None
    
    try:
        with tqdm(total=total_frames, desc="Extracting frames") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Extract keyframe at interval
                if frame_number % frame_interval == 0:
                    timestamp = frame_number / fps
                    frame_filename = f"frame_{frame_number:06d}_t{timestamp:.2f}s.jpg"
                    frame_path = video_frames_dir / frame_filename
                    
                    # Save frame
                    cv2.imwrite(str(frame_path), frame)
                    
                    try:
                        rel_path = str(frame_path.relative_to(Path.cwd()))
                    except ValueError:
                        # If relative_to fails, use the frame path relative to project root
                        rel_path = str(frame_path)
                    
                    keyframe_info = {
                        "frame_number": frame_number,
                        "timestamp_seconds": timestamp,
                        "keyframe_path": rel_path,
                    }
                    keyframes.append(keyframe_info)
                    
                    # Save to database if video record exists
                    if video_record:
                        segment = Segment(
                            video_id=video_record.id,
                            frame_number=frame_number,
                            timestamp_seconds=timestamp,
                            keyframe_path=rel_path,
                        )
                        db.add(segment)
                
                frame_number += 1
                pbar.update(1)
        
        # Commit database changes
        if video_record:
            db.commit()
            print(f"Saved {len(keyframes)} segments to database")
        
    except Exception as e:
        if video_record:
            db.rollback()
        raise
    finally:
        cap.release()
        if video_record:
            db.close()
    
    print(f"Extracted {len(keyframes)} keyframes")
    return keyframes


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Extract keyframes from video")
    parser.add_argument("video_path", help="Path to input video file")
    parser.add_argument("--output-dir", default="data/frames",
                       help="Output directory for keyframes")
    parser.add_argument("--interval", type=float, default=2.0,
                       help="Keyframe extraction interval in seconds")
    
    args = parser.parse_args()
    
    try:
        keyframes = extract_keyframes(args.video_path, args.output_dir, args.interval)
        print(f"Keyframe extraction complete! {len(keyframes)} frames extracted")
    except Exception as e:
        print(f"Keyframe extraction failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
