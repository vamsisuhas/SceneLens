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
    page_title="SceneLens - AI Video Search",
    page_icon="🎬",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
.main-header {
    font-size: 3rem;
    color: #2E86AB;
    text-align: center;
    margin-bottom: 2rem;
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

# API configuration
api_base_url = st.sidebar.text_input(
    "API Base URL",
    value="http://localhost:8000",
    help="Backend API URL"
)

def check_health(api_base_url):
    """Check API health."""
    try:
        response = requests.get(f"{api_base_url}/health", timeout=5)
        if response.status_code == 200:
            st.sidebar.success("✅ API is healthy")
            return True
        else:
            st.sidebar.error("❌ API health check failed")
            return False
    except Exception as e:
        st.sidebar.error(f"❌ Could not connect to API: {e}")
        return False

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
        upload_timeout = max(300, int(file_size_mb * 5))  # 5 seconds per MB, minimum 5 minutes
        
        st.session_state.upload_progress = 30
        with progress_placeholder.container():
            st.progress(0.3)
            status_placeholder.info(f"📤 Uploading {file_size_mb:.1f}MB to server...")
        
        # Step 3: Upload to backend
        response = requests.post(
            f"{api_base_url}/upload-video/", 
            files=files,
            timeout=upload_timeout
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
        storing_timeout = 30
        
        process_response = requests.post(
            f"{api_base_url}/process-video/",
            json={"filename": uploaded_file.name},
            timeout=storing_timeout
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
        st.session_state.error_message = "Upload/processing timed out. This can happen with very large files or slow connections. You can try again."
        with progress_placeholder.container():
            st.error("❌ Upload timed out. Try again with a smaller file.")
            
    except Exception as e:
        st.session_state.processing_status = "error"
        st.session_state.error_message = str(e)
        with progress_placeholder.container():
            st.error(f"❌ Error: {str(e)}")

def main():
    """Main Streamlit application."""
    
    # Header
    st.title("SceneLens - AI Video Search")
    st.markdown("""
    Search through video content using natural language queries. 
    Find specific moments, objects, or scenes in your videos.
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
    
    # Debug session state
    st.sidebar.write("Debug - Selected Video:", st.session_state.selected_video)
    
    # Sidebar controls
    st.sidebar.header("🔧 Search Controls")
    top_k = st.sidebar.slider(
        "Number of Results", 
        min_value=1, 
        max_value=50, 
        value=10,
        help="Maximum number of results to return"
    )
    
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
            st.sidebar.write(f"Debug - Found {len(existing_videos)} available videos in MinIO")
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
        
        # Add upload info
        st.info("\n- No file size limits - upload any size video\n- Supported formats: MP4, AVI, MOV, MKV, WEBM")
        
        uploaded_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'avi', 'mov', 'mkv', 'webm'],
            help="Upload a video file to search through"
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
                
                if st.button("Upload Video", type="primary", use_container_width=True):
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
    
    # Only show search if video is uploaded and processed
    if st.session_state.get('processing_status') == 'completed' and st.session_state.get('uploaded_video_id'):
        st.markdown("---")
        
        # Main search interface
        st.header("🔍 Search Your Video")
        st.info("💡 **First search may take 1-2 minutes** as we extract frames and generate embeddings on-demand. Subsequent searches will be faster!")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            query = st.text_input(
                "Enter your search query:",
                placeholder="e.g., 'blue strip', 'red circle', 'bright colors'",
                key="search_query"
            )
        
        with col2:
            search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    
        # Perform search (only if we have an uploaded video)
        if search_button and query and st.session_state.get('uploaded_video_id'):
            with st.spinner("Searching..."):
                try:
                    # Use query-based search endpoint with video_id filter
                    endpoint = f"{api_base_url}/search/video/{st.session_state.uploaded_video_id}"
                    
                    # Make API request
                    params = {"q": query, "top_k": top_k}
                    
                    response = requests.get(
                        endpoint,
                        params=params,
                        timeout=60  # Longer timeout for query-based search
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.search_results = data
                        st.session_state.current_query = query
                        st.success(f"✅ Search completed! Found results for '{query}'")
                    else:
                        st.error(f"Search failed: {response.status_code} - {response.text}")
                        
                except requests.exceptions.ConnectionError:
                    st.error("❌ Could not connect to API. Make sure the backend server is running.")
                except requests.exceptions.Timeout:
                    st.error("❌ Search request timed out. Try a simpler query.")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Display results if available
    if st.session_state.search_results:
        display_gallery(st.session_state.search_results, st.session_state.current_query, api_base_url)
    
    # Health check in sidebar
    st.sidebar.header("🏥 System Status")
    if st.sidebar.button("Check Health"):
        check_health(api_base_url)
    
    # Instructions
    with st.expander("ℹ️ How to Use"):
        st.markdown("""
        **SceneLens** allows you to search through video frames using natural language queries.
        
        **How It Works:**
        - **Query-based Search**: Analyzes the entire video based on your search query
        - **Smart Frame Selection**: Finds the most relevant frames that match your description
        - **Temporal Diversity**: Ensures results come from different parts of the video
        
        **Example Queries:**
        - "blue strip" or "red circle"
        - "bright colors" or "dark background"
        - "a person walking" or "drone flying"
        
        **Tips:**
        - Be descriptive but concise
        - Try different phrasings if you don't get good results
        - Click "Explore Video" to see the video player with segments
        """)


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
        
        st.subheader(f"📹 {video_name}")
        
        # Create columns for keyframes
        cols = st.columns(min(3, len(video_results)))
        
        for i, result in enumerate(video_results):
            col = cols[i % 3]
            
            with col:
                # Display keyframe
                try:
                    image_url = f"{api_base_url}/image/{result['keyframe_path']}"
                    response = requests.get(image_url)
                    if response.status_code == 200:
                        image = Image.open(BytesIO(response.content))
                        st.image(image, use_column_width=True)
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
                
                if result.get('is_on_demand'):
                    st.markdown("**Dynamically extracted**")
                
                # Add button to explore video
                if st.button(f"🎬 Explore Video", key=f"explore_{video_id}_{i}"):
                    st.session_state.selected_video = video_id
                    st.session_state.current_video_name = video_name
                    st.rerun()
        
        st.markdown("---")
    
    # Video player section
    if st.session_state.selected_video:
        st.info(f"Selected video: {st.session_state.selected_video}")
        display_video_player(st.session_state.selected_video, api_base_url)


def display_video_player(video_id, api_base_url):
    """Display video player with segment navigation."""
    st.header("🎬 Video Player")
    
    # Get search results for this video
    search_results = st.session_state.search_results.get("results", [])
    video_results = [r for r in search_results if r['video_id'] == video_id]
    
    if not video_results:
        st.error("No search results found for this video.")
        return
    
    video_name = video_results[0].get('video_filename', 'Unknown Video')
    st.subheader(f"📹 {video_name}")
    current_query = st.session_state.get('current_query', 'Unknown Query')
    st.markdown(f"**Query:** '{current_query}'")
    st.markdown(f"**Found {len(video_results)} relevant segments**")
    
    # Use the actual video from MinIO
    video_url = f"{api_base_url}/video/{video_id}/file"
    
    # Get current segment info for initial seek
    if st.session_state.current_segment >= len(video_results):
        st.session_state.current_segment = 0
    
    current_result = video_results[st.session_state.current_segment]
    initial_time = current_result.get('segment_start_seconds') or current_result.get('timestamp_seconds', 0)
    
    # Use target time if available (from segment jump), otherwise use current segment time
    target_time = st.session_state.target_segment_time if st.session_state.target_segment_time is not None else initial_time
    
    # Clean video player with auto-seek functionality
    video_html = f"""
    <div style="text-align: center; margin-bottom: 15px;">
        <video id="mainVideo" width="100%" height="400" controls preload="metadata">
            <source src="{video_url}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
    </div>
    
    <script>
        const video = document.getElementById('mainVideo');
        
        // Auto-seek to target time when video is ready
        function seekToTime(time) {{
            console.log('Seeking to time:', time);
            if (video.readyState >= 2) {{
                video.currentTime = time;
            }} else {{
                video.addEventListener('loadedmetadata', function() {{
                    video.currentTime = time;
                }}, {{ once: true }});
            }}
        }}
        
        // Auto-seek when video is ready
        video.addEventListener('loadedmetadata', function() {{
            seekToTime({target_time});
        }});
        
        // Handle video seeking completion
        video.addEventListener('seeked', function() {{
            console.log('Video seeked to:', video.currentTime);
        }});
        
        // Handle video errors
        video.addEventListener('error', function(e) {{
            console.error('Video error:', e);
        }});
    </script>
    """
    
    # Show current target time and segment info
    current_result = video_results[st.session_state.current_segment]
    current_start = current_result.get('segment_start_seconds') or current_result.get('timestamp_seconds', 0)
    current_end = current_result.get('segment_end_seconds', current_start + 2.0)
    
    if st.session_state.target_segment_time is not None:
        st.success(f"🎯 Jumping to: {st.session_state.target_segment_time:.1f}s")
    else:
        st.info(f"📍 Current Segment: {current_start:.1f}s - {current_end:.1f}s")
    
    # Clear the target time after using it
    if st.session_state.target_segment_time is not None:
        st.session_state.target_segment_time = None
    
    st.components.v1.html(video_html, height=500)
    
    # Simple segment navigation
    st.markdown("---")
    st.subheader("🎮 Navigation")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("⏮️ Previous"):
            if st.session_state.current_segment > 0:
                st.session_state.current_segment -= 1
                # Set target time for the new segment
                new_result = video_results[st.session_state.current_segment]
                new_time = new_result.get('segment_start_seconds') or new_result.get('timestamp_seconds', 0)
                st.session_state.target_segment_time = new_time
                st.rerun()
    
    with col2:
        if st.button("⏭️ Next"):
            if st.session_state.current_segment < len(video_results) - 1:
                st.session_state.current_segment += 1
                # Set target time for the new segment
                new_result = video_results[st.session_state.current_segment]
                new_time = new_result.get('segment_start_seconds') or new_result.get('timestamp_seconds', 0)
                st.session_state.target_segment_time = new_time
                st.rerun()
    
    with col3:
        if st.button("🔄 Reset"):
            st.session_state.current_segment = 0
            # Set target time for first segment
            first_result = video_results[0]
            first_time = first_result.get('segment_start_seconds') or first_result.get('timestamp_seconds', 0)
            st.session_state.target_segment_time = first_time
            st.rerun()
    
    # Interactive segment list with jump buttons
    st.markdown("---")
    st.subheader("📋 Segments")
    
    for i, result in enumerate(video_results):
        start_time = result.get('segment_start_seconds') or result.get('timestamp_seconds', 0)
        end_time = result.get('segment_end_seconds', start_time + 2.0)
        
        # Create columns for segment info and jump button
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Highlight current segment
            if i == st.session_state.current_segment:
                st.markdown(f"**🎯 Segment {i + 1}:** {start_time:.1f}s - {end_time:.1f}s")
            else:
                st.markdown(f"Segment {i + 1}: {start_time:.1f}s - {end_time:.1f}s")
        
        with col2:
            # Jump button for each segment
            if st.button(f"🎯 Jump", key=f"jump_{i}"):
                st.session_state.current_segment = i
                # Store the target time for the video to seek to
                st.session_state.target_segment_time = start_time
                st.rerun()
    
    # Back button
    if st.button("← Back to Search"):
        st.session_state.selected_video = None
        st.session_state.current_segment = 0
        st.rerun()


if __name__ == "__main__":
    main()
