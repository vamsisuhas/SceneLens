#!/usr/bin/env python3
"""Direct video upload script - bypasses Streamlit for large files."""

import requests
import sys
import os
from pathlib import Path

def upload_video_direct(video_path, api_url="http://localhost:8000"):
    """Upload video directly to backend API."""
    video_path = Path(video_path)
    
    if not video_path.exists():
        print(f"❌ Video file not found: {video_path}")
        return False
    
    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"📹 Uploading: {video_path.name}")
    print(f"📊 Size: {file_size_mb:.1f} MB")
    
    try:
        # Upload video
        print("📤 Starting upload...")
        with open(video_path, 'rb') as f:
            files = {"file": (video_path.name, f, "video/mp4")}
            response = requests.post(f"{api_url}/upload-video/", files=files, timeout=3600)
        
        if response.status_code != 200:
            print(f"❌ Upload failed: {response.text}")
            return False
        
        print("✅ Upload successful!")
        
        # Process video
        print("⚙️ Starting processing...")
        process_response = requests.post(
            f"{api_url}/process-video/",
            json={"filename": video_path.name},
            timeout=7200  # 2 hours
        )
        
        if process_response.status_code == 200:
            result = process_response.json()
            video_id = result.get('video_id')
            print(f"✅ Processing complete! Video ID: {video_id}")
            print(f"🔍 You can now search this video in the web interface")
            return True
        else:
            print(f"❌ Processing failed: {process_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python direct_upload.py <video_file_path>")
        print("Example: python direct_upload.py /Users/vamsisuhas/downloads/DOD_111274657-1280x720-3000k.mp4")
        sys.exit(1)
    
    video_path = sys.argv[1]
    success = upload_video_direct(video_path)
    sys.exit(0 if success else 1)
