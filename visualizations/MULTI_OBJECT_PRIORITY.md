# Multi-Object Priority Search

## Overview

This feature allows you to search for multiple objects in a video with priority weights. Higher priority numbers mean more importance (e.g., priority 5 > priority 1).

## How It Works

1. **Priority System**: Simple numeric priorities (1, 2, 3, 4, etc.)
   - Higher number = Higher priority
   - Priority 5 is more important than priority 1

2. **Weighted Scoring**: 
   - Each object detection gets a base confidence score (0-1)
   - Weighted score = base_score × priority
   - Results are combined and sorted by weighted score

3. **Result Combination**:
   - Segments where multiple objects appear get higher weighted scores
   - Objects with higher priorities contribute more to the final score

## Usage

### Backend API

**Endpoint**: `POST /search/multi-object/{video_id}`

**Request Body**:
```json
{
  "objects": [
    {"object": "person", "priority": 5},
    {"object": "vehicle", "priority": 3},
    {"object": "drone", "priority": 1}
  ],
  "top_k": 20,
  "frame_interval": 0.5
}
```

**Response**: Same format as regular search, but with additional fields:
- `weighted_score`: Combined weighted score
- `objects_detected`: List of objects found in segment
- `object_priorities`: List of priorities for detected objects
- `raw_scores`: Individual detection scores

### Frontend Dashboard

**Run the dashboard**:
```bash
streamlit run visualizations/multi_object_priority.py
```

**Steps**:
1. Select a video from the sidebar
2. Add objects with priorities:
   - Enter object name (e.g., "person")
   - Set priority (1, 2, 3, 4, etc.)
   - Click "Add Object"
   - Repeat for all objects
3. Adjust search parameters (Top K, Frame Interval)
4. Click "Search" button
5. View visualizations

## Visualizations

### 1. Priority-Weighted Timeline
- Shows when detections occur
- Color intensity = weighted score
- Hover for details (objects, priorities, scores)

### 2. Multi-Object Heatmap
- Rows = objects
- Columns = time bins
- Color = priority-weighted detection strength
- Shows which objects appear when

### 3. Weighted Score Over Time
- Line chart showing weighted score over time
- Marker size = number of objects detected
- Color = normalized score

### 4. Object Co-occurrence Matrix
- Shows which objects appear together
- Weighted by priorities
- Helps identify object relationships

### 5. Priority Statistics
- Table showing detection counts per object
- Average weighted scores
- Total contributions

### 6. Detailed Results Table
- All detection segments
- Objects, priorities, scores
- Sortable and filterable

## Example Use Cases

### Security Monitoring
```
Objects: person (priority 5), weapon (priority 4), vehicle (priority 2)
Result: Finds scenes with high-priority security concerns
```

### Content Analysis
```
Objects: main_character (priority 5), supporting_character (priority 3), background (priority 1)
Result: Identifies key scenes with main characters
```

### Research Analysis
```
Objects: primary_object (priority 4), secondary_object (priority 2), context (priority 1)
Result: Focuses on primary research objects while considering context
```

## Tips

1. **Priority Assignment**:
   - Use higher priorities (4-5) for most important objects
   - Use lower priorities (1-2) for supporting/context objects
   - Priority 3 is a good middle ground

2. **Object Selection**:
   - Start with 2-3 objects to understand patterns
   - Add more objects as needed
   - Remove objects that don't contribute

3. **Frame Interval**:
   - Lower interval (0.1-0.5s) = more precise, slower
   - Higher interval (1-2s) = faster, less precise
   - Default 0.5s is a good balance

4. **Top K Results**:
   - Start with 20 results
   - Increase if you need more coverage
   - Decrease for focused results

## Technical Details

### Scoring Algorithm
```
For each time segment:
  weighted_score = Σ(detection_score × priority)
  
Normalized score = weighted_score / (sum of all priorities)
```

### Segment Grouping
- Segments within 1 second are grouped together
- Multiple objects in same segment = higher weighted score
- Results sorted by weighted_score (descending)

### Performance
- Searches all objects in parallel
- Combines results efficiently
- Typical search time: 30-120 seconds depending on video length and number of objects

