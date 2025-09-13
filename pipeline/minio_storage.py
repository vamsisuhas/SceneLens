#!/usr/bin/env python3
"""MinIO-based storage system for video metadata and search logs."""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from minio import Minio
from minio.error import S3Error

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MinIOStorage:
    """MinIO-based storage system for video metadata and search logs."""
    
    def __init__(self, minio_client: Minio, bucket_name: str = "scenelens"):
        self.minio_client = minio_client
        self.bucket_name = bucket_name
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the bucket exists."""
        try:
            if not self.minio_client.bucket_exists(self.bucket_name):
                self.minio_client.make_bucket(self.bucket_name)
                logger.info(f"✅ Created bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"❌ Failed to create bucket: {e}")
            raise
    
    def store_video_metadata(self, video_data: Dict[str, Any]) -> str:
        """Store video metadata as JSON in MinIO."""
        try:
            video_id = str(uuid.uuid4())
            video_data['id'] = video_id
            video_data['created_at'] = datetime.now().isoformat()
            
            # Store as JSON
            metadata_path = f"videos/{video_id}/metadata.json"
            metadata_json = json.dumps(video_data, indent=2)
            
            from io import BytesIO
            
            self.minio_client.put_object(
                self.bucket_name,
                metadata_path,
                data=BytesIO(metadata_json.encode('utf-8')),
                length=len(metadata_json.encode('utf-8')),
                content_type='application/json'
            )
            
            logger.info(f"✅ Stored video metadata: {video_id}")
            return video_id
            
        except Exception as e:
            logger.error(f"❌ Failed to store video metadata: {e}")
            raise
    
    def get_video_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video metadata from MinIO."""
        try:
            metadata_path = f"videos/{video_id}/metadata.json"
            
            response = self.minio_client.get_object(self.bucket_name, metadata_path)
            metadata_json = response.read().decode('utf-8')
            metadata = json.loads(metadata_json)
            
            return metadata
            
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.warning(f"Video metadata not found: {video_id}")
                return None
            else:
                logger.error(f"❌ Failed to get video metadata: {e}")
                raise
        except Exception as e:
            logger.error(f"❌ Failed to get video metadata: {e}")
            raise
        finally:
            if 'response' in locals():
                response.close()
                response.release_conn()
    
    def list_videos(self) -> List[Dict[str, Any]]:
        """List all videos from MinIO."""
        try:
            videos = []
            
            # List all objects in videos/ prefix
            objects = self.minio_client.list_objects(
                self.bucket_name,
                prefix="videos/",
                recursive=True
            )
            
            for obj in objects:
                if obj.object_name.endswith('/metadata.json'):
                    video_id = obj.object_name.split('/')[1]
                    metadata = self.get_video_metadata(video_id)
                    if metadata:
                        videos.append(metadata)
            
            # Sort by creation date (newest first)
            videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return videos
            
        except Exception as e:
            logger.error(f"❌ Failed to list videos: {e}")
            return []
    
    def store_search_log(self, query: str, results_count: int, response_time_ms: float, search_type: str = "on_demand") -> str:
        """Store search log in MinIO."""
        try:
            log_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            log_data = {
                'id': log_id,
                'query': query,
                'results_count': results_count,
                'response_time_ms': response_time_ms,
                'search_type': search_type,
                'timestamp': timestamp
            }
            
            # Store as JSON
            log_path = f"search_logs/{timestamp}_{log_id}.json"
            log_json = json.dumps(log_data, indent=2)
            
            from io import BytesIO
            
            self.minio_client.put_object(
                self.bucket_name,
                log_path,
                data=BytesIO(log_json.encode('utf-8')),
                length=len(log_json.encode('utf-8')),
                content_type='application/json'
            )
            
            logger.info(f"✅ Stored search log: {log_id}")
            return log_id
            
        except Exception as e:
            logger.error(f"❌ Failed to store search log: {e}")
            raise
    
    def get_search_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent search logs from MinIO."""
        try:
            logs = []
            
            # List all objects in search_logs/ prefix
            objects = self.minio_client.list_objects(
                self.bucket_name,
                prefix="search_logs/",
                recursive=True
            )
            
            # Convert to list and sort by timestamp
            objects_list = list(objects)
            objects_list.sort(key=lambda x: x.object_name, reverse=True)
            
            # Get the most recent logs
            for obj in objects_list[:limit]:
                try:
                    response = self.minio_client.get_object(self.bucket_name, obj.object_name)
                    log_json = response.read().decode('utf-8')
                    log_data = json.loads(log_json)
                    logs.append(log_data)
                except Exception as e:
                    logger.warning(f"Failed to read log {obj.object_name}: {e}")
                    continue
                finally:
                    if 'response' in locals():
                        response.close()
                        response.release_conn()
            
            return logs
            
        except Exception as e:
            logger.error(f"❌ Failed to get search logs: {e}")
            return []
    
    def store_segment_data(self, video_id: str, segment_data: Dict[str, Any]) -> str:
        """Store segment data in MinIO."""
        try:
            segment_id = str(uuid.uuid4())
            segment_data['id'] = segment_id
            segment_data['video_id'] = video_id
            segment_data['created_at'] = datetime.now().isoformat()
            
            # Store as JSON
            segment_path = f"segments/{video_id}/{segment_id}.json"
            segment_json = json.dumps(segment_data, indent=2)
            
            self.minio_client.put_object(
                self.bucket_name,
                segment_path,
                data=segment_json.encode('utf-8'),
                length=len(segment_json),
                content_type='application/json'
            )
            
            logger.info(f"✅ Stored segment data: {segment_id}")
            return segment_id
            
        except Exception as e:
            logger.error(f"❌ Failed to store segment data: {e}")
            raise
    
    def get_segments_for_video(self, video_id: str) -> List[Dict[str, Any]]:
        """Get all segments for a video from MinIO."""
        try:
            segments = []
            
            # List all objects in segments/{video_id}/ prefix
            objects = self.minio_client.list_objects(
                self.bucket_name,
                prefix=f"segments/{video_id}/",
                recursive=True
            )
            
            for obj in objects:
                if obj.object_name.endswith('.json'):
                    try:
                        response = self.minio_client.get_object(self.bucket_name, obj.object_name)
                        segment_json = response.read().decode('utf-8')
                        segment_data = json.loads(segment_json)
                        segments.append(segment_data)
                    except Exception as e:
                        logger.warning(f"Failed to read segment {obj.object_name}: {e}")
                        continue
                    finally:
                        if 'response' in locals():
                            response.close()
                            response.release_conn()
            
            # Sort by timestamp
            segments.sort(key=lambda x: x.get('timestamp_seconds', 0))
            
            return segments
            
        except Exception as e:
            logger.error(f"❌ Failed to get segments for video {video_id}: {e}")
            return []
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics from MinIO."""
        try:
            # Count videos
            video_objects = list(self.minio_client.list_objects(
                self.bucket_name,
                prefix="videos/",
                recursive=True
            ))
            video_count = len([obj for obj in video_objects if obj.object_name.endswith('/metadata.json')])
            
            # Count search logs
            log_objects = list(self.minio_client.list_objects(
                self.bucket_name,
                prefix="search_logs/",
                recursive=True
            ))
            log_count = len(log_objects)
            
            # Count segments
            segment_objects = list(self.minio_client.list_objects(
                self.bucket_name,
                prefix="segments/",
                recursive=True
            ))
            segment_count = len(segment_objects)
            
            return {
                'videos': video_count,
                'search_logs': log_count,
                'segments': segment_count,
                'storage_type': 'minio_only'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get database stats: {e}")
            return {
                'videos': 0,
                'search_logs': 0,
                'segments': 0,
                'storage_type': 'minio_only',
                'error': str(e)
            }
