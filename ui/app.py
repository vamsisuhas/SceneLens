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

def main():
    """Main Streamlit application."""
    
    # Header
    st.title("🎬 SceneLens - AI Video Search")
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
    
    # Main search interface
    st.header("🔍 Search")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input(
            "Enter your search query:",
            placeholder="e.g., 'blue strip', 'red circle', 'bright colors'",
            key="search_query"
        )
    
    with col2:
        search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    
    # Perform search
    if search_button and query:
        with st.spinner("Searching..."):
            try:
                # Use query-based search endpoint
                endpoint = f"{api_base_url}/search/on-demand"
                
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
                    display_gallery(data, query, api_base_url)
                else:
                    st.error(f"Search failed: {response.status_code} - {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to API. Make sure the backend server is running.")
            except requests.exceptions.Timeout:
                st.error("❌ Search request timed out. Try a simpler query.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Display previous results if available
    elif st.session_state.search_results:
        st.info(f"Showing previous results for: '{st.session_state.current_query}'")
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
    st.markdown(f"**Query:** '{st.session_state.current_query}'")
    st.markdown(f"**Found {len(video_results)} relevant segments**")
    
    # Video player section
    st.subheader("🎥 Video Player")
    
    # Create video player with HTML and JavaScript for seeking
    video_url = f"{api_base_url}/video/{video_id}/file"
    
    # Get current segment info for initial seek
    if not video_results:
        st.error("No video results found.")
        return
    
    # Ensure current_segment is within bounds
    if st.session_state.current_segment >= len(video_results):
        st.session_state.current_segment = 0
    
    current_result = video_results[st.session_state.current_segment]
    initial_time = current_result.get('segment_start_seconds') or current_result.get('timestamp_seconds', 0)
    
    video_html = f"""
    <video id="videoPlayer" width="100%" height="400" controls>
        <source src="{video_url}" type="video/mp4">
        Your browser does not support the video tag.
    </video>
    <script>
        // Auto-seek to current segment time when video loads
        document.addEventListener('DOMContentLoaded', function() {{
            const video = document.getElementById('videoPlayer');
            video.addEventListener('loadedmetadata', function() {{
                video.currentTime = {initial_time};
            }});
        }});
    </script>
    """
    
    st.components.v1.html(video_html, height=450)
    
    # Segment navigation controls
    st.subheader("🎮 Segment Navigation")
    
    # Current segment tracking (already initialized in main())
    pass
    
    # Playback controls
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("⏮️ Previous", use_container_width=True):
            if st.session_state.current_segment > 0:
                st.session_state.current_segment -= 1
                st.rerun()
    
    with col2:
        if st.button("▶️ Play Current", use_container_width=True):
            # This will trigger a rerun and the video will auto-seek to current segment
            st.rerun()
    
    with col3:
        if st.button("⏭️ Next", use_container_width=True):
            if st.session_state.current_segment < len(video_results) - 1:
                st.session_state.current_segment += 1
                st.rerun()
    
    with col4:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.current_segment = 0
            st.rerun()
    
    # Current segment info
    if video_results:
        current_result = video_results[st.session_state.current_segment]
        start_time = current_result.get('segment_start_seconds') or current_result.get('timestamp_seconds', 0)
        end_time = current_result.get('segment_end_seconds')
        if end_time is None:
            end_time = start_time + 2.0
        
        st.info(f"**Current Segment {st.session_state.current_segment + 1}:** {start_time:.1f}s - {end_time:.1f}s (Score: {current_result['score']:.3f})")
    
    # Search result segments timeline
    st.subheader("📊 Query-Specific Segments")
    
    # Create a more interactive segment display
    for i, result in enumerate(video_results):
        with st.container():
            # Highlight current segment
            if i == st.session_state.current_segment:
                st.markdown("**🟢 CURRENT SEGMENT**")
            
            col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
            
            with col1:
                st.markdown(f"**Segment {i+1}**")
                start_time = result.get('segment_start_seconds') or result.get('timestamp_seconds', 0)
                end_time = result.get('segment_end_seconds')
                
                if end_time is None:
                    end_time = start_time + 2.0
                
                start_minutes = int(start_time // 60)
                start_seconds = int(start_time % 60)
                end_minutes = int(end_time // 60)
                end_seconds = int(end_time % 60)
                
                st.markdown(f"{start_minutes}:{start_seconds:02d} - {end_minutes}:{end_seconds:02d}")
            
            with col2:
                # Progress bar for segment
                duration = end_time - start_time
                progress = duration / 10.0  # Assuming 10s video
                st.progress(progress)
                
                # Show score and caption
                st.markdown(f"**Score:** {result['score']:.3f}")
                if result.get('caption'):
                    st.markdown(f"**Caption:** {result['caption']}")
            
            with col3:
                if st.button(f"▶️ Play", key=f"play_segment_{i}"):
                    st.session_state.current_segment = i
                    st.rerun()
            
            with col4:
                if st.button(f"🎯 Jump", key=f"jump_segment_{i}"):
                    st.session_state.current_segment = i
                    st.rerun()
        
        st.markdown("---")
    
    # Timeline visualization
    st.subheader("📈 Timeline Overview")
    
    # Create a simple timeline visualization
    timeline_data = []
    for i, result in enumerate(video_results):
        start_time = result.get('segment_start_seconds') or result.get('timestamp_seconds', 0)
        end_time = result.get('segment_end_seconds')
        if end_time is None:
            end_time = start_time + 2.0
        
        timeline_data.append({
            "segment": i + 1,
            "start": start_time,
            "end": end_time,
            "score": result['score']
        })
    
    # Display timeline as a simple chart
    if timeline_data:
        st.write("**Segment Timeline:**")
        for item in timeline_data:
            # Highlight current segment
            if item['segment'] - 1 == st.session_state.current_segment:
                st.write(f"🟢 **Segment {item['segment']}:** {item['start']:.1f}s - {item['end']:.1f}s (Score: {item['score']:.3f})")
            else:
                st.write(f"Segment {item['segment']}: {item['start']:.1f}s - {item['end']:.1f}s (Score: {item['score']:.3f})")
    
    # Back button
    if st.button("← Back to Gallery"):
        st.session_state.selected_video = None
        st.session_state.current_segment = 0
        st.rerun()


if __name__ == "__main__":
    main()
