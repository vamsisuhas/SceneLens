-- SceneLens Database Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Videos table
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    duration_seconds FLOAT,
    fps FLOAT,
    width INTEGER,
    height INTEGER,
    file_size_bytes BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Segments/Frames table
CREATE TABLE IF NOT EXISTS segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    frame_number INTEGER NOT NULL,
    timestamp_seconds FLOAT NOT NULL,
    keyframe_path VARCHAR(500),
    caption TEXT,
    caption_confidence FLOAT,
    embedding_index INTEGER, -- Index in FAISS
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Search logs (optional - for analytics)
CREATE TABLE IF NOT EXISTS search_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    results_count INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_segments_video_id ON segments(video_id);
CREATE INDEX IF NOT EXISTS idx_segments_timestamp ON segments(timestamp_seconds);
CREATE INDEX IF NOT EXISTS idx_segments_frame_number ON segments(frame_number);
CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at);
