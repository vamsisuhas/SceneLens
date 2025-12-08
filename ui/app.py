#!/usr/bin/env python3
"""Streamlit UI for SceneLens search interface."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import requests
import io
from PIL import Image
from pathlib import Path
from io import BytesIO
import time
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# Configure page
st.set_page_config(
    page_title="Intelligent AI Video Player",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Enhanced Custom CSS with modern styling
st.markdown("""
<style>
/* Global Styles */
.stApp {
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.main-header {
    font-size: 3.5rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    margin-bottom: 2rem;
    font-weight: 800;
    letter-spacing: -1px;
}

.search-box {
    font-size: 1.2rem;
    padding: 0.5rem;
    margin-bottom: 1rem;
}

.result-card {
    border: none;
    border-radius: 16px;
    padding: 1.5rem;
    margin: 1rem 0;
    background: white;
    box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.result-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 12px 48px rgba(31, 38, 135, 0.25);
}

.score-badge {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 0.4rem 0.8rem;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

/* Enhanced buttons - all buttons get gradient styling */
.stButton > button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    border: none !important;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
    transition: all 0.3s ease !important;
    padding: 10px 20px !important;
    outline: none !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6) !important;
}

.stButton > button:focus,
.stButton > button:active {
    outline: none !important;
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
}

/* Enhanced text input - remove our border, only use Streamlit's */
.stTextInput input,
.stNumberInput input {
    border: none !important;
    border-radius: 0 !important;
    font-size: 1.05rem !important;
    transition: all 0.3s ease !important;
    outline: none !important;
    box-shadow: none !important;
}

/* Style only the wrapper div (Streamlit's border) */
.stTextInput > div > div,
.stNumberInput > div > div {
    border-radius: 12px !important;
    transition: all 0.3s ease !important;
}

/* Change wrapper border color to purple when focused */
.stTextInput > div > div:focus-within,
.stNumberInput > div > div:focus-within {
    border-color: #667eea !important;
    box-shadow: 0 0 0 1px #667eea !important;
}

