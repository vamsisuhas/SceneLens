#!/usr/bin/env python3
"""
Multi-Object Priority Search Visualization Dashboard
Allows users to search for multiple objects with priority weights (1, 2, 3, 4, etc.)
and visualize weighted results.
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
from io import BytesIO
from PIL import Image

from minio_storage import MinIOStorage
from minio import Minio

st.set_page_config(
    page_title="Multi-Object Priority Search",
    page_icon="🎯",
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
API_BASE_URL = "http://localhost:8000"


def create_priority_timeline(results: List[Dict], video_duration: float) -> go.Figure:
    """Create timeline showing priority-weighted detections."""
    if not results:
        return go.Figure()
    
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
            'priorities': priorities,
            'duration': end - start
        })
    
    fig = go.Figure()
    
    # Add detection segments as horizontal bars
    for idx, seg in enumerate(segments):
        # Color based on weighted score
        color_value = min(255, int(seg['weighted_score'] * 50))  # Scale for color
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
                         f"<b>Normalized Score:</b> {seg['normalized_score']:.3f}<br>" +
                         f"<b>Duration:</b> {seg['duration']:.2f}s<extra></extra>"
        ))
    
    fig.update_layout(
        title="Priority-Weighted Detection Timeline",
        xaxis_title="Time (seconds)",
        yaxis_title="Detection Index",
        height=500,
        showlegend=False,
        hovermode='closest'
    )
    
    return fig


def create_multi_object_heatmap(results: List[Dict], objects: List[str], video_duration: float) -> go.Figure:
    """Create heatmap showing which objects detected at which times."""
    if not results:
        return go.Figure()
    
    # Create time bins
    bins = np.linspace(0, video_duration, 50)  # 50 bins
    
    # Initialize data structure
    heatmap_data = {obj: np.zeros(len(bins) - 1) for obj in objects}
    
    for r in results:
        start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        end = r.get('segment_end_seconds', start + 2.0)
        detected_objects = r.get('objects_detected', [])
        priorities = r.get('object_priorities', [])
        
        # Find bins that overlap with this segment
        start_bin = np.digitize([start], bins)[0] - 1
        end_bin = np.digitize([end], bins)[0]
        
        for obj, priority in zip(detected_objects, priorities):
            if obj in heatmap_data:
                # Weight by priority
                for bin_idx in range(max(0, start_bin), min(len(bins) - 1, end_bin)):
                    heatmap_data[obj][bin_idx] += priority
    
    # Create heatmap
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


def create_weighted_score_over_time(results: List[Dict], video_duration: float) -> go.Figure:
    """Create line chart showing weighted score over time."""
    if not results:
        return go.Figure()
    
    timestamps = []
    weighted_scores = []
    normalized_scores = []
    object_counts = []
    
    for r in results:
        mid_time = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
        timestamps.append(mid_time)
        weighted_scores.append(r.get('weighted_score', 0.0))
        normalized_scores.append(r.get('score', 0.0))
        object_counts.append(len(r.get('objects_detected', [])))
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Weighted score line
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
    
    # Object count (size of markers)
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


def create_object_cooccurrence_matrix(results: List[Dict], objects: List[str]) -> go.Figure:
    """Create matrix showing object co-occurrence."""
    if not results or not objects:
        return go.Figure()
    
    # Count co-occurrences
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
                        # Weight by priorities
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


def create_priority_statistics(results: List[Dict], objects: List[str], priorities: List[int]) -> pd.DataFrame:
    """Create statistics table for priority analysis."""
    if not results:
        return pd.DataFrame()
    
    # Count detections per object
    object_stats = {obj: {'count': 0, 'total_weighted': 0, 'avg_score': 0} for obj in objects}
    
    for r in results:
        detected = r.get('objects_detected', [])
        obj_priorities = r.get('object_priorities', [])
        raw_scores = r.get('raw_scores', [])
        
        for i, obj in enumerate(detected):
            if obj in object_stats:
                object_stats[obj]['count'] += 1
                if i < len(raw_scores):
                    object_stats[obj]['total_weighted'] += raw_scores[i] * obj_priorities[i] if i < len(obj_priorities) else raw_scores[i]
    
    # Calculate averages
    for obj in object_stats:
        if object_stats[obj]['count'] > 0:
            object_stats[obj]['avg_score'] = object_stats[obj]['total_weighted'] / object_stats[obj]['count']
    
    # Create DataFrame
    stats_data = []
    for obj, priority in zip(objects, priorities):
        stats_data.append({
            'Object': obj,
            'Priority': priority,
            'Detection Count': object_stats[obj]['count'],
            'Avg Weighted Score': f"{object_stats[obj]['avg_score']:.3f}",
            'Total Contribution': f"{object_stats[obj]['total_weighted']:.2f}"
        })
    
    return pd.DataFrame(stats_data)


def main():
    st.title("🎯 Multi-Object Priority Search Dashboard")
    st.markdown("Search for multiple objects with priority weights (1, 2, 3, 4, etc.) and visualize weighted results")
    
    # Sidebar - Object and Priority Input
    st.sidebar.header("Multi-Object Priority Search")
    
    # Get videos
    try:
        videos = minio_storage.list_videos()
        if not videos:
            st.warning("No videos found. Upload videos first.")
            return
        
        video_options = {v['filename']: v for v in videos}
        selected_video_name = st.sidebar.selectbox(
            "Select Video",
            options=list(video_options.keys())
        )
        selected_video = video_options[selected_video_name]
        
    except Exception as e:
        st.error(f"Error loading videos: {e}")
        return
    
    # Object list management
    st.sidebar.subheader("Objects & Priorities")
    
    # Initialize session state for objects
    if 'object_list' not in st.session_state:
        st.session_state.object_list = []
    
    # Add object input
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        new_object = st.text_input("Object", key="new_object_input", placeholder="e.g., person")
    with col2:
        new_priority = st.number_input("Priority", min_value=1, max_value=10, value=1, step=1, key="new_priority_input")
    
    if st.sidebar.button("➕ Add Object", use_container_width=True):
        if new_object.strip():
            st.session_state.object_list.append({
                'object': new_object.strip(),
                'priority': int(new_priority)
            })
            st.rerun()
    
    # Display current objects
    if st.session_state.object_list:
        st.sidebar.markdown("**Current Objects:**")
        for idx, obj_data in enumerate(st.session_state.object_list):
            col1, col2, col3 = st.sidebar.columns([3, 1, 1])
            with col1:
                st.write(f"{obj_data['object']}")
            with col2:
                st.write(f"P{obj_data['priority']}")
            with col3:
                if st.button("❌", key=f"remove_{idx}"):
                    st.session_state.object_list.pop(idx)
                    st.rerun()
    
    # Search parameters
    st.sidebar.subheader("Search Parameters")
    top_k = st.sidebar.number_input("Top K Results", min_value=5, max_value=50, value=20, step=5)
    frame_interval = st.sidebar.number_input("Frame Interval (seconds)", min_value=0.1, max_value=5.0, value=0.5, step=0.1)
    
    # Search button
    search_button = st.sidebar.button("🔍 Search", type="primary", use_container_width=True)
    
    if not st.session_state.object_list:
        st.info("👈 Add objects and priorities in the sidebar to begin search")
        return
    
    if not search_button:
        st.info("👈 Click 'Search' button to analyze the video")
        return
    
    # Perform search
    with st.spinner("Searching for multiple objects with priority weights..."):
        try:
            # Prepare request
            objects_data = [
                {"object": obj['object'], "priority": obj['priority']}
                for obj in st.session_state.object_list
            ]
            
            request_data = {
                "objects": objects_data,
                "top_k": top_k,
                "frame_interval": frame_interval
            }
            
            # Make API call
            response = requests.post(
                f"{API_BASE_URL}/search/multi-object/{selected_video['id']}",
                json=request_data,
                timeout=120
            )
            
            if response.status_code != 200:
                st.error(f"Search failed: {response.text}")
                return
            
            data = response.json()
            results = data.get('results', [])
            
        except Exception as e:
            st.error(f"Error performing search: {e}")
            return
    
    if not results:
        st.warning(f"No results found for the specified objects in '{selected_video_name}'")
        return
    
    st.success(f"Found {len(results)} priority-weighted results!")
    
    # Extract objects and priorities for visualizations
    objects = [obj['object'] for obj in st.session_state.object_list]
    priorities = [obj['priority'] for obj in st.session_state.object_list]
    video_duration = selected_video.get('duration_seconds', 100)
    
    # Main visualizations
    st.header("1. Priority-Weighted Timeline")
    timeline_fig = create_priority_timeline(results, video_duration)
    st.plotly_chart(timeline_fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("2. Multi-Object Heatmap")
        heatmap_fig = create_multi_object_heatmap(results, objects, video_duration)
        st.plotly_chart(heatmap_fig, use_container_width=True)
    
    with col2:
        st.subheader("3. Weighted Score Over Time")
        score_fig = create_weighted_score_over_time(results, video_duration)
        st.plotly_chart(score_fig, use_container_width=True)
    
    st.header("4. Object Co-occurrence Matrix")
    cooccurrence_fig = create_object_cooccurrence_matrix(results, objects)
    st.plotly_chart(cooccurrence_fig, use_container_width=True)
    
    st.header("5. Priority Statistics")
    stats_df = create_priority_statistics(results, objects, priorities)
    st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    st.header("6. Detailed Results")
    results_df = pd.DataFrame([
        {
            'Time (s)': r.get('segment_start_seconds', r.get('timestamp_seconds', 0)),
            'Duration (s)': (r.get('segment_end_seconds', 0) - r.get('segment_start_seconds', r.get('timestamp_seconds', 0))),
            'Objects': ', '.join(r.get('objects_detected', [])),
            'Priorities': str(r.get('object_priorities', [])),
            'Weighted Score': f"{r.get('weighted_score', 0):.2f}",
            'Normalized Score': f"{r.get('score', 0):.3f}",
            'Raw Scores': str(r.get('raw_scores', []))
        }
        for r in results
    ])
    st.dataframe(results_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()

