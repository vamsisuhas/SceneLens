#!/usr/bin/env python3
"""
Result-Based Visualization Dashboard for Video Collection Analysis
Similar to research paper visualizations showing detection results, temporal patterns, and statistics.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import requests
from typing import List, Dict, Optional
from datetime import datetime
import json

from minio_storage import MinIOStorage
from minio import Minio

# Configure page
st.set_page_config(
    page_title="SceneLens Result Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize MinIO
@st.cache_resource
def init_minio():
    minio_client = Minio(
        "127.0.0.1:9000",
        access_key="scenelens",
        secret_key="scenelens_dev123",
        secure=False,
        region="us-east-1"
    )
    return MinIOStorage(minio_client, "scenelens")

minio_storage = init_minio()

# API configuration
API_BASE_URL = "http://localhost:8000"


def load_all_search_results() -> pd.DataFrame:
    """Load all search results from search logs and aggregate."""
    try:
        # Get all videos
        videos = minio_storage.list_videos()
        
        # Get search logs
        search_logs = minio_storage.get_search_logs(limit=1000)
        
        # For each search log, we'd need to fetch actual results
        # For now, we'll work with what we have in logs
        results = []
        
        for log in search_logs:
            results.append({
                'query': log.get('query', ''),
                'results_count': log.get('results_count', 0),
                'response_time_ms': log.get('response_time_ms', 0),
                'search_type': log.get('search_type', 'unknown'),
                'timestamp': log.get('timestamp', '')
            })
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Error loading search results: {e}")
        return pd.DataFrame()


def fetch_search_results_for_analysis(video_id: str, query: str, search_type: str = "object") -> List[Dict]:
    """Fetch actual search results from API for detailed analysis."""
    try:
        if search_type == "object":
            endpoint = f"{API_BASE_URL}/search/video/{video_id}"
            params = {"q": query, "top_k": 50, "frame_interval": 0.5}
        else:
            endpoint = f"{API_BASE_URL}/search/action/{video_id}"
            params = {"q": query, "top_k": 50}
        
        response = requests.get(endpoint, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get('results', [])
        return []
    except Exception as e:
        st.warning(f"Could not fetch results: {e}")
        return []


def create_temporal_detection_timeline(results: List[Dict], video_duration: float) -> go.Figure:
    """
    Create timeline visualization showing when detections occur in video.
    Similar to research paper temporal analysis plots.
    """
    if not results:
        return go.Figure()
    
    # Prepare data
    segments = []
    for r in results:
        start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        end = r.get('segment_end_seconds', start + 2.0)
        score = r.get('score', 0.5)
        segments.append({
            'start': start,
            'end': end,
            'score': score,
            'duration': end - start
        })
    
    df = pd.DataFrame(segments)
    
    # Create timeline plot
    fig = go.Figure()
    
    # Add detection segments as horizontal bars
    for idx, seg in enumerate(segments):
        fig.add_trace(go.Scatter(
            x=[seg['start'], seg['end']],
            y=[idx, idx],
            mode='lines+markers',
            line=dict(
                width=8,
                color=px.colors.sequential.Viridis[int(seg['score'] * 255)]
            ),
            marker=dict(size=10),
            name=f"Detection {idx+1}",
            hovertemplate=f"Time: {seg['start']:.1f}s - {seg['end']:.1f}s<br>" +
                          f"Score: {seg['score']:.3f}<br>" +
                          f"Duration: {seg['duration']:.2f}s<extra></extra>"
        ))
    
    fig.update_layout(
        title="Temporal Detection Timeline",
        xaxis_title="Time (seconds)",
        yaxis_title="Detection Index",
        height=400,
        showlegend=False,
        hovermode='closest'
    )
    
    return fig


def create_detection_density_plot(results: List[Dict], video_duration: float, bins: int = 50) -> go.Figure:
    """
    Create density plot showing distribution of detections over video duration.
    Research paper style histogram/density visualization.
    """
    if not results:
        return go.Figure()
    
    # Extract timestamps
    timestamps = []
    scores = []
    for r in results:
        mid_time = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        timestamps.append(mid_time)
        scores.append(r.get('score', 0.5))
    
    # Create histogram
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=timestamps,
        nbinsx=bins,
        name='Detection Count',
        marker_color='rgba(55, 128, 191, 0.7)',
        hovertemplate="Time: %{x:.1f}s<br>Count: %{y}<extra></extra>"
    ))
    
    # Add score-weighted density
    fig.add_trace(go.Histogram(
        x=timestamps,
        y=scores,
        nbinsx=bins,
        name='Score-Weighted Density',
        marker_color='rgba(255, 128, 0, 0.7)',
        yaxis='y2',
        hovertemplate="Time: %{x:.1f}s<br>Weighted: %{y:.3f}<extra></extra>"
    ))
    
    fig.update_layout(
        title="Detection Density Over Time",
        xaxis_title="Time (seconds)",
        yaxis_title="Detection Count",
        yaxis2=dict(
            title="Score-Weighted Density",
            overlaying='y',
            side='right'
        ),
        barmode='overlay',
        height=400
    )
    
    return fig


def create_confidence_distribution(results: List[Dict]) -> go.Figure:
    """Create histogram of confidence scores."""
    if not results:
        return go.Figure()
    
    scores = [r.get('score', 0.5) for r in results]
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=scores,
        nbinsx=20,
        name='Confidence Scores',
        marker_color='rgba(50, 171, 96, 0.7)',
        hovertemplate="Score: %{x:.3f}<br>Count: %{y}<extra></extra>"
    ))
    
    # Add statistics
    mean_score = np.mean(scores)
    median_score = np.median(scores)
    
    fig.add_vline(
        x=mean_score,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {mean_score:.3f}"
    )
    
    fig.add_vline(
        x=median_score,
        line_dash="dash",
        line_color="blue",
        annotation_text=f"Median: {median_score:.3f}"
    )
    
    fig.update_layout(
        title="Confidence Score Distribution",
        xaxis_title="Confidence Score",
        yaxis_title="Frequency",
        height=400
    )
    
    return fig


def create_segment_duration_analysis(results: List[Dict]) -> go.Figure:
    """Analyze and visualize segment durations."""
    if not results:
        return go.Figure()
    
    durations = []
    for r in results:
        start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        end = r.get('segment_end_seconds', start + 2.0)
        durations.append(end - start)
    
    fig = go.Figure()
    
    fig.add_trace(go.Box(
        y=durations,
        name='Segment Durations',
        boxmean='sd',
        hovertemplate="Duration: %{y:.2f}s<extra></extra>"
    ))
    
    fig.update_layout(
        title="Segment Duration Distribution",
        yaxis_title="Duration (seconds)",
        height=400
    )
    
    return fig


def create_multi_video_comparison(video_results: Dict[str, List[Dict]]) -> go.Figure:
    """
    Compare detection results across multiple videos.
    Research paper style comparison visualization.
    """
    if not video_results:
        return go.Figure()
    
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set3
    
    for idx, (video_name, results) in enumerate(video_results.items()):
        if not results:
            continue
        
        timestamps = [r.get('segment_start_seconds', r.get('timestamp_seconds', 0)) for r in results]
        scores = [r.get('score', 0.5) for r in results]
        
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=scores,
            mode='markers',
            name=video_name,
            marker=dict(
                size=8,
                color=colors[idx % len(colors)],
                opacity=0.7
            ),
            hovertemplate=f"Video: {video_name}<br>" +
                         "Time: %{x:.1f}s<br>" +
                         "Score: %{y:.3f}<extra></extra>"
        ))
    
    fig.update_layout(
        title="Multi-Video Detection Comparison",
        xaxis_title="Time (seconds)",
        yaxis_title="Confidence Score",
        height=500,
        hovermode='closest'
    )
    
    return fig


def create_statistical_summary_table(results: List[Dict], video_info: Dict) -> pd.DataFrame:
    """Create statistical summary table."""
    if not results:
        return pd.DataFrame()
    
    durations = []
    scores = []
    timestamps = []
    
    for r in results:
        start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        end = r.get('segment_end_seconds', start + 2.0)
        durations.append(end - start)
        scores.append(r.get('score', 0.5))
        timestamps.append(start)
    
    stats = {
        'Metric': [
            'Total Detections',
            'Mean Confidence',
            'Std Confidence',
            'Mean Duration (s)',
            'Total Coverage (s)',
            'Coverage %',
            'First Detection (s)',
            'Last Detection (s)',
            'Detection Rate (per min)'
        ],
        'Value': [
            len(results),
            f"{np.mean(scores):.3f}",
            f"{np.std(scores):.3f}",
            f"{np.mean(durations):.2f}",
            f"{sum(durations):.2f}",
            f"{(sum(durations) / video_info.get('duration_seconds', 1)) * 100:.1f}%",
            f"{min(timestamps):.1f}",
            f"{max(timestamps):.1f}",
            f"{(len(results) / (video_info.get('duration_seconds', 1) / 60)):.2f}"
        ]
    }
    
    return pd.DataFrame(stats)


def main():
    st.title("📊 Video Collection Result Analysis Dashboard")
    st.markdown("Research-style visualizations of detection results and temporal patterns")
    
    # Sidebar controls
    st.sidebar.header("Analysis Configuration")
    
    # Get videos
    try:
        videos = minio_storage.list_videos()
        video_options = {v['filename']: v for v in videos}
        
        if not video_options:
            st.warning("No videos found in collection. Upload videos first.")
            return
        
        selected_video_name = st.sidebar.selectbox(
            "Select Video",
            options=list(video_options.keys())
        )
        
        selected_video = video_options[selected_video_name]
        
        # Query input
        query = st.sidebar.text_input(
            "Search Query",
            value="",
            help="Enter object or action to analyze"
        )
        
        search_type = st.sidebar.radio(
            "Search Type",
            ["Object Detection", "Action Detection"],
            index=0
        )
        
        analyze_button = st.sidebar.button("Analyze Results", type="primary")
        
    except Exception as e:
        st.error(f"Error loading videos: {e}")
        return
    
    if not analyze_button or not query:
        st.info("👈 Select a video and enter a query in the sidebar to begin analysis")
        return
    
    # Fetch results
    with st.spinner("Fetching search results..."):
        results = fetch_search_results_for_analysis(
            selected_video['id'],
            query,
            "object" if search_type == "Object Detection" else "action"
        )
    
    if not results:
        st.warning(f"No results found for query '{query}' in video '{selected_video_name}'")
        return
    
    st.success(f"Found {len(results)} detections for '{query}'")
    
    # Main visualizations
    st.header("1. Temporal Detection Timeline")
    timeline_fig = create_temporal_detection_timeline(
        results,
        selected_video.get('duration_seconds', 0)
    )
    st.plotly_chart(timeline_fig, use_container_width=True)
    
    # Two column layout for density and confidence
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("2. Detection Density")
        density_fig = create_detection_density_plot(
            results,
            selected_video.get('duration_seconds', 0)
        )
        st.plotly_chart(density_fig, use_container_width=True)
    
    with col2:
        st.subheader("3. Confidence Distribution")
        conf_fig = create_confidence_distribution(results)
        st.plotly_chart(conf_fig, use_container_width=True)
    
    # Segment duration analysis
    st.header("4. Segment Duration Analysis")
    duration_fig = create_segment_duration_analysis(results)
    st.plotly_chart(duration_fig, use_container_width=True)
    
    # Statistical summary
    st.header("5. Statistical Summary")
    stats_df = create_statistical_summary_table(results, selected_video)
    st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    # Results table
    st.header("6. Detailed Results")
    results_df = pd.DataFrame([
        {
            'Time (s)': r.get('segment_start_seconds', r.get('timestamp_seconds', 0)),
            'Duration (s)': (r.get('segment_end_seconds', 0) - r.get('segment_start_seconds', r.get('timestamp_seconds', 0))),
            'Score': f"{r.get('score', 0):.3f}",
            'Frame': r.get('frame_number', 0),
            'Caption': r.get('caption', '')
        }
        for r in results
    ])
    st.dataframe(results_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()