/* Radio buttons with rounded styling */
.stRadio > div {
    background: white;
    padding: 15px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.stRadio > div > label > div[data-testid="stMarkdownContainer"] > p {
    font-size: 1.1rem;
    font-weight: 600;
    color: #333;
}

/* File uploader styling */
.stFileUploader > div > div {
    border-radius: 12px !important;
}

/* Select box styling */
.stSelectbox > div > div {
    border-radius: 12px !important;
}

.stSelectbox > div > div > div {
    border-radius: 12px !important;
    outline: none !important;
}


/* Sidebar styling */
.css-1d391kg {
    background: white;
    box-shadow: 2px 0 15px rgba(0,0,0,0.1);
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

# If auto-detection fails, use ngrok CLI backend URL
if not api_base_url:
    api_base_url = "https://my-backend.ngrok.io"

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
        1. Start ngrok CLI: `./ngrok start --all`
        2. Refresh this page
        """)
        return
    
    # Loading screen - wait for models to load
    loading_placeholder = st.empty()
    with loading_placeholder.container():
        st.markdown("""
        <div style='text-align: center; padding: 100px 20px;'>
            <h1 style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       -webkit-background-clip: text; 
                       -webkit-text-fill-color: transparent; 
                       font-size: 3em; 
                       margin-bottom: 20px;'>
                🎬 Intelligent AI Video Player
            </h1>
            <p style='color: #666; font-size: 1.3em; margin-bottom: 40px;'>Initializing AI Models...</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Check backend health and wait for models
        max_wait_minutes = 15  # Maximum 15 minutes to wait for models to load
        max_retries = max_wait_minutes * 20  # Check every 3 seconds
        retry_count = 0
        models_ready = False
        
        status_text.info(f"⏳ Waiting for AI models to load (BLIP-2 + X-CLIP)... This may take up to {max_wait_minutes} minutes on first run.")
        
        while retry_count < max_retries and not models_ready:
            try:
                # Show progress (but cap at 90% until actually ready)
                progress_value = min((retry_count / max_retries), 0.9)
                progress_bar.progress(progress_value)
                
                # Calculate elapsed time
                elapsed_minutes = (retry_count * 3) // 60
                elapsed_seconds = (retry_count * 3) % 60
                status_text.info(f"⏳ Loading AI models... {elapsed_minutes}m {elapsed_seconds}s elapsed (max {max_wait_minutes} minutes)")
                
                health_response = requests.get(f"{api_base_url}/health", timeout=10)
                if health_response.status_code == 200:
                    health_data = health_response.json()
                    if health_data.get('status') == 'healthy':
                        models_ready = True
                        progress_bar.progress(1.0)
                        status_text.success("✅ All AI models loaded successfully!")
                        time.sleep(1)  # Brief pause to show success
                        break
                    else:
                        # Backend is loading, show specific message if available
                        error_msg = health_data.get('error', 'Initializing...')
                        status_text.info(f"⏳ Loading AI models... {elapsed_minutes}m {elapsed_seconds}s - {error_msg}")
                    
            except Exception as e:
                # Connection error - backend might still be starting
                elapsed_minutes = (retry_count * 3) // 60
                elapsed_seconds = (retry_count * 3) % 60
                status_text.info(f"⏳ Waiting for backend to start... {elapsed_minutes}m {elapsed_seconds}s")
            
            time.sleep(3)  # Check every 3 seconds instead of every 1 second
            retry_count += 1
        
        if not models_ready:
            loading_placeholder.empty()
            st.error(f"❌ **Models not loaded after {max_wait_minutes} minutes**")
            st.info("""
            **Troubleshooting:**
            1. Check if backend is running: `ps aux | grep "backend/app.py"`
            2. Check backend logs for errors
            3. Make sure you have enough GPU/CPU memory for BLIP-2 and X-CLIP models
            4. Try restarting backend: `pkill -f "backend/app.py" && python backend/app.py &`
            """)
            return
    
    # Clear loading screen
    loading_placeholder.empty()
    
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
    if 'search_mode' not in st.session_state:
        st.session_state.search_mode = "Object Detection"
    if 'multi_object_list' not in st.session_state:
        st.session_state.multi_object_list = []
    if 'auto_analysis_results' not in st.session_state:
        st.session_state.auto_analysis_results = None
    if 'selected_cluster_keyword' not in st.session_state:
        st.session_state.selected_cluster_keyword = None
    
    
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
        st.info("**Video Upload Requirements:**\n"
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
    
    # Only show search controls if video is uploaded or selected AND no search results yet
    if st.session_state.get('processing_status') == 'completed' and st.session_state.get('uploaded_video_id') and not st.session_state.selected_video:
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
        
        # Mode selector
        mode = st.radio(
            "Select Detection Mode:",
            ["🔍 Object Detection", "🎬 Action Detection", "🎯 Multi-Object Priority", "🤖 Auto Analysis"],
            index=0 if st.session_state.search_mode == "Object Detection" else (1 if st.session_state.search_mode == "Action Detection" else (2 if st.session_state.search_mode == "Multi-Object Priority" else 3)),
            horizontal=True,
            help="Object Detection: Find specific objects | Action Detection: Find temporal actions | Multi-Object Priority: Search multiple objects with priority weights | Auto Analysis: Automatically analyze and cluster entire video"
        )
        if "Object Detection" in mode:
            st.session_state.search_mode = "Object Detection"
        elif "Action Detection" in mode:
            st.session_state.search_mode = "Action Detection"
        elif "Multi-Object Priority" in mode:
            st.session_state.search_mode = "Multi-Object Priority"
        else:
            st.session_state.search_mode = "Auto Analysis"
        
        st.markdown("---")
        
        # Mode-specific UI
        if st.session_state.search_mode == "Multi-Object Priority":
            # Multi-Object Priority mode
            st.info("🎯 **Multi-Object Priority Search**: Add multiple objects with priority weights (1, 2, 3, 4, etc.). Higher numbers = more important.")
            
            # Object list management
            st.subheader("Objects & Priorities")
            
            # Add object input
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                new_object = st.text_input("Object", key="new_object_input", placeholder="e.g., person", label_visibility="collapsed")
            with col2:
                new_priority = st.number_input("Priority", min_value=1, max_value=10, value=1, step=1, key="new_priority_input", label_visibility="collapsed")
            with col3:
                if st.button("➕ Add", key="add_object_btn", use_container_width=True):
                    if new_object.strip():
                        st.session_state.multi_object_list.append({
                            'object': new_object.strip(),
                            'priority': int(new_priority)
                        })
                        st.rerun()
            
            # Display current objects
            if st.session_state.multi_object_list:
                st.markdown("**Current Objects:**")
                for idx, obj_data in enumerate(st.session_state.multi_object_list):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"• {obj_data['object']}")
                    with col2:
                        st.write(f"Priority: {obj_data['priority']}")
                    with col3:
                        if st.button("❌", key=f"remove_obj_{idx}"):
                            st.session_state.multi_object_list.pop(idx)
                            st.rerun()
            else:
                st.info("Add objects above to begin")
            
            # Search parameters
            col1, col2 = st.columns(2)
            with col1:
                top_k = st.number_input("Top K Results", min_value=5, max_value=50, value=20, step=5, key="multi_top_k")
            with col2:
                frame_interval = st.number_input("Frame Interval (seconds)", min_value=0.1, max_value=5.0, value=0.5, step=0.1, key="multi_frame_interval")
            
            # Search button
            search_button = st.button(
                "🎯 Search with Priorities", 
                type="primary",
                use_container_width=True,
                disabled=len(st.session_state.multi_object_list) == 0
            )
            
            if len(st.session_state.multi_object_list) == 0:
                st.warning("⚠️ Add at least one object to search")
        
        elif st.session_state.search_mode == "Auto Analysis":
            # Auto Analysis mode
            st.info("🤖 **Automatic Video Analysis**: Automatically analyze the entire video, generate summaries, and cluster segments. No keywords needed!")
            
            col1, col2 = st.columns(2)
            with col1:
                segment_duration = st.number_input(
                    "Segment Duration (seconds)",
                    min_value=2.0,
                    max_value=30.0,
                    value=5.0,
                    step=1.0,
                    key="auto_segment_duration",
                    help="Duration of each segment to analyze"
                )
            with col2:
                overlap = st.number_input(
                    "Overlap (seconds)",
                    min_value=0.0,
                    max_value=5.0,
                    value=1.0,
                    step=0.5,
                    key="auto_overlap",
                    help="Overlap between consecutive segments"
                )
            
            st.info("💡 The number of clusters will be automatically determined based on the video content using silhouette score analysis.")
            
            st.warning("⏱️ This may take several minutes for long videos. Please be patient.")
            
            analyze_button = st.button(
                "🤖 Analyze Video Automatically",
                type="primary",
                use_container_width=True
            )
            
            if analyze_button:
                video_id = st.session_state.uploaded_video_id
                if not video_id:
                    st.error("❌ Please upload a video first")
                else:
                    with st.spinner("🔄 Analyzing video... This may take a while..."):
                        try:
                            endpoint = f"{api_base_url}/analyze-video-auto/{video_id}"
                            params = {
                                "segment_duration": segment_duration,
                                "overlap": overlap
                            }
                            response = requests.post(endpoint, params=params, timeout=600)
                            
                            if response.status_code == 200:
                                data = response.json()
                                st.session_state.auto_analysis_results = data
                                st.session_state.selected_video = video_id
                                st.session_state.current_video_name = st.session_state.uploaded_video_name
                                st.success(f"✅ Analysis complete! Found {data.get('total_segments', 0)} segments in {data.get('n_clusters', 0)} clusters.")
                                st.rerun()
                            else:
                                st.error(f"❌ Analysis failed: {response.status_code} - {response.text}")
                        except requests.exceptions.Timeout:
                            st.error("❌ Analysis timed out. The video might be too long. Try reducing segment duration or overlap.")
                        except Exception as e:
                            st.error(f"❌ Error during analysis: {str(e)}")
        
        elif st.session_state.search_mode == "Object Detection":
            # Object Detection mode - show all parameters
            col1, col2, col3 = st.columns([4, 2, 1.5])
            
            with col1:
                query = st.text_input(
                    "Enter your search query:",
                    key="search_query",
                    placeholder="e.g., 'car' or 'person'",
                    help="Enter the object you want to detect"
                )
            
            with col2:
                frame_interval_text = st.text_input(
                    "Frame Precision (seconds):",
                    value="5.0",
                    help="Enter any positive value (e.g., 0.01 for ultra-high precision, 10.0 for very low precision)"
                )
            
            with col3:
                top_k_text = st.text_input(
                    "Results:",
                    value="10",
                    help="Number of results to return"
                )
                try:
                    top_k = int(top_k_text)
                except:
                    top_k = 10
            
            # Search button in full width below
            search_button = st.button(
                "🔍 Search", 
                type="primary",
                use_container_width=True
            )
        
        else:
            # Action Detection mode - with user parameters
            query = st.text_input(
                "Enter your action query:",
                key="search_query",
                placeholder="e.g., 'person running' or 'drone landing'",
                help="Describe the action you want to find"
            )
            
            col1, col2, col3, col4 = st.columns([3, 2, 1.5, 1.5])
            
            with col1:
                clip_duration_text = st.text_input(
                    "Clip Duration (seconds):",
                    value="20.0",
                    help="Duration of each temporal window to analyze"
                )
            
            with col2:
                overlap_text = st.text_input(
                    "Overlap (seconds):",
                    value="10.0",
                    help="Overlap between consecutive windows"
                )
            
            with col3:
                num_frames_text = st.text_input(
                    "Frames/Clip:",
                    value="8",
                    help="⚠️ X-CLIP model requires exactly 8 frames (fixed in pre-trained model)"
                )
            
            with col4:
                top_k_text = st.text_input(
                    "Results:",
                    value="10",
                    help="Number of action segments to return"
                )
            
            # Search button in full width below
            search_button = st.button(
                "🎬 Search", 
                type="primary",
                use_container_width=True
            )
            
            # Convert text inputs to numbers
            try:
                clip_duration = float(clip_duration_text)
            except:
                clip_duration = 20.0
            
            try:
                overlap = float(overlap_text)
            except:
                overlap = 10.0
            
            try:
                num_frames = int(num_frames_text)
                if num_frames != 8:
                    st.warning(f"⚠️ X-CLIP requires exactly 8 frames. Your input ({num_frames}) will be changed to 8.")
                    num_frames = 8
            except:
                num_frames = 8
            
            try:
                top_k = int(top_k_text)
            except:
                top_k = 10
    
    # Only perform search if video is uploaded and processed
    if st.session_state.get('processing_status') == 'completed' and st.session_state.get('uploaded_video_id'):
    
        # Perform search (only if we have an uploaded video)
        if search_button and st.session_state.get('uploaded_video_id'):
            search_mode = st.session_state.search_mode
            
            # Check if we have query or objects based on mode
            if search_mode == "Multi-Object Priority":
                if not st.session_state.multi_object_list:
                    st.warning("⚠️ Please add at least one object to search")
                    continue_search = False
                else:
                    continue_search = True
            else:
                if not query:
                    st.warning("⚠️ Please enter a search query")
                    continue_search = False
                else:
                    continue_search = True
            
            if continue_search and search_mode == "Object Detection":
                try:
                    frame_interval = float(frame_interval_text) if frame_interval_text else 5.0
                    if frame_interval <= 0:
                        st.error("⚠️ Frame interval must be positive")
                        continue_search = False
                except ValueError:
                    st.error("⚠️ Please enter a valid number (e.g., 0.5)")
                    continue_search = False
            
            if continue_search:
                with st.spinner(f"{'🔍 Searching for objects...' if search_mode == 'Object Detection' else ('🎬 Detecting actions...' if search_mode == 'Action Detection' else '🎯 Searching with priorities...')}"):
                    try:
                        if search_mode == "Multi-Object Priority":
                            endpoint = f"{api_base_url}/search/multi-object/{st.session_state.uploaded_video_id}"
                            objects_data = [
                                {"object": obj['object'], "priority": obj['priority']}
                                for obj in st.session_state.multi_object_list
                            ]
                            request_data = {
                                "objects": objects_data,
                                "top_k": top_k,
                                "frame_interval": frame_interval
                            }
                            response = requests.post(endpoint, json=request_data, timeout=120)
                        else:
                            if search_mode == "Object Detection":
                                endpoint = f"{api_base_url}/search/video/{st.session_state.uploaded_video_id}"
                                params = {
                                    "q": query,
                                    "top_k": top_k,
                                    "frame_interval": frame_interval
                                }
                            else:
                                endpoint = f"{api_base_url}/search/action/{st.session_state.uploaded_video_id}"
                                params = {
                                    "q": query,
                                    "top_k": top_k,
                                    "clip_duration": clip_duration,
                                    "overlap": overlap,
                                    "num_frames": num_frames
                                }
                            response = requests.get(endpoint, params=params, timeout=120)
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            if isinstance(data, dict) and data.get('error'):
                                st.error(f"❌ Backend Error: {data['error']}")
                                st.session_state.search_results = None
                            elif data.get('results') and len(data['results']) > 0:
                                st.session_state.search_results = data
                                st.session_state.current_query = data.get('query', query)
                                st.session_state.selected_video = st.session_state.uploaded_video_id
                                st.session_state.current_video_name = st.session_state.uploaded_video_name
                                st.session_state.current_segment = 0
                                first_result = data['results'][0]
                                st.session_state.target_segment_time = first_result.get('segment_start_seconds') or first_result.get('timestamp_seconds', 0)
                            else:
                                st.warning("🔍 Search completed - No results found. Try different inputs.")
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
    
    # Video player section - display when a video is selected (after search)
    if st.session_state.selected_video:
        st.markdown("---")
        
        if st.button("← Back to Search", type="primary"):
            st.session_state.selected_video = None
            st.session_state.current_segment = 0
            st.session_state.target_segment_time = None
            st.rerun()
        
        # Check if this is multi-object priority search
        is_multi_object = (st.session_state.search_mode == "Multi-Object Priority" and 
                          st.session_state.search_results and 
                          st.session_state.search_results.get('search_type') == 'multi_object_priority')
        
        # Check if this is auto analysis
        is_auto_analysis = (st.session_state.search_mode == "Auto Analysis" and 
                           st.session_state.auto_analysis_results)
        
        if is_multi_object:
            # For multi-object, show visualizations first, then video player
            display_multi_object_visualizations(st.session_state.search_results, api_base_url)
            st.markdown("---")
        elif is_auto_analysis:
            # For auto analysis, show interactive keyword visualization
            display_auto_analysis_visualization(st.session_state.auto_analysis_results, api_base_url)
            st.markdown("---")
        
        display_video_player(st.session_state.selected_video, api_base_url)
        
        # Display segment cards below the video player (reduced spacing)
        st.markdown("<div style='margin-top: -20px;'></div>", unsafe_allow_html=True)
        if st.session_state.search_results:
            display_segment_cards(st.session_state.search_results, st.session_state.current_query, api_base_url)
        
def display_segment_cards(data, query, api_base_url):
    """Display search results as segment cards below the video player."""
    results = data.get("results", [])
    
    if not results:
        st.warning("No results found. Try a different query.")
        return
    
    # Enhanced search results header
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px 30px; border-radius: 16px; margin: 20px 0; box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);'>
        <div style='display: flex; align-items: center; justify-content: space-between;'>
            <div style='flex: 1;'>
                <h2 style='color: white; margin: 0; font-size: 2em; font-weight: 700; letter-spacing: -0.5px;'>
                    🎬 Search Results
                </h2>
                <div style='margin-top: 8px; display: flex; align-items: center; gap: 10px;'>
                    <span style='color: rgba(255,255,255,0.7); font-size: 0.9em; font-weight: 500;'>Query:</span>
                    <span style='color: white; font-size: 1.15em; font-weight: 600; background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 6px;'>"{query}"</span>
                </div>
            </div>
            <div style='background: rgba(255,255,255,0.2); padding: 20px 30px; border-radius: 12px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.3); min-width: 120px;'>
                <div style='color: white; font-size: 2.5em; font-weight: 700; text-align: center; line-height: 1;'>{len(results)}</div>
                <div style='color: rgba(255,255,255,0.85); font-size: 0.95em; text-align: center; margin-top: 5px; font-weight: 500; letter-spacing: 0.5px;'>SEGMENTS</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
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
                
                # Add button to jump to segment
                if st.button(f"Segment {i + 1}", key=f"segment_{video_id}_{i}", type="primary"):
                    st.session_state.current_segment = i
                    # Set target time to jump to this segment
                    segment_time = result.get('segment_start_seconds') or result.get('timestamp_seconds', 0)
                    st.session_state.target_segment_time = segment_time
                    st.rerun()
        
        st.markdown("---")

def display_gallery(data, query, api_base_url):
    """Display search results as a gallery (legacy function - not used in new flow)."""
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
    # Handle both regular search and auto-analysis modes
    if st.session_state.search_mode == "Auto Analysis" and st.session_state.auto_analysis_results:
        # For auto-analysis, we don't need segment navigation in the same way
        # Just show the video player
        video_url = f"{api_base_url}/video/{video_id}/file"
        st.video(video_url)
        return
    
    # For regular search modes
    if not st.session_state.search_results:
        st.error("No search results found for this video.")
        return
    
    search_results = st.session_state.search_results.get("results", [])
    if not search_results:
        st.error("No search results found for this video.")
        return
    
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
    
    # Video player
    try:
        # Format segment time range
        segment_start = current_result.get('segment_start_seconds', 0)
        segment_end = current_result.get('segment_end_seconds', segment_start)
        
        # Convert seconds to MM:SS format
        start_mins, start_secs = divmod(int(segment_start), 60)
        end_mins, end_secs = divmod(int(segment_end), 60)
        time_range = f"{start_mins}:{start_secs:02d} → {end_mins}:{end_secs:02d}"
        
        # Video info at the top
        st.info(f"**Video:** {video_name} | **Current Segment:** {st.session_state.current_segment + 1} of {len(video_results)} | **Time:** {time_range}")
        
        # Get current segment info for initial seek
        if st.session_state.target_segment_time is not None:
            initial_time = st.session_state.target_segment_time
        else:
            initial_time = current_result.get('segment_start_seconds') or current_result.get('timestamp_seconds', 0)
        
        # Enhanced HTML5 video player with playback controls and segment boundaries
        video_html = f"""
        <div style="margin: 0;">
            <video id="main-video" controls width="100%" height="600" preload="auto">
                <source src="{video_url}" type="video/mp4">
                Your browser does not support HTML5 video.
            </video>
            
            <!-- Segment progress indicator -->
            <div style="margin-top: 5px; padding: 5px; background: #f0f0f0; border-radius: 4px; text-align: center;">
                <span id="current-time" style="font-weight: bold; color: #2E86AB;">00:00</span>
                <span style="color: #666;"> / </span>
                <span id="segment-range" style="color: #666;">{start_mins}:{start_secs:02d} - {end_mins}:{end_secs:02d}</span>
            </div>
            
            <div style="margin-top: 10px; margin-bottom: 10px; display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; align-items: center; padding: 5px 0;">
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
                
                <button id="replay-segment-btn" onclick="replaySegment()" style="padding: 8px 16px; background: #FF6B6B; color: white; border: none; border-radius: 4px; cursor: pointer;" title="Replay current segment from start">
                    🔄 Replay Segment
                </button>
            </div>
        </div>
        
        <script>
            const video = document.getElementById('main-video');
            const segmentStart = {segment_start};
            const segmentEnd = {segment_end};
            const currentTimeDisplay = document.getElementById('current-time');
            
            function seekTo(time) {{
                if (video.readyState >= 1) {{
                    video.currentTime = time;
                    video.play();
                }}
            }}
            
            function setPlaybackRate(rate) {{
                video.playbackRate = rate;
                // Update button styles
                document.querySelectorAll('button').forEach(btn => {{
                    if (btn.id !== 'replay-segment-btn') {{
                        btn.style.background = '#666';
                    }}
                }});
                event.target.style.background = '#4CAF50';
            }}
            
            function replaySegment() {{
                video.currentTime = segmentStart;
                hasAutoPaused = false; // Reset flag when replaying segment
                video.play();
            }}
            
            // Store video reference globally for segment navigation
            window.sceneLensVideo = video;
            
            // Track if we've already auto-paused for this segment
            let hasAutoPaused = false;
            
            // Auto-seek to target time when video loads
            video.addEventListener('loadedmetadata', function() {{
                if ({initial_time} > 0) {{
                    video.currentTime = {initial_time};
                    hasAutoPaused = false; // Reset flag when loading new segment
                }}
            }});
            
            // Reset auto-pause flag when user manually seeks
            video.addEventListener('seeking', function() {{
                // If user seeks back into the segment, allow auto-pause again
                if (video.currentTime < segmentEnd) {{
                    hasAutoPaused = false;
                }}
            }});
            
            // Allow user to continue playing after auto-pause
            video.addEventListener('play', function() {{
                console.log('User clicked play - allowing continuous playback');
            }});
            
            // Monitor playback and auto-pause at segment end (only once)
            video.addEventListener('timeupdate', function() {{
                const currentTime = video.currentTime;
                
                // Update time display
                const mins = Math.floor(currentTime / 60);
                const secs = Math.floor(currentTime % 60);
                currentTimeDisplay.textContent = mins + ':' + (secs < 10 ? '0' : '') + secs;
                
                // Auto-pause when segment ends (only once per segment)
                if (currentTime >= segmentEnd && !video.paused && !hasAutoPaused) {{
                    video.pause();
                    hasAutoPaused = true; // Mark that we've paused once
                    console.log('Segment ended at', currentTime, '- auto-paused (click play to continue)');
                }}
            }});
            
            // Handle video errors gracefully
            video.addEventListener('error', function() {{
                console.error('Video error:', video.error);
            }});
        </script>
        """
        
        # Navigation buttons on left and right of video
        left_col, video_col, right_col = st.columns([1, 10, 1])
        
        with left_col:
            # Add vertical space to center button at video midpoint
            st.markdown("<div style='height: 250px;'></div>", unsafe_allow_html=True)
            if st.button("Previous Segment", key="nav_prev", help="Go to previous segment", type="primary", use_container_width=True):
                if st.session_state.current_segment > 0:
                    st.session_state.current_segment -= 1
                    new_result = video_results[st.session_state.current_segment]
                    new_time = new_result.get('segment_start_seconds') or new_result.get('timestamp_seconds', 0)
                    st.session_state.target_segment_time = new_time
                    st.rerun()
        
        with video_col:
            st.components.v1.html(video_html, height=750)
        
        with right_col:
            # Add vertical space to center button at video midpoint
            st.markdown("<div style='height: 250px;'></div>", unsafe_allow_html=True)
            if st.button("Next Segment", key="nav_next", help="Go to next segment", type="primary", use_container_width=True):
                if st.session_state.current_segment < len(video_results) - 1:
                    st.session_state.current_segment += 1
                    new_result = video_results[st.session_state.current_segment]
                    new_time = new_result.get('segment_start_seconds') or new_result.get('timestamp_seconds', 0)
                    st.session_state.target_segment_time = new_time
                    st.rerun()
            
                              
    except Exception as e:
        st.error(f"❌ Error loading video: {str(e)}")
    
    # Add JavaScript to control HTML5 video player when navigation buttons are clicked
    if st.session_state.target_segment_time is not None:
        seek_js = f"""
        <script>
            if (window.sceneLensVideo) {{
                window.sceneLensVideo.currentTime = {st.session_state.target_segment_time};
                // Note: hasAutoPaused will be reset by the 'seeking' event listener
            }}
        </script>
        """
        st.components.v1.html(seek_js, height=0)


def create_priority_timeline(results, video_duration):
    """Create timeline visualization for multi-object priority results."""
    if not results:
        return None
    
    segments = []
    for r in results:
        start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        end = r.get('segment_end_seconds', start + 2.0)
        weighted_score = r.get('weighted_score', 0.0)
        objects = r.get('objects_detected', [])
        priorities = r.get('object_priorities', [])
        
        segments.append({
            'start': start,
            'end': end,
            'weighted_score': weighted_score,
            'normalized_score': r.get('score', 0.0),
            'objects': objects,
            'priorities': priorities
        })
    
    fig = go.Figure()
    
    for idx, seg in enumerate(segments):
        color_value = min(255, int(seg['weighted_score'] * 50))
        color = px.colors.sequential.Viridis[color_value] if color_value < 256 else px.colors.sequential.Viridis[-1]
        
        fig.add_trace(go.Scatter(
            x=[seg['start'], seg['end']],
            y=[idx, idx],
            mode='lines+markers',
            line=dict(width=10, color=color),
            marker=dict(size=12),
            name=f"Segment {idx+1}",
            hovertemplate=f"<b>Time:</b> {seg['start']:.1f}s - {seg['end']:.1f}s<br>" +
                         f"<b>Objects:</b> {', '.join(seg['objects'])}<br>" +
                         f"<b>Priorities:</b> {seg['priorities']}<br>" +
                         f"<b>Weighted Score:</b> {seg['weighted_score']:.2f}<br>" +
                         f"<b>Normalized Score:</b> {seg['normalized_score']:.3f}<extra></extra>"
        ))
    
    fig.update_layout(
        title="Priority-Weighted Detection Timeline",
        xaxis_title="Time (seconds)",
        yaxis_title="Detection Index",
        height=400,
        showlegend=False,
        hovermode='closest'
    )
    
    return fig


def create_multi_object_heatmap(results, objects, video_duration):
    """Create heatmap showing which objects detected at which times."""
    if not results or not objects:
        return None
    
    bins = np.linspace(0, video_duration, 50)
    heatmap_data = {obj: np.zeros(len(bins) - 1) for obj in objects}
    
    for r in results:
        start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        end = r.get('segment_end_seconds', start + 2.0)
        detected_objects = r.get('objects_detected', [])
        priorities = r.get('object_priorities', [])
        
        start_bin = np.digitize([start], bins)[0] - 1
        end_bin = np.digitize([end], bins)[0]
        
        for obj, priority in zip(detected_objects, priorities):
            if obj in heatmap_data:
                for bin_idx in range(max(0, start_bin), min(len(bins) - 1, end_bin)):
                    heatmap_data[obj][bin_idx] += priority
    
    z_data = [heatmap_data[obj] for obj in objects]
    x_labels = [f"{(bins[i] + bins[i+1])/2:.1f}s" for i in range(len(bins) - 1)]
    
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=x_labels,
        y=objects,
        colorscale='Viridis',
        hovertemplate='Object: %{y}<br>Time: %{x}<br>Priority Weight: %{z}<extra></extra>'
    ))
    
    fig.update_layout(
        title="Multi-Object Detection Heatmap (Priority-Weighted)",
        xaxis_title="Time (seconds)",
        yaxis_title="Object",
        height=300 + len(objects) * 30
    )
    
    return fig


