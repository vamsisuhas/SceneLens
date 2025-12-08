# Video Collection Visualization Dashboards

Research-style visualizations for analyzing detection results from SceneLens video collection.

## 📊 Available Dashboards

### 1. **Result Analysis Dashboard** (`result_analysis.py`)
Single video analysis with detailed temporal and statistical visualizations.

**Features:**
- Temporal Detection Timeline - When detections occur in video
- Detection Density Plot - Distribution over time
- Confidence Score Distribution - Histogram of detection confidence
- Segment Duration Analysis - Box plot of segment lengths
- Statistical Summary Table - Comprehensive metrics
- Detailed Results Table - All detection segments

**Usage:**
```bash
streamlit run visualizations/result_analysis.py
```

### 2. **Collection Analysis Dashboard** (`collection_analysis.py`)
Multi-video collection analysis comparing results across all videos.

**Features:**
- Temporal-Spatial Heatmap - Detection density across videos and time
- Detection Count Comparison - Bar chart with confidence overlay
- Temporal Distribution - When detections occur (normalized)
- Confidence Analysis - Box plots comparing videos
- Coverage Analysis - How much of each video is covered
- Statistical Summary - Comprehensive comparison table

**Usage:**
```bash
streamlit run visualizations/collection_analysis.py
```

## 🎯 Research Paper Style Visualizations

These dashboards provide visualizations similar to those found in video analysis research papers:

1. **Temporal Patterns** - Timeline and density plots showing when detections occur
2. **Statistical Analysis** - Distributions, means, medians, coverage metrics
3. **Multi-Video Comparison** - Heatmaps and comparative charts
4. **Confidence Analysis** - Score distributions and quality metrics
5. **Coverage Metrics** - How much of videos contain detections

## 📋 Requirements

- Streamlit
- Plotly
- Pandas
- NumPy
- MinIO client (already in project)

## 🚀 Quick Start

1. Make sure backend is running:
   ```bash
   python backend/app.py
   ```

2. Run visualization dashboard:
   ```bash
   # Single video analysis
   streamlit run visualizations/result_analysis.py
   
   # Collection analysis
   streamlit run visualizations/collection_analysis.py
   ```

3. In the sidebar:
   - Select a video (for single video analysis)
   - Enter a search query (e.g., "person", "drone", "car")
   - Choose search type (Object or Action Detection)
   - Click "Analyze" button

## 📈 Visualization Types

### Temporal Visualizations
- **Timeline**: Horizontal bars showing detection segments
- **Density Plots**: Histograms showing detection frequency over time
- **Heatmaps**: 2D visualization of detections across videos and time

### Statistical Visualizations
- **Histograms**: Distribution of confidence scores
- **Box Plots**: Comparison of metrics across videos
- **Bar Charts**: Count comparisons with overlays

### Comparative Visualizations
- **Multi-video Scatter**: Compare detections across videos
- **Coverage Analysis**: How much each video is covered
- **Confidence Comparison**: Score distributions by video

## 💡 Tips

1. **For Single Video Analysis**: Use `result_analysis.py` to dive deep into one video's results
2. **For Collection Analysis**: Use `collection_analysis.py` to compare across all videos
3. **Query Selection**: Try different queries to see patterns (e.g., "person", "vehicle", "drone landing")
4. **Export Data**: Use Streamlit's built-in download button or copy tables

## 🔧 Customization

Both dashboards are modular - you can:
- Add new visualization functions
- Modify color schemes
- Adjust bin sizes for histograms
- Add filtering options
- Export visualizations as images

## 📝 Data Structure

Visualizations work with search results containing:
- `segment_start_seconds`: Start time of detection
- `segment_end_seconds`: End time of detection
- `timestamp_seconds`: Midpoint timestamp
- `score`: Confidence score (0-1)
- `video_id`: Video identifier
- `video_filename`: Video name
- `caption`: Detection description

