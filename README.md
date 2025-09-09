# SceneLens - AI Video Search System

SceneLens is an intelligent video search system that uses on-demand CLIP-based frame extraction to enable semantic search through video content using natural language queries. No pre-processing required!

## Prerequisites & Installation

### System Dependencies

**macOS:**
```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install python@3.11 ffmpeg docker
```

**Ubuntu/Debian:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-pip python3.11-venv -y

# Install FFmpeg
sudo apt install ffmpeg -y

# Install Docker
sudo apt install docker.io docker-compose -y
sudo systemctl start docker
sudo usermod -aG docker $USER
```

**Windows:**
- Install Python 3.11 from [python.org](https://python.org)
- Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/)
- Install Docker Desktop from [docker.com](https://docker.com)

### Project Setup

```bash
# Clone the repository
git clone https://github.com/vamsisuhas/SceneLens.git
cd SceneLens

# Install Python dependencies
pip install -r requirements.txt

```

## Quick Start

### 1. Start Infrastructure
```bash
cd infra && docker-compose up -d && cd ..
```

### 2. Start Backend API
```bash
python backend/app.py &
# ✅ API: http://localhost:8000
# ✅ Health Check: http://localhost:8000/health
```

### 3. Start Frontend UI
```bash
streamlit run ui/app.py --server.port 8501 &
# ✅ UI: http://localhost:8501
# ✅ Open in browser: open http://localhost:8501
```

### 4. Upload Video (On-Demand Processing)
```bash
# Upload video for on-demand search (no heavy pre-processing!)
python run_pipeline.py <video_file_path>
```

## Complete Demo (Recommended)

```bash
# 1. Start infrastructure services
cd infra && docker-compose up -d && cd ..

# 2. Upload video (instant setup - no heavy processing!)
python run_pipeline.py /path/to/your/video.mp4

# 3. Start backend API
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload &

# 4. Start frontend UI  
streamlit run ui/app.py --server.port 8501 &

# 5. Open browser and search
open http://localhost:8501
# First search takes 1-2 minutes (extracting relevant frames)
# Subsequent searches are much faster!
```

## API Endpoints

- **Health Check**: `GET http://localhost:8000/health`
- **On-Demand Search**: `GET http://localhost:8000/search/on-demand?q=query&top_k=10`
- **Video-Specific Search**: `GET http://localhost:8000/search/video/{video_id}?q=query&top_k=10`

### Example API Usage

```bash
# Health check
curl http://localhost:8000/health

# On-demand search (extracts relevant frames in real-time)
curl "http://localhost:8000/search/on-demand?q=blue+circle&top_k=5"

# Video-specific search
curl "http://localhost:8000/search/video/VIDEO_ID?q=red+strip&top_k=3"
```

## Architecture

```
SceneLens/
├── backend/          # FastAPI backend server
│   ├── app.py       # Main API application
│   └── search.py    # On-demand search engine
├── ui/              # Streamlit frontend
│   └── app.py       # Web interface
├── pipeline/        # Video processing
│   ├── ingest.py    # Lightweight video metadata storage
│   ├── on_demand_extract.py # Intelligent frame extraction
│   ├── models.py    # Database models
│   └── database.py  # Database connection
├── infra/           # Infrastructure
│   └── docker-compose.yml # PostgreSQL + MinIO
├── run_pipeline.py  # Video upload and setup
└── requirements.txt # Python dependencies
```