def create_weighted_score_chart(results):
    """Create line chart showing weighted score over time."""
    if not results:
        return None
    
    timestamps = [r.get('segment_start_seconds', r.get('timestamp_seconds', 0)) for r in results]
    weighted_scores = [r.get('weighted_score', 0.0) for r in results]
    normalized_scores = [r.get('score', 0.0) for r in results]
    object_counts = [len(r.get('objects_detected', [])) for r in results]
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=weighted_scores,
            mode='lines+markers',
            name='Weighted Score',
            line=dict(color='blue', width=2),
            marker=dict(size=8)
        ),
        secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=normalized_scores,
            mode='markers',
            name='Normalized Score',
            marker=dict(
                size=[c * 5 + 5 for c in object_counts],
                color=normalized_scores,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Normalized Score")
            ),
            hovertemplate='Time: %{x:.1f}s<br>Normalized: %{y:.3f}<br>Objects: %{customdata}<extra></extra>',
            customdata=object_counts
        ),
        secondary_y=True
    )
    
    fig.update_xaxes(title_text="Time (seconds)")
    fig.update_yaxes(title_text="Weighted Score", secondary_y=False)
    fig.update_yaxes(title_text="Normalized Score", secondary_y=True)
    
    fig.update_layout(
        title="Priority-Weighted Score Over Time",
        height=400,
        hovermode='closest'
    )
    
    return fig


