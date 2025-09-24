#!/usr/bin/env python3
"""Streamlit UI for SceneLens search interface."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import requests
import json
import io
from PIL import Image
from pathlib import Path
from io import BytesIO
import time

# Configure page
st.set_page_config(
    page_title="Intelligent AI Video Player",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
.main-header {
    font-size: 3rem;
    color: #2E86AB;
    text-align: center;
    margin-bottom: 2rem;
    font-weight: bold;
}

.search-box {
    font-size: 1.2rem;
    padding: 0.5rem;
    margin-bottom: 1rem;
}

.result-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 1rem;
    margin: 1rem 0;
    background-color: #f9f9f9;
}

.score-badge {
    background-color: #2E86AB;
    color: white;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
}
</style>
""", unsafe_allow_html=True)

# API configuration - auto-detect backend URL
import os

def get_backend_url():
    """Auto-detect the current backend Ngrok URL."""
    try:
        # Get current Ngrok status from localhost backend
        response = requests.get("http://localhost:8000/ngrok/status", timeout=3)
        if response.status_code == 200:
            status = response.json()
            # Look for port 8000 tunnel (backend)
            if "8000" in status.get("tunnels", {}):
                backend_url = status["tunnels"]["8000"]["url"]
                if backend_url:
                    return backend_url
        
        # No tunnel found
        return None
    except:
        # Connection failed
        return None

# Auto-detect backend URL
api_base_url = get_backend_url()

# Show current API URL with refresh option
col1, col2 = st.sidebar.columns([3, 1])
with col1:
    if api_base_url:
        st.info(f"🔗 **API:** {api_base_url}")
    else:
        st.error("❌ **API:** Not detected")
with col2:
    if st.button("🔄", help="Refresh backend URL", key="refresh_api"):
        st.rerun()

if not api_base_url:
    st.sidebar.error("🚨 **No backend tunnel detected!** Start backend Ngrok tunnel first.")
elif api_base_url.startswith('http://localhost'):
    st.sidebar.warning("💡 **Tip:** Start backend Ngrok tunnel for remote access")
else:
    st.sidebar.success("🌐 Using remote API endpoint")


def upload_and_store_video(uploaded_file, api_base_url):
    """Upload video and store metadata (no heavy processing)."""
    
    # Initialize progress tracking
    if 'upload_progress' not in st.session_state:
        st.session_state.upload_progress = 0
    
    # Create progress placeholders
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    
    try:
        # Step 1: Start upload
        st.session_state.processing_status = "uploading"
        st.session_state.upload_start_time = time.time()
        st.session_state.upload_progress = 10
        
        file_size_mb = uploaded_file.size / (1024*1024)
        
        with progress_placeholder.container():
            st.progress(0.1)
            status_placeholder.info(f"📤 Starting upload of {file_size_mb:.1f}MB file...")
        
        # Step 2: Prepare upload
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        # No timeout for video upload - let it run as long as needed
        
        st.session_state.upload_progress = 30
        with progress_placeholder.container():
            st.progress(0.3)
            status_placeholder.info(f"📤 Uploading {file_size_mb:.1f}MB to server...")
        
        # Step 3: Upload to backend
        response = requests.post(
            f"{api_base_url}/upload-video/", 
            files=files
            # No timeout - let upload run as long as needed
        )
        
        if response.status_code != 200:
            st.session_state.processing_status = "error"
            st.session_state.error_message = f"Upload failed: {response.text}"
            with progress_placeholder.container():
                st.error(f"❌ Upload failed: {response.text}")
            return
        
        # Step 4: Upload completed
        upload_time = time.time() - st.session_state.upload_start_time
        st.session_state.upload_progress = 70
        
        with progress_placeholder.container():
            st.progress(0.7)
            status_placeholder.success(f"✅ Upload completed in {upload_time:.1f} seconds")
        
        # Step 5: Store metadata
        st.session_state.processing_status = "storing"
        st.session_state.processing_start_time = time.time()
        st.session_state.upload_progress = 80
        
        with progress_placeholder.container():
            st.progress(0.8)
            status_placeholder.info("💾 Storing video metadata in database...")
        
        # Store metadata (very fast operation)
        # No timeout for video processing - let it run as long as needed
        
        process_response = requests.post(
            f"{api_base_url}/process-video/",
            json={"filename": uploaded_file.name}
            # No timeout - let processing run as long as needed
        )
        
        # Step 6: Complete
        if process_response.status_code == 200:
            result = process_response.json()
            processing_time = time.time() - st.session_state.processing_start_time
            
            st.session_state.processing_status = "completed"
            st.session_state.uploaded_video_id = result.get('video_id')
            st.session_state.uploaded_video_name = uploaded_file.name
            st.session_state.upload_progress = 100
            
            with progress_placeholder.container():
                st.progress(1.0)
                status_placeholder.success(f"✅ Video stored successfully! Total time: {upload_time + processing_time:.1f} seconds")
            
            st.info("🔍 **Note**: Video processing (keyframes, embeddings) will happen when you search - this makes uploads super fast!")
            
        else:
            st.session_state.processing_status = "error"
            st.session_state.error_message = f"Processing failed: {process_response.text}"
            with progress_placeholder.container():
                st.error(f"❌ Processing failed: {process_response.text}")
        
    except requests.exceptions.Timeout:
        st.session_state.processing_status = "error"
        st.session_state.error_message = "Request timed out unexpectedly. Please try again."
        with progress_placeholder.container():
            st.error("❌ Request timed out unexpectedly. Please try again.")
            
    except Exception as e:
        st.session_state.processing_status = "error"
        st.session_state.error_message = str(e)
        with progress_placeholder.container():
            st.error(f"❌ Error: {str(e)}")

