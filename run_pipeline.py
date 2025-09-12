#!/usr/bin/env python3
"""Single command to run the complete SceneLens pipeline."""

import os
import sys
import subprocess
import argparse
import tempfile
import shutil
from pathlib import Path
from minio import Minio

# Initialize MinIO client
minio_client = Minio(
    "localhost:9000",
    access_key="scenelens",
    secret_key="scenelens_dev123",
    secure=False
)

# Ensure MinIO bucket exists
bucket_name = "scenelens"
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)

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

def test_on_demand_search(video_name):
    """Test on-demand search functionality."""
    print(f"\n🔍 Testing On-Demand Search")
    print("=" * 60)
    
    try:
        import requests
        
        # Test basic on-demand search
        test_queries = [
            "colorful circle",
            "black background", 
            "geometric pattern"
        ]
        
        for query in test_queries:
            print(f"Testing query: '{query}'")
            response = requests.get(
                "http://localhost:8000/search/on-demand",
                params={"q": query, "top_k": 3},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Found {data['total_results']} results")
                print(f"  📊 Search type: {data['search_type']}")
                
                # Show first result details
                if data['results']:
                    first_result = data['results'][0]
                    print(f"  🎯 Top result: {first_result['video_filename']} at {first_result['timestamp_seconds']:.1f}s")
            else:
                print(f"  ❌ Failed: {response.status_code}")
                
    except Exception as e:
        print(f"❌ On-demand search test failed: {e}")
        return False
    
    print("✅ On-demand search test completed")
    return True

def main():
    parser = argparse.ArgumentParser(description="Run complete SceneLens pipeline")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("--interval", default="2", help="Keyframe interval in seconds")
    parser.add_argument("--test-on-demand", action="store_true", help="Test on-demand search after processing")
    
    args = parser.parse_args()
    
    # Extract video name from argument (could be just filename or full path)
    video_name = Path(args.video).name
    video_stem = Path(video_name).stem
    
    print("🎬 SceneLens Complete Pipeline")
    print(f"Video: {video_name} (from MinIO)")
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary directory: {temp_dir}")
        
        # Download video from MinIO to temp location
        local_video_path = os.path.join(temp_dir, video_name)
        
        try:
            minio_client.fget_object(bucket_name, f"videos/{video_name}", local_video_path)
            print(f"✅ Downloaded {video_name} from MinIO")
        except Exception as e:
            print(f"❌ Failed to download {video_name} from MinIO: {e}")
            sys.exit(1)

        # Create temp subdirectories
        temp_frames_dir = os.path.join(temp_dir, "frames", video_stem)
        temp_artifacts_dir = os.path.join(temp_dir, "artifacts")
        temp_faiss_dir = os.path.join(temp_dir, "faiss")
        
        os.makedirs(temp_frames_dir, exist_ok=True)
        os.makedirs(temp_artifacts_dir, exist_ok=True)
        os.makedirs(temp_faiss_dir, exist_ok=True)

        frames_dir = temp_frames_dir
    
        # Update steps to use temp paths
        temp_captions_file = os.path.join(temp_artifacts_dir, f"{video_stem}_captions.json")
        temp_embeddings_file = os.path.join(temp_artifacts_dir, f"{video_stem}_embeddings.json")
        
        steps = [
            ("pipeline/ingest.py", [local_video_path, "--output-dir", temp_dir], "Video Ingestion"),
            ("pipeline/keyframe.py", [local_video_path, "--output-dir", temp_frames_dir, "--interval", args.interval], "Keyframe Extraction"),
            ("pipeline/captions.py", [frames_dir, "--output", temp_captions_file], "Caption Generation"),
            ("pipeline/vision_embed.py", [frames_dir, "--output", temp_embeddings_file], "Vision Embeddings"),
            ("pipeline/fuse_index.py", [temp_embeddings_file, "--captions", temp_captions_file, "--output-dir", temp_faiss_dir], "Search Index"),
        ]

        # Upload artifacts to MinIO after each step
        success = True
        for script, script_args, description in steps:
            if run_step(script, script_args, description):
                # Upload generated artifacts to MinIO
                if "Keyframe Extraction" in description:
                    # Upload frames to MinIO
                    frames_uploaded = 0
                    # Handle nested directory structure created by keyframe extraction
                    actual_frames_dir = frames_dir
                    if os.path.exists(os.path.join(frames_dir, video_stem)):
                        actual_frames_dir = os.path.join(frames_dir, video_stem)
                    
                    for frame_file in os.listdir(actual_frames_dir):
                        if frame_file.endswith(('.jpg', '.jpeg', '.png')):
                            local_frame_path = os.path.join(actual_frames_dir, frame_file)
                            minio_frame_path = f"frames/{video_stem}/{frame_file}"
                            minio_client.fput_object(bucket_name, minio_frame_path, local_frame_path)
                            frames_uploaded += 1
                    print(f"📤 Uploaded {frames_uploaded} frames to MinIO")
                elif "Caption Generation" in description:
                    minio_client.fput_object(bucket_name, f"artifacts/{video_stem}_captions.json", temp_captions_file)
                    print(f"📤 Uploaded captions to MinIO")
                elif "Vision Embeddings" in description:
                    minio_client.fput_object(bucket_name, f"artifacts/{video_stem}_embeddings.json", temp_embeddings_file)
                    print(f"📤 Uploaded embeddings to MinIO")
                elif "Search Index" in description:
                    # Upload FAISS files from temp directory
                    temp_faiss_index = os.path.join(temp_faiss_dir, "keyframes.index")
                    temp_faiss_metadata = os.path.join(temp_faiss_dir, "metadata.json")
                    
                    if os.path.exists(temp_faiss_index):
                        minio_client.fput_object(bucket_name, f"faiss/{video_stem}_index.faiss", temp_faiss_index)
                        print(f"📤 Uploaded FAISS index to MinIO")
                    if os.path.exists(temp_faiss_metadata):
                        minio_client.fput_object(bucket_name, f"faiss/{video_stem}_metadata.json", temp_faiss_metadata)
                        print(f"📤 Uploaded FAISS metadata to MinIO")
            else:
                success = False
                break
    
        if success:
            print("\n🎉 PIPELINE COMPLETE!")
            print("🧹 Temporary files automatically cleaned up")
            
            # Test on-demand search if requested
            if args.test_on_demand:
                test_on_demand_search(video_name)
            
            print("\nStart services:")
            print("  API: uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload")
            print("  UI:  streamlit run ui/app.py --server.port 8501")
            print("\nOpen: http://localhost:8501")
            print("\n🔍 Try on-demand search:")
            print("  - Select 'On-demand' search type in the UI")
            print("  - Or use API: curl 'http://localhost:8000/search/on-demand?q=your_query&top_k=10'")
        else:
            print("\n❌ Pipeline failed!")
            sys.exit(1)

if __name__ == "__main__":
    main()