#!/usr/bin/env python3
"""SceneLens On-Demand Video Processing - Upload and prepare videos for intelligent search."""

import os
import sys
import argparse
import tempfile
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

def upload_video_to_minio(video_path: str) -> str:
    """Upload video to MinIO storage."""
    video_path = Path(video_path)
    
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    video_name = video_path.name
    minio_path = f"videos/{video_name}"
    
    print(f"📤 Uploading {video_name} to MinIO...")
    
    try:
        # Upload video to MinIO
        minio_client.fput_object(bucket_name, minio_path, str(video_path))
        print(f"✅ Successfully uploaded {video_name} to MinIO")
        return video_name
    except Exception as e:
        print(f"❌ Failed to upload {video_name}: {e}")
        raise

def store_video_metadata(video_name: str) -> str:
    """Store video metadata in database."""
    print(f"💾 Storing metadata for {video_name}...")
    
    # Download video temporarily to extract metadata
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        try:
            minio_client.fget_object(bucket_name, f"videos/{video_name}", temp_video.name)
            temp_path = temp_video.name
        except Exception as e:
            print(f"❌ Failed to download video for metadata extraction: {e}")
            raise
    
    try:
        # Import here to avoid circular imports
        from pipeline.ingest import store_video_metadata
        
        video_id = store_video_metadata(video_name, temp_path)
        if video_id:
            print(f"✅ Video metadata stored with ID: {video_id}")
            return video_id
        else:
            raise Exception("Failed to store video metadata")
            
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def test_on_demand_search(video_name: str):
    """Test on-demand search functionality."""
    print(f"\n🔍 Testing On-Demand Search for {video_name}")
    print("=" * 60)
    
    try:
        import requests
        
        # Test queries
        test_queries = [
            "colorful circle",
            "red strip", 
            "blue background",
            "geometric pattern"
        ]
        
        for query in test_queries:
            print(f"Testing query: '{query}'")
            response = requests.get(
                "http://localhost:8000/search/on-demand",
                params={"q": query, "top_k": 3},
                timeout=60  # Longer timeout for first search
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Found {data['total_results']} results")
                print(f"  📊 Search type: {data['search_type']}")
                
                # Show first result details
                if data['results']:
                    first_result = data['results'][0]
                    print(f"  🎯 Top result: {first_result['video_filename']} at {first_result['timestamp_seconds']:.1f}s")
                    print(f"  🎯 Score: {first_result['score']:.3f}")
            else:
                print(f"  ❌ Failed: {response.status_code} - {response.text}")
                
    except Exception as e:
        print(f"❌ On-demand search test failed: {e}")
        return False
    
    print("✅ On-demand search test completed")
    return True

def main():
    """Main entry point for SceneLens on-demand video processing."""
    parser = argparse.ArgumentParser(
        description="SceneLens On-Demand Video Processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py my_video.mp4
  python run_pipeline.py my_video.mp4 --test-search
  python run_pipeline.py my_video.mp4 --skip-upload  # If already uploaded
        """
    )
    parser.add_argument("video", help="Input video file path")
    parser.add_argument("--test-search", action="store_true", 
                       help="Test on-demand search after setup")
    parser.add_argument("--skip-upload", action="store_true",
                       help="Skip upload if video is already in MinIO")
    
    args = parser.parse_args()
    
    video_path = Path(args.video)
    video_name = video_path.name
    
    print("🎬 SceneLens On-Demand Video Processing")
    print("=" * 50)
    print(f"Video: {video_name}")
    print(f"Approach: On-demand intelligent extraction")
    print("=" * 50)
    
    try:
        # Step 1: Upload video to MinIO (if not skipped)
        if not args.skip_upload:
            video_name = upload_video_to_minio(video_path)
        else:
            print(f"⏭️ Skipping upload (assuming {video_name} already in MinIO)")
        
        # Step 2: Store video metadata in database
        video_id = store_video_metadata(video_name)
        
        # Step 3: Success message
        print("\n🎉 VIDEO SETUP COMPLETE!")
        print("=" * 50)
        print(f"✅ Video: {video_name}")
        print(f"✅ Video ID: {video_id}")
        print("✅ Ready for on-demand search!")
        
        # Step 4: Test search if requested
        if args.test_search:
            print("\n⚠️  Starting search test - make sure API server is running!")
            print("   Start API with: uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload")
            input("   Press Enter when API server is ready...")
            test_on_demand_search(video_name)
        
        # Step 5: Instructions
        print("\n📋 Next Steps:")
        print("=" * 50)
        print("1. Start the API server:")
        print("   uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload")
        print()
        print("2. Start the UI:")
        print("   streamlit run ui/app.py --server.port 8501")
        print()
        print("3. Open in browser:")
        print("   http://localhost:8501")
        print()
        print("4. Search your video:")
        print("   - Type queries like 'blue circle', 'red strip', 'bright colors'")
        print("   - First search will take 1-2 minutes (extracting frames)")
        print("   - Subsequent searches will be much faster!")
        print()
        print("🔍 API Endpoints:")
        print(f"   Search: http://localhost:8000/search/on-demand?q=blue+circle&top_k=10")
        print(f"   Video-specific: http://localhost:8000/search/video/{video_id}?q=red+strip&top_k=5")
        
    except Exception as e:
        print(f"\n❌ Processing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()