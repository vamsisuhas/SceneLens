#!/usr/bin/env python3
"""Create a diverse test video with distinct segments for testing."""

import cv2
import numpy as np
import os
from pathlib import Path

def create_test_video(output_path="test_video.mp4", duration=30):
    """Create a test video with distinct segments."""
    
    # Video parameters
    fps = 30
    width, height = 640, 480
    total_frames = duration * fps
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    print(f"Creating test video: {output_path}")
    print(f"Duration: {duration}s, FPS: {fps}, Total frames: {total_frames}")
    
    # Define segments with distinct content
    segments = [
        # Segment 1: Blue circle (0-5s)
        {"start": 0, "end": 5, "type": "blue_circle", "description": "Blue circle in center"},
        
        # Segment 2: Red square (5-10s)
        {"start": 5, "end": 10, "type": "red_square", "description": "Red square in corner"},
        
        # Segment 3: Green triangle (10-15s)
        {"start": 10, "end": 15, "type": "green_triangle", "description": "Green triangle"},
        
        # Segment 4: Yellow rectangle (15-20s)
        {"start": 15, "end": 20, "type": "yellow_rectangle", "description": "Yellow rectangle"},
        
        # Segment 5: Purple star (20-25s)
        {"start": 20, "end": 25, "type": "purple_star", "description": "Purple star shape"},
        
        # Segment 6: Orange circle (25-30s)
        {"start": 25, "end": 30, "type": "orange_circle", "description": "Orange circle"}
    ]
    
    for frame_num in range(total_frames):
        # Calculate current time
        current_time = frame_num / fps
        
        # Find current segment
        current_segment = None
        for segment in segments:
            if segment["start"] <= current_time < segment["end"]:
                current_segment = segment
                break
        
        # Create frame based on segment type
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        if current_segment:
            segment_type = current_segment["type"]
            
            if segment_type == "blue_circle":
                # Blue circle in center
                cv2.circle(frame, (width//2, height//2), 100, (255, 0, 0), -1)
                cv2.putText(frame, "BLUE CIRCLE", (width//2-80, height//2+5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            elif segment_type == "red_square":
                # Red square in corner
                cv2.rectangle(frame, (50, 50), (200, 200), (0, 0, 255), -1)
                cv2.putText(frame, "RED SQUARE", (60, 120), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            elif segment_type == "green_triangle":
                # Green triangle
                pts = np.array([[width//2, 100], [width//2-100, 300], [width//2+100, 300]], np.int32)
                cv2.fillPoly(frame, [pts], (0, 255, 0))
                cv2.putText(frame, "GREEN TRIANGLE", (width//2-100, 350), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            elif segment_type == "yellow_rectangle":
                # Yellow rectangle
                cv2.rectangle(frame, (100, 150), (540, 330), (0, 255, 255), -1)
                cv2.putText(frame, "YELLOW RECTANGLE", (200, 250), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            
            elif segment_type == "purple_star":
                # Purple star (simplified as polygon)
                pts = np.array([[width//2, 50], [width//2+50, 150], [width//2+100, 50], 
                               [width//2+75, 200], [width//2+125, 250], [width//2, 220], 
                               [width//2-125, 250], [width//2-75, 200], [width//2-100, 50], 
                               [width//2-50, 150]], np.int32)
                cv2.fillPoly(frame, [pts], (255, 0, 255))
                cv2.putText(frame, "PURPLE STAR", (width//2-80, 280), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            elif segment_type == "orange_circle":
                # Orange circle
                cv2.circle(frame, (width//2, height//2), 120, (0, 165, 255), -1)
                cv2.putText(frame, "ORANGE CIRCLE", (width//2-100, height//2+5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Add timestamp
        cv2.putText(frame, f"Time: {current_time:.1f}s", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add segment info
        if current_segment:
            cv2.putText(frame, f"Segment: {current_segment['description']}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Write frame
        out.write(frame)
    
    # Release video writer
    out.release()
    
    print(f"✅ Test video created: {output_path}")
    print("📊 Video segments:")
    for i, segment in enumerate(segments, 1):
        print(f"  {i}. {segment['start']}s - {segment['end']}s: {segment['description']}")
    
    return output_path

if __name__ == "__main__":
    # Create test video
    video_path = create_test_video("diverse_test_video.mp4", duration=30)
    
    print(f"\n🎬 Test video ready: {video_path}")
    print("You can now use this video for testing the search functionality!")
    print("\nExample search queries:")
    print("- 'blue circle'")
    print("- 'red square'") 
    print("- 'green triangle'")
    print("- 'yellow rectangle'")
    print("- 'purple star'")
    print("- 'orange circle'")