def create_cooccurrence_matrix(results, objects):
    """Create matrix showing object co-occurrence."""
    if not results or not objects:
        return None
    
    cooccurrence = np.zeros((len(objects), len(objects)))
    
    for r in results:
        detected = r.get('objects_detected', [])
        priorities = r.get('object_priorities', [])
        
        for i, obj1 in enumerate(detected):
            for j, obj2 in enumerate(detected):
                if i != j:
                    idx1 = objects.index(obj1) if obj1 in objects else -1
                    idx2 = objects.index(obj2) if obj2 in objects else -1
                    if idx1 >= 0 and idx2 >= 0:
                        weight = priorities[i] * priorities[j] if i < len(priorities) and j < len(priorities) else 1
                        cooccurrence[idx1][idx2] += weight
    
    fig = go.Figure(data=go.Heatmap(
        z=cooccurrence,
        x=objects,
        y=objects,
        colorscale='Blues',
        hovertemplate='%{y} & %{x}<br>Co-occurrence Weight: %{z:.1f}<extra></extra>'
    ))
    
    fig.update_layout(
        title="Object Co-occurrence Matrix (Priority-Weighted)",
        xaxis_title="Object",
        yaxis_title="Object",
        height=400 + len(objects) * 30,
        width=400 + len(objects) * 30
    )
    
    return fig


