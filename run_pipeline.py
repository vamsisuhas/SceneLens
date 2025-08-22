#!/usr/bin/env python3
"""Single command to run the complete SceneLens pipeline."""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_step(script, args, description):
    """Run a pipeline step."""
    print(f"\n🚀 {description}")
    print("=" * 60)
    
    cmd = [sys.executable, script] + args
    print(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, cwd=Path.cwd())
    if result.returncode != 0:
        print(f"❌ Failed: {description}")
        return False
    
    print(f"✅ Success: {description}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Run complete SceneLens pipeline")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("--interval", default="2", help="Keyframe interval in seconds")
    
    args = parser.parse_args()
    
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"❌ Video not found: {video_path}")
        sys.exit(1)
    
    print("🎬 SceneLens Complete Pipeline")
    print(f"Video: {video_path}")
    
    # Ensure directories exist
    os.makedirs("data/videos", exist_ok=True)
    os.makedirs("data/frames", exist_ok=True) 
    os.makedirs("artifacts", exist_ok=True)
    os.makedirs("faiss", exist_ok=True)
    
    video_stem = video_path.stem
    frames_dir = f"data/frames/{video_stem}"
    
    steps = [
        ("pipeline/ingest.py", [str(video_path)], "Video Ingestion"),
        ("pipeline/keyframe.py", [str(video_path), "--interval", args.interval], "Keyframe Extraction"),
        ("pipeline/captions.py", [frames_dir, "--output", f"artifacts/{video_stem}_captions.json"], "Caption Generation"),
        ("pipeline/vision_embed.py", [frames_dir, "--output", f"artifacts/{video_stem}_embeddings.json"], "Vision Embeddings"),
        ("pipeline/fuse_index.py", [f"artifacts/{video_stem}_embeddings.json", "--captions", f"artifacts/{video_stem}_captions.json"], "Search Index"),
    ]
    
    success = True
    for script, script_args, description in steps:
        if not run_step(script, script_args, description):
            success = False
            break
    
    if success:
        print("\n🎉 PIPELINE COMPLETE!")
        print("\nStart services:")
        print("  API: bazel run //backend:server")
        print("  UI:  bazel run //ui:app") 
        print("\nAlternatively with Python:")
        print("  API: source .venv/bin/activate && python backend/app.py")
        print("  UI:  source .venv/bin/activate && streamlit run ui/proto/app.py --server.port 8501")
        print("\nOpen: http://localhost:8501")
    else:
        print("\n❌ Pipeline failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
