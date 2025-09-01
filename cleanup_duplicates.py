#!/usr/bin/env python3
"""Clean up duplicate segments in the database."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pipeline.database import get_db_session
from pipeline.models import Video, Segment
from sqlalchemy import func

def cleanup_duplicate_segments():
    """Remove duplicate segments from the database."""
    db = get_db_session()
    
    try:
        # Get all videos
        videos = db.query(Video).all()
        
        for video in videos:
            print(f"Processing video: {video.filename}")
            
            # Get all segments for this video
            segments = db.query(Segment).filter(
                Segment.video_id == video.id
            ).order_by(Segment.timestamp_seconds).all()
            
            print(f"  Found {len(segments)} total segments")
            
            # Group segments by timestamp
            segments_by_timestamp = {}
            for segment in segments:
                timestamp = segment.timestamp_seconds
                if timestamp not in segments_by_timestamp:
                    segments_by_timestamp[timestamp] = []
                segments_by_timestamp[timestamp].append(segment)
            
            # Remove duplicates (keep the first one at each timestamp)
            segments_to_delete = []
            for timestamp, segment_list in segments_by_timestamp.items():
                if len(segment_list) > 1:
                    # Keep the first one, delete the rest
                    for segment in segment_list[1:]:
                        segments_to_delete.append(segment)
            
            print(f"  Found {len(segments_to_delete)} duplicate segments to remove")
            
            # Delete duplicate segments
            for segment in segments_to_delete:
                db.delete(segment)
            
            db.commit()
            print(f"  Cleaned up {len(segments_to_delete)} duplicate segments")
        
        print("✅ Database cleanup completed!")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_duplicate_segments()
