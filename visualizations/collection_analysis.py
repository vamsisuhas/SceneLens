#!/usr/bin/env python3
"""
Collection-Level Result Analysis Dashboard
Research paper style visualizations for analyzing results across entire video collection.
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
from collections import Counter, defaultdict
import json

from minio_storage import MinIOStorage
from minio import Minio

st.set_page_config(
    page_title="Collection Analysis",
    page_icon="📈",
    layout="wide"
)

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


def fetch_all_video_results(query: str, search_type: str = "object") -> Dict[str, List[Dict]]:
    """Fetch search results for all videos in collection."""
    videos = minio_storage.list_videos()
    all_results = {}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, video in enumerate(videos):
        status_text.text(f"Analyzing {video['filename']} ({idx+1}/{len(videos)})...")
        progress_bar.progress((idx + 1) / len(videos))
        
        try:
            if search_type == "object":
                endpoint = f"{API_BASE_URL}/search/video/{video['id']}"
                params = {"q": query, "top_k": 50, "frame_interval": 0.5}
            else:
                endpoint = f"{API_BASE_URL}/search/action/{video['id']}"
                params = {"q": query, "top_k": 50}
            
            response = requests.get(endpoint, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if results:
                    all_results[video['filename']] = results
        except Exception as e:
            st.warning(f"Could not analyze {video['filename']}: {e}")
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    return all_results


def create_collection_heatmap(all_results: Dict[str, List[Dict]], videos: List[Dict]) -> go.Figure:
    """
    Create heatmap showing detection density across videos and time.
    Research paper style temporal-spatial heatmap.
    """
    if not all_results:
        return go.Figure()
    
    # Normalize time to 0-100% for each video
    video_names = []
    time_percentages = []
    detection_counts = []
    
    for video_name, results in all_results.items():
        video_info = next((v for v in videos if v['filename'] == video_name), None)
        if not video_info:
            continue
        
        duration = video_info.get('duration_seconds', 1)
        
        # Create time bins (0-100%)
        bins = np.linspace(0, 100, 20)  # 20 bins
        counts = np.zeros(len(bins) - 1)
        
        for r in results:
            time_sec = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
            time_pct = (time_sec / duration) * 100 if duration > 0 else 0
            
            bin_idx = np.digitize([time_pct], bins)[0] - 1
            if 0 <= bin_idx < len(counts):
                counts[bin_idx] += 1
        
        for i in range(len(bins) - 1):
            video_names.append(video_name)
            time_percentages.append((bins[i] + bins[i+1]) / 2)
            detection_counts.append(counts[i])
    
    # Create heatmap
    df = pd.DataFrame({
        'Video': video_names,
        'Time (%)': time_percentages,
        'Detections': detection_counts
    })
    
    # Pivot for heatmap
    pivot_df = df.pivot_table(
        index='Video',
        columns='Time (%)',
        values='Detections',
        aggfunc='sum',
        fill_value=0
    )
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot_df.values,
        x=pivot_df.columns,
        y=pivot_df.index,
        colorscale='Viridis',
        hovertemplate='Video: %{y}<br>Time: %{x:.1f}%<br>Detections: %{z}<extra></extra>'
    ))
    
    fig.update_layout(
        title="Detection Density Heatmap Across Collection",
        xaxis_title="Video Progress (%)",
        yaxis_title="Video",
        height=400 + len(pivot_df) * 30,
        width=800
    )
    
    return fig


def create_detection_count_comparison(all_results: Dict[str, List[Dict]]) -> go.Figure:
    """Bar chart comparing detection counts across videos."""
    video_names = []
    counts = []
    avg_scores = []
    
    for video_name, results in all_results.items():
        video_names.append(video_name)
        counts.append(len(results))
        scores = [r.get('score', 0.5) for r in results]
        avg_scores.append(np.mean(scores) if scores else 0)
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(
        go.Bar(
            x=video_names,
            y=counts,
            name='Detection Count',
            marker_color='rgba(55, 128, 191, 0.7)'
        ),
        secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(
            x=video_names,
            y=avg_scores,
            name='Avg Confidence',
            mode='lines+markers',
            marker=dict(size=10),
            line=dict(color='red', width=2)
        ),
        secondary_y=True
    )
    
    fig.update_xaxes(title_text="Video", tickangle=-45)
    fig.update_yaxes(title_text="Detection Count", secondary_y=False)
    fig.update_yaxes(title_text="Average Confidence", secondary_y=True)
    
    fig.update_layout(
        title="Detection Count and Confidence Comparison",
        height=500
    )
    
    return fig


def create_temporal_distribution_analysis(all_results: Dict[str, List[Dict]], videos: List[Dict]) -> go.Figure:
    """Analyze when detections occur across all videos."""
    all_timestamps = []
    video_labels = []
    
    for video_name, results in all_results.items():
        video_info = next((v for v in videos if v['filename'] == video_name), None)
        if not video_info:
            continue
        
        duration = video_info.get('duration_seconds', 1)
        
        for r in results:
            time_sec = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
            time_pct = (time_sec / duration) * 100 if duration > 0 else 0
            all_timestamps.append(time_pct)
            video_labels.append(video_name)
    
    if not all_timestamps:
        return go.Figure()
    
    fig = go.Figure()
    
    # Create histogram
    fig.add_trace(go.Histogram(
        x=all_timestamps,
        nbinsx=20,
        name='Detection Distribution',
        marker_color='rgba(50, 171, 96, 0.7)',
        hovertemplate="Time: %{x:.1f}%<br>Count: %{y}<extra></extra>"
    ))
    
    fig.update_layout(
        title="Temporal Distribution of Detections (Normalized)",
        xaxis_title="Video Progress (%)",
        yaxis_title="Detection Count",
        height=400
    )
    
    return fig


def create_confidence_analysis(all_results: Dict[str, List[Dict]]) -> go.Figure:
    """Box plot comparing confidence scores across videos."""
    video_names = []
    scores_list = []
    
    for video_name, results in all_results.items():
        scores = [r.get('score', 0.5) for r in results]
        if scores:
            video_names.append(video_name)
            scores_list.append(scores)
    
    if not scores_list:
        return go.Figure()
    
    fig = go.Figure()
    
    for video_name, scores in zip(video_names, scores_list):
        fig.add_trace(go.Box(
            y=scores,
            name=video_name,
            boxmean='sd'
        ))
    
    fig.update_layout(
        title="Confidence Score Distribution by Video",
        yaxis_title="Confidence Score",
        xaxis_title="Video",
        height=500,
        xaxis=dict(tickangle=-45)
    )
    
    return fig


def create_coverage_analysis(all_results: Dict[str, List[Dict]], videos: List[Dict]) -> go.Figure:
    """Analyze how much of each video is covered by detections."""
    video_names = []
    coverage_pcts = []
    total_durations = []
    
    for video_name, results in all_results.items():
        video_info = next((v for v in videos if v['filename'] == video_name), None)
        if not video_info:
            continue
        
        duration = video_info.get('duration_seconds', 1)
        total_durations.append(duration)
        
        # Calculate total coverage
        covered_time = 0
        segments = []
        for r in results:
            start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
            end = r.get('segment_end_seconds', start + 2.0)
            segments.append((start, end))
        
        # Merge overlapping segments
        if segments:
            segments.sort()
            merged = [segments[0]]
            for start, end in segments[1:]:
                last_start, last_end = merged[-1]
                if start <= last_end:
                    merged[-1] = (last_start, max(last_end, end))
                else:
                    merged.append((start, end))
            
            covered_time = sum(end - start for start, end in merged)
        
        coverage_pct = (covered_time / duration) * 100 if duration > 0 else 0
        video_names.append(video_name)
        coverage_pcts.append(coverage_pct)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=video_names,
        y=coverage_pcts,
        name='Coverage %',
        marker_color='rgba(255, 128, 0, 0.7)',
        text=[f"{p:.1f}%" for p in coverage_pcts],
        textposition='outside'
    ))
    
    fig.update_layout(
        title="Video Coverage by Detections",
        xaxis_title="Video",
        yaxis_title="Coverage (%)",
        height=500,
        xaxis=dict(tickangle=-45)
    )
    
    return fig


def create_statistical_summary_table(all_results: Dict[str, List[Dict]], videos: List[Dict]) -> pd.DataFrame:
    """Create comprehensive statistical summary."""
    summary_data = []
    
    for video_name, results in all_results.items():
        video_info = next((v for v in videos if v['filename'] == video_name), None)
        if not video_info:
            continue
        
        if not results:
            continue
        
        scores = [r.get('score', 0.5) for r in results]
        durations = []
        for r in results:
            start = r.get('segment_start_seconds', r.get('timestamp_seconds', 0))
            end = r.get('segment_end_seconds', start + 2.0)
            durations.append(end - start)
        
        video_duration = video_info.get('duration_seconds', 1)
        total_coverage = sum(durations)
        
        summary_data.append({
            'Video': video_name,
            'Detections': len(results),
            'Avg Confidence': f"{np.mean(scores):.3f}",
            'Std Confidence': f"{np.std(scores):.3f}",
            'Avg Duration (s)': f"{np.mean(durations):.2f}",
            'Total Coverage (s)': f"{total_coverage:.2f}",
            'Coverage %': f"{(total_coverage / video_duration) * 100:.1f}%",
            'Detection Rate (/min)': f"{(len(results) / (video_duration / 60)):.2f}"
        })
    
    return pd.DataFrame(summary_data)


def main():
    st.title("📈 Collection-Level Result Analysis")
    st.markdown("Research-style visualizations for analyzing detection results across entire video collection")
    
    # Sidebar
    st.sidebar.header("Collection Analysis")
    
    query = st.sidebar.text_input(
        "Search Query",
        value="",
        help="Enter object or action to analyze across all videos"
    )
    
    search_type = st.sidebar.radio(
        "Search Type",
        ["Object Detection", "Action Detection"],
        index=0
    )
    
    analyze_button = st.sidebar.button("Analyze Collection", type="primary")
    
    if not analyze_button or not query:
        st.info("👈 Enter a query in the sidebar to analyze across all videos")
        return
    
    # Get videos
    videos = minio_storage.list_videos()
    if not videos:
        st.warning("No videos found in collection")
        return
    
    st.info(f"Analyzing '{query}' across {len(videos)} videos...")
    
    # Fetch results for all videos
    all_results = fetch_all_video_results(
        query,
        "object" if search_type == "Object Detection" else "action"
    )
    
    if not all_results:
        st.warning(f"No results found for '{query}' in any video")
        return
    
    st.success(f"Found detections in {len(all_results)}/{len(videos)} videos")
    
    # Visualizations
    st.header("1. Temporal-Spatial Heatmap")
    heatmap_fig = create_collection_heatmap(all_results, videos)
    st.plotly_chart(heatmap_fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("2. Detection Count Comparison")
        count_fig = create_detection_count_comparison(all_results)
        st.plotly_chart(count_fig, use_container_width=True)
    
    with col2:
        st.subheader("3. Temporal Distribution")
        temp_fig = create_temporal_distribution_analysis(all_results, videos)
        st.plotly_chart(temp_fig, use_container_width=True)
    
    st.header("4. Confidence Score Analysis")
    conf_fig = create_confidence_analysis(all_results)
    st.plotly_chart(conf_fig, use_container_width=True)
    
    st.header("5. Video Coverage Analysis")
    coverage_fig = create_coverage_analysis(all_results, videos)
    st.plotly_chart(coverage_fig, use_container_width=True)
    
    st.header("6. Statistical Summary")
    summary_df = create_statistical_summary_table(all_results, videos)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()