def display_multi_object_visualizations(data, api_base_url):
    """Display informative visualizations for multi-object priority search results."""
    results = data.get("results", [])
    
    if not results:
        st.warning("No results to visualize")
        return
    
    # Debug: Show what data we have
    if st.checkbox("🔍 Debug: Show raw data structure", key="debug_multi_object"):
        st.json(results[0] if results else {})
        st.write(f"Total results: {len(results)}")
        if results:
            st.write("Available keys in first result:", list(results[0].keys()))
    
    # Extract objects and priorities from session state
    objects = [obj['object'] for obj in st.session_state.multi_object_list]
    priorities = {obj['object']: obj['priority'] for obj in st.session_state.multi_object_list}
    
    st.markdown("---")
    
    st.header("Multi-Object Priority Analysis")
    
    # === SUMMARY STATISTICS ===
    st.subheader("Summary Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    total_segments = len(results)
    total_objects = len(objects)
    
    # Calculate detection counts per object
    detection_counts = {}
    total_coverage = 0
    for obj in objects:
        # Handle both list and string formats
        obj_detections = []
        for r in results:
            detected = r.get('objects_detected', [])
            if isinstance(detected, list) and obj in detected:
                obj_detections.append(r)
            elif isinstance(detected, str) and obj in detected:
                obj_detections.append(r)
        detection_counts[obj] = len(obj_detections)
    
    # Calculate total coverage time
    covered_segments = set()
    for r in results:
        start = r.get('segment_start_seconds', 0)
        end = r.get('segment_end_seconds', start + 2.0)
        # Simple coverage calculation (could be improved with proper merging)
        total_coverage += (end - start)
    
    with col1:
        st.metric("Total Segments Found", total_segments)
    with col2:
        st.metric("Objects Searched", total_objects)
    with col3:
        st.metric("Total Coverage", f"{total_coverage:.1f}s")
    with col4:
        avg_score = np.mean([r.get('score', 0) for r in results]) if results else 0
        st.metric("Avg Score", f"{avg_score:.3f}")
    
    st.markdown("---")
    
    # === OBJECT DETECTION STATISTICS ===
    st.subheader("Detection Statistics by Object")
    
    stats_data = []
    for obj in objects:
        # Handle both list and string formats for objects_detected
        obj_results = []
        for r in results:
            detected = r.get('objects_detected', [])
            if isinstance(detected, list) and obj in detected:
                obj_results.append(r)
            elif isinstance(detected, str) and obj in detected:
                obj_results.append(r)
        
        if obj_results:
            # Calculate statistics
            detection_count = len(obj_results)
            
            # Get raw scores safely
            raw_scores_list = []
            for r in obj_results:
                raw_scores = r.get('raw_scores', [])
                if raw_scores and isinstance(raw_scores, list) and len(raw_scores) > 0:
                    # Find the score for this object
                    detected = r.get('objects_detected', [])
                    if isinstance(detected, list) and obj in detected:
                        obj_idx = detected.index(obj)
                        if obj_idx < len(raw_scores):
                            raw_scores_list.append(raw_scores[obj_idx])
                    elif isinstance(detected, str):
                        raw_scores_list.append(raw_scores[0] if raw_scores else 0)
            
            avg_score = np.mean([r.get('score', 0.0) for r in obj_results])
            max_score = max([r.get('score', 0.0) for r in obj_results]) if obj_results else 0.0
            
            # Find time range
            times = [r.get('segment_start_seconds', r.get('timestamp_seconds', 0)) for r in obj_results]
            first_appearance = min(times) if times else 0
            last_appearance = max(times) if times else 0
            
            stats_data.append({
                'Object': obj,
                'Priority': priorities.get(obj, 0),
                'Detections': detection_count,
                'First Appears (s)': f"{first_appearance:.1f}",
                'Last Appears (s)': f"{last_appearance:.1f}",
                'Avg Score': f"{avg_score:.3f}",
                'Max Score': f"{max_score:.3f}"
            })
        else:
            stats_data.append({
                'Object': obj,
                'Priority': priorities.get(obj, 0),
                'Detections': 0,
                'First Appears (s)': "N/A",
                'Last Appears (s)': "N/A",
                'Avg Score': "N/A",
                'Max Score': "N/A"
            })
    
    stats_df = pd.DataFrame(stats_data)
    st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    # Bar chart showing detection counts
    if any(detection_counts.values()):
        fig_counts = go.Figure()
        fig_counts.add_trace(go.Bar(
            x=list(detection_counts.keys()),
            y=list(detection_counts.values()),
            marker_color='steelblue',
            text=list(detection_counts.values()),
            textposition='outside',
            hovertemplate='Object: %{x}<br>Detections: %{y}<br>Priority: %{customdata}<extra></extra>',
            customdata=[priorities.get(obj, 0) for obj in detection_counts.keys()]
        ))
        fig_counts.update_layout(
            title="Detection Count by Object",
            xaxis_title="Object",
            yaxis_title="Number of Detections",
            height=400
        )
        st.plotly_chart(fig_counts, use_container_width=True, key="detection_counts_chart")
    
    st.markdown("---")
    
    # === TOP SEGMENTS WITH DETAILS ===
    st.subheader("Top Segments (Ranked by Weighted Score)")
    
    top_segments_data = []
    for i, r in enumerate(results[:10], 1):  # Top 10
        start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        end = r.get('segment_end_seconds', start + 2.0)
        detected_objs = r.get('objects_detected', [])
        obj_priorities = r.get('object_priorities', [])
        raw_scores = r.get('raw_scores', [])
        
        # Handle list/string formats
        if isinstance(detected_objs, str):
            detected_objs = [detected_objs]
        if not isinstance(detected_objs, list):
            detected_objs = []
        
        if not isinstance(obj_priorities, list):
            obj_priorities = []
        if not isinstance(raw_scores, list):
            raw_scores = []
        
        top_segments_data.append({
            'Rank': i,
            'Time Range (s)': f"{start:.1f} - {end:.1f}",
            'Duration (s)': f"{end - start:.1f}",
            'Objects': ", ".join(detected_objs) if detected_objs else "None",
            'Priorities': ", ".join([str(p) for p in obj_priorities]) if obj_priorities else "N/A",
            'Score': f"{r.get('score', 0):.2f}"
        })
    
    top_segments_df = pd.DataFrame(top_segments_data)
    st.dataframe(top_segments_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # === TEMPORAL DISTRIBUTION ===
    st.subheader("Temporal Distribution of Detections")
    
    # Create timeline showing when each object appears
    fig_temporal = go.Figure()
    
    colors = px.colors.qualitative.Set3
    for idx, obj in enumerate(objects):
        obj_results = [r for r in results if obj in r.get('objects_detected', [])]
        if obj_results:
            timestamps = [r.get('segment_start_seconds', 0) for r in obj_results]
            scores = [r.get('score', 0) for r in obj_results]  # Use normalized score
            
            fig_temporal.add_trace(go.Scatter(
                x=timestamps,
                y=[idx] * len(timestamps),
                mode='markers',
                name=f"{obj} (P{priorities.get(obj, 0)})",
                marker=dict(
                    size=[s * 100 + 10 for s in scores],  # Scale for normalized scores (0-1)
                    color=colors[idx % len(colors)],
                    opacity=0.7,
                    line=dict(width=1, color='black')
                ),
                hovertemplate=f'<b>{obj}</b> (Priority {priorities.get(obj, 0)})<br>' +
                             'Time: %{x:.1f}s<br>' +
                             'Score: %{customdata:.3f}<extra></extra>',
                customdata=scores
            ))
    
    fig_temporal.update_layout(
        title="When Each Object Appears in Video (Marker Size = Score)",
        xaxis_title="Time (seconds)",
        yaxis_title="Object",
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(len(objects))),
            ticktext=[f"{obj} (P{priorities.get(obj, 0)})" for obj in objects]
        ),
        height=300 + len(objects) * 40,
        hovermode='closest'
    )
    st.plotly_chart(fig_temporal, use_container_width=True, key="temporal_distribution_chart")
    
    st.markdown("---")
    
    # === PRIORITY IMPACT ANALYSIS ===
    st.subheader("Priority Impact Analysis")
    
    # Show how priority affects ranking
    priority_impact_data = []
    for obj in objects:
        # Handle both list and string formats
        obj_results = []
        for r in results:
            detected = r.get('objects_detected', [])
            if isinstance(detected, list) and obj in detected:
                obj_results.append(r)
            elif isinstance(detected, str) and obj in detected:
                obj_results.append(r)
        
        if obj_results:
            # Find segments where this object appears and check its rank
            segments_with_obj = []
            for r in results:
                detected = r.get('objects_detected', [])
                if isinstance(detected, list) and obj in detected:
                    obj_idx = detected.index(obj)
                    raw_scores = r.get('raw_scores', [])
                    raw_score = raw_scores[obj_idx] if raw_scores and obj_idx < len(raw_scores) else 0.0
                    weighted_contribution = raw_score * priorities.get(obj, 0)
                    segments_with_obj.append({
                        'segment_rank': results.index(r) + 1,
                        'raw_score': raw_score,
                        'weighted_contribution': weighted_contribution
                    })
                elif isinstance(detected, str) and obj in detected:
                    raw_scores = r.get('raw_scores', [])
                    raw_score = raw_scores[0] if raw_scores and len(raw_scores) > 0 else 0.0
                    weighted_contribution = raw_score * priorities.get(obj, 0)
                    segments_with_obj.append({
                        'segment_rank': results.index(r) + 1,
                        'raw_score': raw_score,
                        'weighted_contribution': weighted_contribution
                    })
            
            avg_rank = np.mean([s['segment_rank'] for s in segments_with_obj]) if segments_with_obj else 0
            avg_score = np.mean([r.get('score', 0.0) for r in obj_results]) if obj_results else 0.0
            
            priority_impact_data.append({
                'Object': obj,
                'Priority': priorities.get(obj, 0),
                'Detections': len(obj_results),
                'Avg Segment Rank': f"{avg_rank:.1f}",
                'Avg Score': f"{avg_score:.3f}"
            })
    
    if priority_impact_data:
        impact_df = pd.DataFrame(priority_impact_data)
        st.dataframe(impact_df, use_container_width=True, hide_index=True)
        
        # Bar chart showing priority impact
        fig_impact = go.Figure()
        fig_impact.add_trace(go.Bar(
            x=[d['Object'] for d in priority_impact_data],
            y=[float(d['Avg Score'].replace('N/A', '0')) for d in priority_impact_data],
            marker_color='coral',
            text=[d['Priority'] for d in priority_impact_data],
            textposition='outside',
            hovertemplate='Object: %{x}<br>Avg Score: %{y:.3f}<br>Priority: %{text}<extra></extra>'
        ))
        fig_impact.update_layout(
            title="Average Score by Object (Priority Impact)",
            xaxis_title="Object",
            yaxis_title="Average Score",
            height=400
        )
        st.plotly_chart(fig_impact, use_container_width=True, key="priority_impact_chart")
    
    st.markdown("---")
    
    # === COMPLETE RESULTS TABLE ===
    st.subheader("Complete Results Table")
    
    complete_results_data = []
    for i, r in enumerate(results, 1):
        start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        end = r.get('segment_end_seconds', start + 2.0)
        detected_objs = r.get('objects_detected', [])
        
        # Handle both list and string formats
        if isinstance(detected_objs, list):
            objects_str = ", ".join(detected_objs)
        elif isinstance(detected_objs, str):
            objects_str = detected_objs
        else:
            objects_str = "Unknown"
        
        raw_scores = r.get('raw_scores', [])
        if isinstance(raw_scores, list):
            raw_scores_str = str([f"{s:.2f}" for s in raw_scores])
        else:
            raw_scores_str = "N/A"
        
        complete_results_data.append({
            'Rank': i,
            'Time (s)': f"{start:.1f}",
            'Duration (s)': f"{end - start:.1f}",
            'Objects': objects_str if objects_str else "None",
            'Score': f"{r.get('score', 0):.2f}"
        })
    
    complete_df = pd.DataFrame(complete_results_data)
    st.dataframe(complete_df, use_container_width=True, hide_index=True)


