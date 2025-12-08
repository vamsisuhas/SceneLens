#!/usr/bin/env python3
"""
Test script for Multi-Object Priority Search API
"""

import requests
import json
import sys

API_BASE_URL = "http://localhost:8000"

def test_health():
    """Test if backend is running."""
    print("1. Testing backend health...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Backend is healthy")
            print(f"   Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"   ❌ Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Cannot connect to backend: {e}")
        print(f"   Make sure backend is running: python backend/app.py")
        return False

def get_videos():
    """Get list of available videos."""
    print("\n2. Getting list of videos...")
    try:
        response = requests.get(f"{API_BASE_URL}/check-minio-videos", timeout=10)
        if response.status_code == 200:
            data = response.json()
            videos = data.get('videos', [])
            print(f"   ✅ Found {len(videos)} videos")
            
            if videos:
                print("\n   Available videos:")
                for i, video in enumerate(videos[:5], 1):  # Show first 5
                    print(f"   {i}. {video.get('filename', 'Unknown')} (ID: {video.get('id', 'N/A')})")
                
                return videos[0].get('id') if videos else None
            else:
                print("   ⚠️  No videos found. Upload a video first.")
                return None
        else:
            print(f"   ❌ Failed to get videos: {response.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Error getting videos: {e}")
        return None

def test_multi_object_search(video_id, objects_list):
    """Test multi-object priority search."""
    print(f"\n3. Testing multi-object priority search on video {video_id}...")
    print(f"   Objects: {[(obj['object'], obj['priority']) for obj in objects_list]}")
    
    request_data = {
        "objects": objects_list,
        "top_k": 10,
        "frame_interval": 0.5
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/search/multi-object/{video_id}",
            json=request_data,
            timeout=120  # Search can take time
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            print(f"   ✅ Search successful!")
            print(f"   Query: {data.get('query', 'N/A')}")
            print(f"   Total results: {data.get('total_results', 0)}")
            print(f"   Search type: {data.get('search_type', 'N/A')}")
            
            if results:
                print(f"\n   Top 3 results:")
                for i, result in enumerate(results[:3], 1):
                    print(f"   {i}. Time: {result.get('segment_start_seconds', 0):.1f}s")
                    print(f"      Objects: {', '.join(result.get('objects_detected', []))}")
                    print(f"      Weighted Score: {result.get('weighted_score', 0):.2f}")
                    print(f"      Normalized Score: {result.get('score', 0):.3f}")
            else:
                print("   ⚠️  No results found")
            
            return True
        else:
            print(f"   ❌ Search failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("   ⚠️  Request timed out (search may take longer)")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("🧪 Multi-Object Priority Search API Test")
    print("=" * 50)
    
    # Test 1: Health check
    if not test_health():
        sys.exit(1)
    
    # Test 2: Get videos
    video_id = get_videos()
    if not video_id:
        print("\n❌ Cannot proceed without a video. Please upload a video first.")
        sys.exit(1)
    
    # Test 3: Multi-object search - Example 1
    print("\n" + "=" * 50)
    test_objects_1 = [
        {"object": "person", "priority": 5},
        {"object": "vehicle", "priority": 3},
        {"object": "drone", "priority": 1}
    ]
    test_multi_object_search(video_id, test_objects_1)
    
    # Test 4: Multi-object search - Example 2 (if you want to test more)
    print("\n" + "=" * 50)
    print("\n4. Testing with different objects...")
    test_objects_2 = [
        {"object": "car", "priority": 4},
        {"object": "truck", "priority": 2}
    ]
    test_multi_object_search(video_id, test_objects_2)
    
    print("\n" + "=" * 50)
    print("✅ All tests complete!")
    print("\nTo test the visualization dashboard:")
    print("  streamlit run visualizations/multi_object_priority.py")

if __name__ == "__main__":
    main()

