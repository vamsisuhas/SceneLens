#!/usr/bin/env python3
"""Utility for extracting frames from temporal windows without creating video clips."""

import logging
import cv2
import numpy as np
from typing import List, Tuple, Dict
from PIL import Image

logger = logging.getLogger(__name__)


class TemporalWindow:
    """Represents a temporal window in a video."""
    
    def __init__(self, start_time: float, end_time: float, window_id: int):
        self.start_time = start_time
        self.end_time = end_time
        self.window_id = window_id
        self.duration = end_time - start_time
    
    def __repr__(self):
        return f"Window({self.window_id}: {self.start_time:.1f}s - {self.end_time:.1f}s)"


class VideoChunker:
    """Extract frames from temporal windows in memory without creating video clips."""
    
    def __init__(self, video_path: str):
        """
        Initialize video chunker.
        
        Args:
            video_path: Path to the video file
        """
        self.video_path = video_path
        self.cap = None
        self.fps = None
        self.total_frames = None
        self.duration = None
        self._initialize_video()
    
    def _initialize_video(self):
        """Open video and get metadata."""
        try:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                raise ValueError(f"Cannot open video: {self.video_path}")
            
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Handle invalid FPS
            if self.fps <= 0 or self.fps is None:
                logger.warning(f"Invalid FPS ({self.fps}), using default 30.0")
                self.fps = 30.0
            
            self.duration = self.total_frames / self.fps
            
            logger.info(f"Video initialized: {self.duration:.1f}s @ {self.fps:.1f} FPS ({self.total_frames} frames)")
            
        except Exception as e:
            logger.error(f"Failed to initialize video: {e}")
            raise
    
    def get_temporal_windows(self, clip_duration: float = 20.0, overlap: float = 10.0) -> List[TemporalWindow]:
        """
        Generate temporal windows for the video.
        
        Args:
            clip_duration: Duration of each window in seconds
            overlap: Overlap between consecutive windows in seconds
            
        Returns:
            List of TemporalWindow objects
        """
        windows = []
        window_id = 0
        start_time = 0.0
        stride = clip_duration - overlap
        
        while start_time < self.duration:
            end_time = min(start_time + clip_duration, self.duration)
            
            # Only add window if it has meaningful duration (at least 50% of clip_duration)
            if (end_time - start_time) >= (clip_duration * 0.5):
                window = TemporalWindow(start_time, end_time, window_id)
                windows.append(window)
                window_id += 1
            
            start_time += stride
            
            # Break if we've covered the entire video
            if end_time >= self.duration:
                break
        
        logger.info(f"Generated {len(windows)} temporal windows (clip={clip_duration}s, overlap={overlap}s)")
        return windows
    
    def extract_frames_from_window(
        self, 
        window: TemporalWindow, 
        num_frames: int = 8,
        return_pil: bool = True
    ) -> List:
        """
        Extract uniformly sampled frames from a temporal window.
        
        Args:
            window: TemporalWindow object specifying time range
            num_frames: Number of frames to extract from the window
            return_pil: If True, return PIL Images; else return numpy arrays
            
        Returns:
            List of frames (PIL Images or numpy arrays)
        """
        try:
            # Calculate frame indices
            start_frame = int(window.start_time * self.fps)
            end_frame = int(window.end_time * self.fps)
            
            # Ensure we don't exceed video bounds
            end_frame = min(end_frame, self.total_frames - 1)
            
            # Calculate uniform sampling indices
            frame_indices = np.linspace(start_frame, end_frame, num_frames, dtype=int)
            
            frames = []
            for frame_idx in frame_indices:
                # Seek to the frame
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = self.cap.read()
                
                if not ret:
                    logger.warning(f"Failed to read frame {frame_idx}")
                    continue
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                if return_pil:
                    pil_image = Image.fromarray(frame_rgb)
                    frames.append(pil_image)
                else:
                    frames.append(frame_rgb)
            
            if len(frames) < num_frames:
                logger.warning(f"Only extracted {len(frames)}/{num_frames} frames from {window}")
            
            return frames
            
        except Exception as e:
            logger.error(f"Failed to extract frames from {window}: {e}")
            return []
    
    def extract_frames_from_time_range(
        self,
        start_time: float,
        end_time: float,
        num_frames: int = 8,
        return_pil: bool = True
    ) -> List:
        """
        Extract frames from a specific time range.
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            num_frames: Number of frames to extract
            return_pil: If True, return PIL Images; else return numpy arrays
            
        Returns:
            List of frames
        """
        window = TemporalWindow(start_time, end_time, -1)
        return self.extract_frames_from_window(window, num_frames, return_pil)
    
    def release(self):
        """Release video capture resources."""
        if self.cap is not None:
            self.cap.release()
            logger.info("Video chunker released")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
    
    def __del__(self):
        """Destructor to ensure resources are released."""
        self.release()


def extract_keyframe_from_window(video_path: str, start_time: float, end_time: float) -> Image.Image:
    """
    Extract a single keyframe from the middle of a temporal window.
    
    Args:
        video_path: Path to video file
        start_time: Start time in seconds
        end_time: End time in seconds
        
    Returns:
        PIL Image of the keyframe
    """
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        if fps <= 0:
            fps = 30.0
        
        # Get middle frame
        mid_time = (start_time + end_time) / 2.0
        mid_frame = int(mid_time * fps)
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        
        if not ret:
            raise ValueError(f"Failed to read keyframe at {mid_time}s")
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        
        cap.release()
        return pil_image
        
    except Exception as e:
        logger.error(f"Failed to extract keyframe: {e}")
        raise