def main():
    """Main Streamlit application."""
    
    # Check if backend is available
    if not api_base_url:
        st.error("🚨 **Backend not available!** Please start the backend Ngrok tunnel first.")
        st.info("""
        **To fix this:**
        1. Start backend tunnel: `curl -X POST "http://localhost:8000/ngrok/start" -H "Content-Type: application/json" -d '{"auth_token": "YOUR_TOKEN", "port": 8000}'`
        2. Refresh this page
        """)
        return
    
    # Header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #2E86AB; 
                   font-size: 3.5rem; 
                   font-weight: bold; 
                   margin: 0;
                   text-shadow: 2px 2px 4px rgba(0,0,0,0.1);">
            🎬 Intelligent AI Video Player
        </h1>
        <p style="color: #666; font-size: 1.2rem; margin-top: 10px; font-style: italic;">
            Search through video content using natural language queries
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'current_query' not in st.session_state:
        st.session_state.current_query = None
    if 'selected_video' not in st.session_state:
        st.session_state.selected_video = None
    if 'current_video_name' not in st.session_state:
        st.session_state.current_video_name = None
    if 'current_segment' not in st.session_state:
        st.session_state.current_segment = 0
    if 'target_segment_time' not in st.session_state:
        st.session_state.target_segment_time = None
    
    
    # Check for existing videos that are actually available in MinIO
    try:
        response = requests.get(f"{api_base_url}/check-minio-videos", timeout=5)
        if response.status_code == 200:
            minio_data = response.json()
            # Only include videos that are available in MinIO
            available_videos = [v for v in minio_data.get('videos', []) if v['status'] == 'available']
            existing_videos = []
            for v in available_videos:
                # Convert to format expected by frontend
                existing_videos.append({
                    'id': v['id'],
                    'filename': v['filename'],
                    'duration_seconds': 0,  # Will be filled from database if needed
                })
        else:
            existing_videos = []
    except:
        existing_videos = []
    
    # Show existing videos option
    if existing_videos:
        st.header("Available Videos")
        st.info("Select a video that's already processed, or upload a new one below.")
        
        video_options = ["Upload new video..."] + [f"{v['filename']} ({v['duration_seconds']:.0f}s)" for v in existing_videos]
        selected_option = st.selectbox("Choose a video:", video_options)
        
        if selected_option != "Upload new video...":
            # User selected an existing video
            selected_idx = video_options.index(selected_option) - 1
            selected_video = existing_videos[selected_idx]
            
            st.session_state.processing_status = "completed"
            st.session_state.uploaded_video_id = selected_video['id']
            st.session_state.uploaded_video_name = selected_video['filename']
            
            st.success(f"✅ Selected: {selected_video['filename']} - Ready for search!")
    
    # Video Upload Section (only show if no video selected)
    if not (st.session_state.get('processing_status') == 'completed' and st.session_state.get('uploaded_video_id')):
        st.header("Upload New Video")
        
        # Add upload info with format requirements
        st.info("📹 **Video Upload Requirements:**\n"
               "- **Format**: MP4 files only (standard MP4 or ISO Media, not M4V/AVI)\n"
               "- **Size**: No limits - upload any size video\n"
               "- **Compatibility**: Most MP4 videos work, including those from phones/cameras")
        
        uploaded_file = st.file_uploader(
            "Choose a video file",
            type=['mp4'],
            help="Upload an MP4 video file to search through"
        )
        
        if uploaded_file is not None:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.video(uploaded_file)
                
            with col2:
                file_size_mb = uploaded_file.size / (1024*1024)
                st.write(f"**File:** {uploaded_file.name}")
                st.write(f"**Size:** {file_size_mb:.1f} MB")
                
                # Show file info (no warnings)
                if file_size_mb > 1000:  # 1GB+
                    st.info(f"📹 Large video ({file_size_mb:.1f} MB) - Processing will take time")
                elif file_size_mb > 100:
                    st.info(f"📹 Medium video ({file_size_mb:.1f} MB)")
                
                # Estimate upload time (much faster now)
                upload_time_est = max(1, int(file_size_mb / 100))  # Much faster: 100MB per minute
                st.write(f"**Estimated upload time:** ~{upload_time_est} minute(s)")
                st.write("**Heavy processing:** Only when you search! 🔍")
                
                if st.button("Upload Video", type="primary"):
                    upload_and_store_video(uploaded_file, api_base_url)
    
    # Show processing status (simplified - detailed progress is handled in upload function)
    if st.session_state.get('processing_status') == "error":
        st.error(f"❌ Error: {st.session_state.get('error_message', 'Unknown error')}")
        
        # Add troubleshooting tips
        st.info("💡 **Troubleshooting Tips:**\n"
               "- Check your internet connection\n"
               "- Make sure the video format is supported (MP4 works best)\n"
               "- Try refreshing the page and uploading again")
    
    # Initialize search variables
    search_button = False
    query = ""
    
    # Only show search controls if video is uploaded or selected
    if st.session_state.get('processing_status') == 'completed' and st.session_state.get('uploaded_video_id'):
        st.markdown("---")
        
        # Main search interface
        st.header("🔍 Search Your Video")
        
        # Check backend health first
        try:
            health_response = requests.get(f"{api_base_url}/health", timeout=5)
            if health_response.status_code == 200:
                health_data = health_response.json()
                if health_data.get('status') == 'healthy':
                    st.success("✅ Video is uploaded and ready to search")
                else:
                    st.error(f"❌ Backend is unhealthy: {health_data.get('error', 'Unknown error')}")
            else:
                st.error(f"❌ Backend health check failed: {health_response.status_code}")
        except Exception as e:
            st.error(f"❌ Cannot connect to backend: {str(e)}")
        
        # Show search time message
        st.info("💡  Search time maybe longer for large videos. Please be patient.")
        
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        
        with col1:
            query = st.text_input(
                "Enter your search query:",
                key="search_query",
                help="Enter anything you want to detect in the video"
            )
        
        with col2:
            frame_interval_text = st.text_input(
                "Frame Precision (seconds):",
                value="5.0",
                help="Enter any positive value (e.g., 0.01 for ultra-high precision, 10.0 for very low precision)"
            )
        
        with col3:
            top_k = st.slider(
                "Results:",
                min_value=1,
                max_value=50,
                value=10,
                help="Number of results to return"
            )
        
        with col4:
            search_button = st.button(
                "🔍 Search", 
                type="primary"
            )
    
    # Only perform search if video is uploaded and processed
    if st.session_state.get('processing_status') == 'completed' and st.session_state.get('uploaded_video_id'):
    
        # Perform search (only if we have an uploaded video)
        if search_button and query and st.session_state.get('uploaded_video_id'):
            with st.spinner("Searching..."):
                try:
                    # Use query-based search endpoint with video_id filter
                    endpoint = f"{api_base_url}/search/video/{st.session_state.uploaded_video_id}"
                    
                    # Convert text to float with minimal validation
                    try:
                        frame_interval = float(frame_interval_text) if frame_interval_text else 5.0
                        if frame_interval <= 0:
                            st.error("⚠️ Frame interval must be positive")
                            frame_interval = 5.0
                    except ValueError:
                        st.error("⚠️ Please enter a valid number (e.g., 0.5)")
                        frame_interval = 5.0
                    
                    # Make API request
                    params = {
                        "q": query, 
                        "top_k": top_k,
                        "frame_interval": frame_interval
                    }
                    
                    response = requests.get(
                        endpoint,
                        params=params
                        # No timeout for search - let it run as long as needed
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Check for backend errors in the response
                        if 'error' in data:
                            st.error(f"❌ Backend Error: {data['error']}")
                            st.session_state.search_results = None
                            return
                        
                        # Check if we actually found results
                        if data.get('results') and len(data['results']) > 0:
                            st.session_state.search_results = data
                            st.session_state.current_query = query
                        else:
                            st.warning(f"🔍 Search completed for '{query}' - No results found. Try a different query.")
                            st.session_state.search_results = None
                    else:
                        st.error(f"❌ HTTP Error {response.status_code}: {response.text}")
                        st.session_state.search_results = None
                        
                except requests.exceptions.ConnectionError:
                    st.error("❌ Could not connect to API. Make sure the backend server is running.")
                    st.session_state.search_results = None
                except requests.exceptions.Timeout:
                    st.error("❌ Search request timed out unexpectedly. Please try again.")
                    st.session_state.search_results = None
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ Network Error: {str(e)}")
                    st.session_state.search_results = None
                except Exception as e:
                    st.error(f"❌ Unexpected Error: {str(e)}")
                    st.session_state.search_results = None
    
    # Display results if available
    if st.session_state.search_results:
        display_gallery(st.session_state.search_results, st.session_state.current_query, api_base_url)
    # Video player section - display independently when a video is selected
    if st.session_state.selected_video:
        if st.button("← Back to Search", type="primary"):
            st.session_state.selected_video = None
            st.session_state.current_segment = 0
            st.session_state.target_segment_time = None
            st.rerun()
        display_video_player(st.session_state.selected_video, api_base_url)
        
def display_gallery(data, query, api_base_url):
    """Display search results as a gallery."""
    results = data.get("results", [])
    
    if not results:
        st.warning("No results found. Try a different query.")
        return
    
    st.success(f"Found {len(results)} results for '{query}'")
    
    # Group results by video
    videos = {}
    for result in results:
        video_id = result['video_id']
        if video_id not in videos:
            videos[video_id] = []
        videos[video_id].append(result)
    
    # Display each video's results
    for video_id, video_results in videos.items():
        video_name = video_results[0].get('video_filename', 'Unknown Video')
        
        st.subheader(f"{video_name}")
        
        # Create columns for keyframes
        cols = st.columns(min(3, len(video_results)))
        
        for i, result in enumerate(video_results):
            col = cols[i % 3]
            
            with col:
                # Display keyframe
                try:
                    # Check if we have base64 image data (BLIP-2 results)
                    if result.get('image_base64'):
                        import base64
                        image_data = base64.b64decode(result['image_base64'])
                        image = Image.open(BytesIO(image_data))
                        st.image(image, use_column_width=True)
                    else:
                        # Fallback to URL-based image loading
                        image_url = f"{api_base_url}/image/{result['keyframe_path']}"
                        response = requests.get(image_url)
                        if response.status_code == 200:
                            image = Image.open(BytesIO(response.content))
                            st.image(image, width='stretch')
                        else:
                            st.error(f"Failed to load image: {response.status_code}")
                except Exception as e:
                    st.error(f"Error loading image: {str(e)}")
                
                # Display info
                start_time = result.get('segment_start_seconds') or result.get('timestamp_seconds', 0)
                end_time = result.get('segment_end_seconds')
                
                if end_time is None:
                    end_time = start_time + 2.0
                
                start_minutes = int(start_time // 60)
                start_seconds = int(start_time % 60)
                end_minutes = int(end_time // 60)
                end_seconds = int(end_time % 60)
                
                st.markdown(f"**Time:** {start_minutes}:{start_seconds:02d} → {end_minutes}:{end_seconds:02d}")
                st.markdown(f"**Score:** {result['score']:.3f}")
                
                
                # Add button to explore video
                if st.button(f"Explore Video", key=f"explore_{video_id}_{i}", type="primary"):
                    st.session_state.selected_video = video_id
                    st.session_state.current_video_name = video_name
                    # Set initial segment to the one that was clicked
                    st.session_state.current_segment = i
                    # Set target time to jump to this segment
                    segment_time = result.get('segment_start_seconds') or result.get('timestamp_seconds', 0)
                    st.session_state.target_segment_time = segment_time
                    st.rerun()
        
        st.markdown("---")


def display_video_player(video_id, api_base_url):
    """Display video player with segment navigation."""
    st.header("Video Player ")
    
    # Get search results for this video
    search_results = st.session_state.search_results.get("results", [])
    video_results = [r for r in search_results if r['video_id'] == video_id]
    
    if not video_results:
        st.error("No search results found for this video.")
        return
    
    video_name = video_results[0].get('video_filename', 'Unknown Video')
    current_query = st.session_state.get('current_query', 'Unknown Query')
    
    # Use backend streaming endpoint - works with Ngrok
    video_url = f"{api_base_url}/video/{video_id}/file"
    
    # Get current segment info for initial seek
    if st.session_state.current_segment >= len(video_results):
        st.session_state.current_segment = 0
    
    current_result = video_results[st.session_state.current_segment]
    initial_time = current_result.get('segment_start_seconds') or current_result.get('timestamp_seconds', 0)
    
    # Use target time if available (from segment jump), otherwise use current segment time
    target_time = st.session_state.target_segment_time if st.session_state.target_segment_time is not None else initial_time
    
    # Video player with segments side by side
    try:
        # Video info at the top
        st.info(f"**Video:** {video_name} | **Current Segment:** {st.session_state.current_segment + 1} of {len(video_results)}")
        
        # Create two columns: video on left, segments on right
        video_col, segments_col = st.columns([2, 1])
        
        with video_col:
            # Get current segment info for initial seek
            if st.session_state.target_segment_time is not None:
                initial_time = st.session_state.target_segment_time
            else:
                initial_time = current_result.get('segment_start_seconds') or current_result.get('timestamp_seconds', 0)
            
            # Enhanced HTML5 video player with working controls
            video_html = f"""
            <div style="margin: 20px 0;">
                <video id="main-video" controls width="100%" height="400" preload="auto">
                    <source src="{video_url}" type="video/mp4">
                    Your browser does not support HTML5 video.
                </video>
                
                <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;">
                    <button onclick="seekTo({initial_time})" style="padding: 8px 16px; background: #2E86AB; color: white; border: none; border-radius: 4px; cursor: pointer;" title="Jump to current segment">
                        Jump to Segment ({initial_time:.1f}s)
                    </button>
                    
                    <button onclick="setPlaybackRate(0.5)" style="padding: 8px 16px; background: #666; color: white; border: none; border-radius: 4px; cursor: pointer;" title="Slow down playback to half speed">
                        Slow (0.5x)
                    </button>
                    
                    <button onclick="setPlaybackRate(1)" style="padding: 8px 16px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;" title="Normal playback speed">
                        Normal (1x)
                    </button>
                    
                    <button onclick="setPlaybackRate(1.5)" style="padding: 8px 16px; background: #666; color: white; border: none; border-radius: 4px; cursor: pointer;" title="Speed up playback by 50%">
                        Fast (1.5x)
                    </button>
                    
                    <button onclick="setPlaybackRate(2)" style="padding: 8px 16px; background: #666; color: white; border: none; border-radius: 4px; cursor: pointer;" title="Double speed playback">
                        Turbo (2x)
                    </button>
                </div>
            </div>
            
            <script>
                const video = document.getElementById('main-video');
                
                function seekTo(time) {{
                    if (video.readyState >= 1) {{
                        video.currentTime = time;
                        video.play();
                    }}
                }}
                
                function setPlaybackRate(rate) {{
                    video.playbackRate = rate;
                    // Update button styles
                    document.querySelectorAll('button').forEach(btn => btn.style.background = '#666');
                    event.target.style.background = '#4CAF50';
                }}
                
                // Store video reference globally for segment navigation
                window.sceneLensVideo = video;
                
                // Auto-seek to target time when video loads
                video.addEventListener('loadedmetadata', function() {{
                    if ({initial_time} > 0) {{
                        video.currentTime = {initial_time};
                    }}
                }});
                
                // Handle video errors gracefully
                video.addEventListener('error', function() {{
                    console.error('Video error:', video.error);
                }});
            </script>
            """
            
            st.components.v1.html(video_html, height=500)
        
        with segments_col:
            # Segments section in the right column
            st.subheader("Segments")
            
            # Navigation controls
            nav_col1, nav_col2, nav_col3 = st.columns(3)
            with nav_col1:
                if st.button("⏮️ Previous", key="nav_prev", help="Go to previous segment"):
                    if st.session_state.current_segment > 0:
                        st.session_state.current_segment -= 1
                        new_result = video_results[st.session_state.current_segment]
                        new_time = new_result.get('segment_start_seconds') or new_result.get('timestamp_seconds', 0)
                        st.session_state.target_segment_time = new_time
                        st.rerun()
                    else:
                        st.warning("Already at first segment")
            
            with nav_col2:
                if st.button("🔄 Reset", key="nav_reset", help="Go back to first segment"):
                    st.session_state.current_segment = 0
                    first_result = video_results[0]
                    first_time = first_result.get('segment_start_seconds') or first_result.get('timestamp_seconds', 0)
                    st.session_state.target_segment_time = first_time
                    st.rerun()
            
            with nav_col3:
                if st.button("Next ⏭️", key="nav_next", help="Go to next segment"):
                    if st.session_state.current_segment < len(video_results) - 1:
                        st.session_state.current_segment += 1
                        new_result = video_results[st.session_state.current_segment]
                        new_time = new_result.get('segment_start_seconds') or new_result.get('timestamp_seconds', 0)
                        st.session_state.target_segment_time = new_time
                        st.rerun()
                    else:
                        st.warning("Already at last segment")
            
            # Current segment info
            current_idx = st.session_state.current_segment
            total_segments = len(video_results)
            st.info(f"**Segment {current_idx + 1} of {total_segments}**")
            
            # Individual segment list
            st.markdown("**Jump to Segment:**")
            for i, result in enumerate(video_results):
                start_time = result.get('segment_start_seconds') or result.get('timestamp_seconds', 0)
                end_time = result.get('segment_end_seconds', start_time + 2.0)
                
                # Format time for better readability
                start_min = int(start_time // 60)
                start_sec = int(start_time % 60)
                end_min = int(end_time // 60)
                end_sec = int(end_time % 60)
                
                time_str = f"{start_min}:{start_sec:02d}-{end_min}:{end_sec:02d}"
                
                # Highlight current segment
                if i == st.session_state.current_segment:
                    button_style = "primary"
                    button_text = f"🎯 Segment {i + 1}: {time_str}"
                else:
                    button_style = "secondary"
                    button_text = f"Segment {i + 1}: {time_str}"
                
                # Create help text
                help_text = f"Jump to segment {i + 1} ({time_str})"
                
                if st.button(button_text, key=f"segment_{i}", help=help_text, type=button_style):
                    st.session_state.current_segment = i
                    st.session_state.target_segment_time = start_time
                    st.rerun()
                
                # Show caption for current segment
                if i == st.session_state.current_segment and result.get('caption'):
                    st.caption(f"*{result['caption'][:100]}{'...' if len(result['caption']) > 100 else ''}*")
        
    except Exception as e:
        st.error(f"❌ Error loading video: {str(e)}")
    
    # Add JavaScript to control HTML5 video player when navigation buttons are clicked
    if st.session_state.target_segment_time is not None:
        seek_js = f"""
        <script>
            if (window.sceneLensVideo) {{
                window.sceneLensVideo.currentTime = {st.session_state.target_segment_time};
            }}
        </script>
        """
        st.components.v1.html(seek_js, height=0)
    


if __name__ == "__main__":
    main()
