#!/bin/bash

# Test Multi-Object Priority Search API
# Make sure backend is running on http://localhost:8000

echo "🧪 Testing Multi-Object Priority Search API"
echo "========================================"

# First, get list of videos to find a video_id
echo ""
echo "1. Getting list of videos..."
curl -s http://localhost:8000/check-minio-videos | python3 -m json.tool | head -20

echo ""
echo "2. Enter a video_id from above, or use a known one:"
read -p "Video ID: " VIDEO_ID

if [ -z "$VIDEO_ID" ]; then
    echo "❌ No video ID provided. Exiting."
    exit 1
fi

echo ""
echo "3. Testing multi-object priority search..."
echo "   Objects: person (priority 5), vehicle (priority 3), drone (priority 1)"

curl -X POST "http://localhost:8000/search/multi-object/${VIDEO_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "objects": [
      {"object": "person", "priority": 5},
      {"object": "vehicle", "priority": 3},
      {"object": "drone", "priority": 1}
    ],
    "top_k": 10,
    "frame_interval": 0.5
  }' | python3 -m json.tool

echo ""
echo "✅ Test complete!"
echo ""
echo "To test with different objects, modify the JSON in the curl command above."