def display_cluster_visualizations(clustered_segments, cluster_stats, objects, priorities):
    """Display visualizations based on BLIP-2 summaries and clustering."""
    if not clustered_segments or not cluster_stats:
        st.warning("⚠️ No cluster data available. Please run summarization and clustering first.")
        if st.checkbox("Debug: Show cluster data", key="debug_cluster"):
            st.json({
                "clustered_segments_count": len(clustered_segments) if clustered_segments else 0,
                "cluster_stats": cluster_stats,
                "sample_segment": clustered_segments[0] if clustered_segments else None
            })
        return
    
    st.header("Cluster-Based Analysis (BLIP-2 Summaries)")
    
    # Cluster statistics
    st.subheader("Cluster Overview")
    if not cluster_stats:
        st.warning("No cluster statistics available")
        return
    
    if len(cluster_stats) == 0:
        st.error("No clusters found. Check if clustering completed successfully.")
        return
    
    cluster_cols = st.columns(len(cluster_stats))
    
    for idx, (cluster_id, stats) in enumerate(sorted(cluster_stats.items())):
        with cluster_cols[idx]:
            keywords_str = ', '.join(stats.get('keywords', [])) if stats.get('keywords') else 'None'
            st.metric(
                f"Cluster {cluster_id}",
                f"{stats.get('count', 0)} segments",
                help=f"Keywords: {keywords_str}"
            )
    
    st.markdown("---")
    
    # Cluster details
    st.subheader("Segments by Cluster")
    
    for cluster_id in sorted(cluster_stats.keys()):
        cluster_segs = [s for s in clustered_segments if s.get('cluster_id') == cluster_id]
        keywords = cluster_stats.get(cluster_id, {}).get('keywords', [])
        keywords_str = ', '.join(keywords) if keywords else 'None'
        
        with st.expander(f"Cluster {cluster_id} - {len(cluster_segs)} segments (Keywords: {keywords_str})"):
            cluster_data = []
            for seg in cluster_segs:
                start = seg.get('segment_start_seconds', seg.get('timestamp_seconds', 0))
                end = seg.get('segment_end_seconds', start + 2.0)
                summary = seg.get('blip2_summary', 'No summary')
                detected_objs = seg.get('objects_detected', [])
                
                cluster_data.append({
                    'Time (s)': f"{start:.1f} - {end:.1f}",
                    'Duration (s)': f"{end - start:.1f}",
                    'BLIP-2 Summary': summary,
                    'Objects': ', '.join(detected_objs),
                    'Weighted Score': f"{seg.get('weighted_score', 0):.2f}"
                })
            
            if cluster_data:
                st.dataframe(pd.DataFrame(cluster_data), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # Temporal distribution by cluster
    st.subheader("Temporal Distribution by Cluster")
    
    fig_cluster_temporal = go.Figure()
    
    colors = px.colors.qualitative.Set3
    for cluster_id in sorted(cluster_stats.keys()):
        cluster_segs = [s for s in clustered_segments if s.get('cluster_id') == cluster_id]
        if cluster_segs:
            timestamps = [s.get('segment_start_seconds', s.get('timestamp_seconds', 0)) for s in cluster_segs]
            scores = [s.get('weighted_score', 0) for s in cluster_segs]
            
            fig_cluster_temporal.add_trace(go.Scatter(
                x=timestamps,
                y=[cluster_id] * len(timestamps),
                mode='markers',
                name=f"Cluster {cluster_id}",
                marker=dict(
                    size=[s * 10 + 5 for s in scores],
                    color=colors[cluster_id % len(colors)],
                    opacity=0.7
                ),
                hovertemplate=f'<b>Cluster {cluster_id}</b><br>' +
                             'Time: %{x:.1f}s<br>' +
                             'Score: %{customdata:.2f}<br>' +
                             'Summary: %{text}<extra></extra>',
                customdata=scores,
                text=[s.get('blip2_summary', '')[:50] for s in cluster_segs]
            ))
    
    fig_cluster_temporal.update_layout(
        title="Segment Clusters Over Time (Marker Size = Weighted Score)",
        xaxis_title="Time (seconds)",
        yaxis_title="Cluster ID",
        height=400,
        hovermode='closest'
    )
    st.plotly_chart(fig_cluster_temporal, use_container_width=True, key="cluster_temporal_chart")
    
    st.markdown("---")
    
    # Cluster comparison
    st.subheader("Cluster Comparison")
    
    comparison_data = []
    for cluster_id, stats in cluster_stats.items():
        cluster_segs = [s for s in clustered_segments if s.get('cluster_id') == cluster_id]
        if cluster_segs:
            avg_score = np.mean([s.get('weighted_score', 0) for s in cluster_segs])
            avg_duration = np.mean([s.get('segment_end_seconds', 0) - s.get('segment_start_seconds', 0) for s in cluster_segs])
            
            comparison_data.append({
                'Cluster': cluster_id,
                'Segment Count': stats['count'],
                'Avg Weighted Score': f"{avg_score:.2f}",
                'Avg Duration (s)': f"{avg_duration:.1f}",
                'Keywords': ', '.join(stats['keywords'])
            })
    
    if comparison_data:
        st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)
        
        # Bar chart
        fig_comparison = go.Figure()
        fig_comparison.add_trace(go.Bar(
            x=[d['Cluster'] for d in comparison_data],
            y=[float(d['Avg Weighted Score']) for d in comparison_data],
            marker_color='steelblue',
            text=[d['Segment Count'] for d in comparison_data],
            textposition='outside',
            hovertemplate='Cluster: %{x}<br>Avg Score: %{y:.2f}<br>Segments: %{text}<extra></extra>'
        ))
        fig_comparison.update_layout(
            title="Average Weighted Score by Cluster",
            xaxis_title="Cluster",
            yaxis_title="Average Weighted Score",
            height=400
        )
        st.plotly_chart(fig_comparison, use_container_width=True, key="cluster_comparison_chart")


