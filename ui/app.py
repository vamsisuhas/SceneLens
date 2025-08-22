#!/usr/bin/env python3
"""Streamlit UI for SceneLens search interface."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import requests
import json
from PIL import Image
from pathlib import Path


# Page configuration
st.set_page_config(
    page_title="SceneLens - Video Search",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
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


def main():
    """Main Streamlit application."""
    
    # Header
    st.markdown('<h1 class="main-header">🎬 SceneLens</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">Search video frames with natural language</p>', 
                unsafe_allow_html=True)
    
    # Sidebar configuration
    st.sidebar.header("⚙️ Configuration")
    
    api_base_url = st.sidebar.text_input(
        "API Base URL", 
        value="http://localhost:8000",
        help="Base URL for the SceneLens API"
    )
    
    search_type = st.sidebar.selectbox(
        "Search Type",
        ["semantic", "caption"],
        index=0,
        help="Semantic: CLIP embeddings, Caption: Text matching"
    )
    
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
            placeholder="e.g., 'a person walking', 'drone flying', 'sunset over mountains'",
            key="search_query"
        )
    
    with col2:
        search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    
    # Perform search
    if search_button and query:
        with st.spinner("Searching..."):
            try:
                # Choose endpoint based on search type
                if search_type == "semantic":
                    endpoint = f"{api_base_url}/search"
                else:
                    endpoint = f"{api_base_url}/search/caption"
                
                # Make API request
                response = requests.get(
                    endpoint,
                    params={"q": query, "top_k": top_k},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    display_results(data, api_base_url)
                else:
                    st.error(f"Search failed: {response.status_code} - {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to API. Make sure the backend server is running.")
            except requests.exceptions.Timeout:
                st.error("❌ Search request timed out. Try a simpler query.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Health check in sidebar
    st.sidebar.header("🏥 System Status")
    if st.sidebar.button("Check Health"):
        check_health(api_base_url)
    
    # Instructions
    with st.expander("ℹ️ How to Use"):
        st.markdown("""
        **SceneLens** allows you to search through video frames using natural language queries.
        
        **Search Types:**
        - **Semantic**: Uses CLIP embeddings to find visually similar content
        - **Caption**: Searches through generated captions using text matching
        
        **Example Queries:**
        - "a person walking on the street"
        - "drone flying over landscape"
        - "car driving on highway"
        - "people in a meeting room"
        
        **Tips:**
        - Be descriptive but concise
        - Try different phrasings if you don't get good results
        - Semantic search works better for visual concepts
        - Caption search works better for specific objects or actions
        """)


def display_results(data, api_base_url):
    """Display search results."""
    results = data.get("results", [])
    
    if not results:
        st.warning("No results found. Try a different query or check if videos have been processed.")
        return
    
    st.success(f"Found {len(results)} results for '{data['query']}' (search type: {data['search_type']})")
    
    # Results grid
    cols_per_row = 3
    for i in range(0, len(results), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(results):
                result = results[idx]
                display_result_card(result, col, api_base_url)


def display_result_card(result, container, api_base_url):
    """Display a single result card."""
    with container:
        # Try to display image
        image_path = result.get("keyframe_path")
        if image_path and os.path.exists(image_path):
            try:
                image = Image.open(image_path)
                st.image(image, use_column_width=True)
            except Exception as e:
                st.error(f"Could not load image: {e}")
        else:
            st.info("Image not available")
        
        # Result details
        st.markdown(f"**Score:** `{result.get('score', 0):.3f}`")
        
        video_title = result.get('video_title') or result.get('video_filename', 'Unknown')
        st.markdown(f"**Video:** {video_title}")
        
        timestamp = result.get('timestamp_seconds', 0)
        minutes = int(timestamp // 60)
        seconds = int(timestamp % 60)
        st.markdown(f"**Time:** {minutes}:{seconds:02d}")
        
        if result.get('caption'):
            st.markdown(f"**Caption:** {result['caption']}")
        
        # Additional details in expander
        with st.expander("Details"):
            st.json({
                "segment_id": result.get("segment_id"),
                "frame_number": result.get("frame_number"),
                "timestamp_seconds": result.get("timestamp_seconds"),
                "keyframe_path": result.get("keyframe_path"),
            })


def check_health(api_base_url):
    """Check API health status."""
    try:
        response = requests.get(f"{api_base_url}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            st.sidebar.success("✅ API is healthy")
            st.sidebar.json(health_data)
        else:
            st.sidebar.error(f"❌ API health check failed: {response.status_code}")
    except Exception as e:
        st.sidebar.error(f"❌ Could not check health: {str(e)}")


if __name__ == "__main__":
    main()