def display_auto_analysis_visualization(data, api_base_url):
    """Display interactive keyword/cluster visualization for auto analysis."""
    segments = data.get('segments', [])
    cluster_stats = data.get('cluster_statistics', {})
    n_clusters = data.get('n_clusters', 0)
    total_segments = data.get('total_segments', 0)
    
    if not segments:
        st.warning("No segments found in analysis results.")
        return
    
    st.header("Interactive Keyword & Cluster Visualization")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Segments", total_segments)
    with col2:
        st.metric("Clusters", n_clusters)
    with col3:
        avg_segments_per_cluster = total_segments / n_clusters if n_clusters > 0 else 0
        st.metric("Avg Segments/Cluster", f"{avg_segments_per_cluster:.1f}")
    with col4:
        video_duration = data.get('video_duration', 0)
        st.metric("Video Duration", f"{video_duration:.1f}s")
    
    st.markdown("---")
    
    # Create keyword/cluster selection interface
    st.subheader("Explore Clusters by Keywords")
    
    # Build keyword list from all clusters
    all_keywords = []
    keyword_to_clusters = {}
    for cluster_id, stats in cluster_stats.items():
        keywords = stats.get('keywords', [])
        if keywords:  # Only process if keywords exist
            for keyword in keywords:
                if keyword and keyword.strip():  # Only add non-empty keywords
                    if keyword not in keyword_to_clusters:
                        keyword_to_clusters[keyword] = []
                    keyword_to_clusters[keyword].append(cluster_id)
                    all_keywords.append(keyword)
    
    # Remove duplicates while preserving order
    unique_keywords = []
    seen = set()
    for kw in all_keywords:
        if kw not in seen:
            unique_keywords.append(kw)
            seen.add(kw)
    
    # Create keyword buttons in a grid
    if unique_keywords:
        st.markdown("**Click on a keyword to see related segments:**")
        cols_per_row = 5
        for i in range(0, len(unique_keywords), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, keyword in enumerate(unique_keywords[i:i+cols_per_row]):
                with cols[j]:
                    # Create a styled button
                    cluster_ids = keyword_to_clusters.get(keyword, [])
                    segment_count = sum(len([s for s in segments if s.get('cluster_id') == cid]) 
                                       for cid in cluster_ids)
                    if st.button(
                        f"{keyword}\n({segment_count})",
                        key=f"keyword_btn_{keyword}",
                        use_container_width=True,
                        help=f"Show {segment_count} segments for keyword '{keyword}'"
                    ):
                        st.session_state.selected_cluster_keyword = keyword
                        st.rerun()
    
    # Show cluster selection
    st.markdown("---")
    st.subheader("Cluster Overview")
    
    cluster_options = [f"Cluster {cid} ({stats.get('count', 0)} segments)" 
                      for cid, stats in sorted(cluster_stats.items())]
    cluster_options.insert(0, "All Clusters")
    
    selected_cluster_display = st.selectbox(
        "Select a cluster to explore:",
        cluster_options,
        key="cluster_selector"
    )
    
    # Parse selected cluster
    selected_cluster_id = None
    if selected_cluster_display != "All Clusters":
        selected_cluster_id = int(selected_cluster_display.split()[1])
    
    # Filter segments based on selection
    filtered_segments = segments
    if st.session_state.selected_cluster_keyword:
        # Filter by keyword
        keyword = st.session_state.selected_cluster_keyword
        cluster_ids = keyword_to_clusters.get(keyword, [])
        filtered_segments = [s for s in segments if s.get('cluster_id') in cluster_ids]
        st.info(f"Showing segments for keyword: **{keyword}** ({len(filtered_segments)} segments)")
    elif selected_cluster_id is not None:
        # Filter by cluster
        filtered_segments = [s for s in segments if s.get('cluster_id') == selected_cluster_id]
        st.info(f"Showing segments for Cluster {selected_cluster_id} ({len(filtered_segments)} segments)")
    
    # Interactive 2D scatter plot
    st.markdown("---")
    st.subheader("Segment Space Visualization")
    st.markdown("**Hover over points to see details. Points are colored by cluster.**")
    
    # Prepare data for plotting
    plot_data = []
    for seg in filtered_segments:
        cluster_id = seg.get('cluster_id', 0)
        keywords = cluster_stats.get(cluster_id, {}).get('keywords', [])
        main_keyword = keywords[0] if keywords else ''
        
        plot_data.append({
            'x': seg.get('x', 0),
            'y': seg.get('y', 0),
            'cluster_id': cluster_id,
            'keyword': main_keyword,
            'timestamp': seg.get('timestamp_seconds', 0),
            'start': seg.get('segment_start_seconds', 0),
            'end': seg.get('segment_end_seconds', 0),
            'summary': seg.get('blip2_summary', 'No summary'),
            'duration': seg.get('duration', 0),
            'segment_id': seg.get('segment_id', '')
        })
    
    if plot_data:
        df_plot = pd.DataFrame(plot_data)
        
        # Create interactive scatter plot
        fig = px.scatter(
            df_plot,
            x='x',
            y='y',
            color='cluster_id',
            hover_data=['timestamp', 'start', 'end', 'summary', 'keyword'],
            labels={'x': 'Dimension 1', 'y': 'Dimension 2', 'cluster_id': 'Cluster'},
            title="Segment Clusters in 2D Space (t-SNE projection)",
            color_continuous_scale='viridis',
            size_max=15
        )
        
        # Update hover template
        fig.update_traces(
            hovertemplate="<b>Cluster %{marker.color}</b><br>" +
                         "Time: %{customdata[0]:.1f}s<br>" +
                         "Range: %{customdata[1]:.1f}s - %{customdata[2]:.1f}s<br>" +
                         "Keyword: %{customdata[4]}<br>" +
                         "Summary: %{customdata[3]}<extra></extra>",
            marker=dict(size=10, opacity=0.7, line=dict(width=1, color='white'))
        )
        
        fig.update_layout(
            height=600,
            showlegend=True,
            hovermode='closest',
            plot_bgcolor='rgba(240,240,240,0.5)'
        )
        
        st.plotly_chart(fig, use_container_width=True, key="auto_analysis_scatter")
    
    # Display segments in a table
    st.markdown("---")
    st.subheader("Segments Details")
    
    if filtered_segments:
        # Sort by timestamp
        filtered_segments_sorted = sorted(filtered_segments, key=lambda x: x.get('timestamp_seconds', 0))
        
        # Create expandable sections for each cluster
        clusters_in_view = set(s.get('cluster_id') for s in filtered_segments_sorted)
        
        for cluster_id in sorted(clusters_in_view):
            cluster_segs = [s for s in filtered_segments_sorted if s.get('cluster_id') == cluster_id]
            if not cluster_segs:
                continue
            
            stats = cluster_stats.get(cluster_id, {})
            keywords_list = stats.get('keywords', [])
            keywords = ', '.join(keywords_list) if keywords_list else 'No keywords'
            
            with st.expander(f"Cluster {cluster_id} - {len(cluster_segs)} segments | Keywords: {keywords}", expanded=True):
                # Create table data
                table_data = []
                for seg in cluster_segs:
                    table_data.append({
                        'Time (s)': f"{seg.get('segment_start_seconds', 0):.1f} - {seg.get('segment_end_seconds', 0):.1f}",
                        'Duration (s)': f"{seg.get('duration', 0):.1f}",
                        'Summary': seg.get('blip2_summary', 'No summary')[:100] + '...' if len(seg.get('blip2_summary', '')) > 100 else seg.get('blip2_summary', 'No summary'),
                        'Keywords': keywords
                    })
                
                df_table = pd.DataFrame(table_data)
                st.dataframe(df_table, use_container_width=True, hide_index=True)
                
                # Show segment cards
                st.markdown("**Click to jump to segment in video:**")
                cols = st.columns(min(3, len(cluster_segs)))
                for idx, seg in enumerate(cluster_segs):
                    with cols[idx % 3]:
                        start_time = seg.get('segment_start_seconds', 0)
                        end_time = seg.get('segment_end_seconds', 0)
                        summary = seg.get('blip2_summary', 'No summary')
                        
                        with st.container():
                            st.markdown(f"""
                            <div style="border: 1px solid #ddd; border-radius: 8px; padding: 10px; margin: 5px 0; background: #f9f9f9;">
                                <b>{start_time:.1f}s - {end_time:.1f}s</b><br>
                                <small>{summary[:80]}...</small>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button(f"Play Segment", key=f"play_seg_{seg.get('segment_id')}"):
                                st.session_state.target_segment_time = start_time
                                st.rerun()
    else:
        st.info("No segments to display. Try selecting a different keyword or cluster.")
    
    # Reset keyword selection button
    if st.session_state.selected_cluster_keyword:
        if st.button("Clear Keyword Filter", key="clear_keyword_filter"):
            st.session_state.selected_cluster_keyword = None
            st.rerun()


if __name__ == "__main__":
    main()
