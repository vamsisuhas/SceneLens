# SceneLens - AI Video Search System

SceneLens is an intelligent video search system that uses CLIP and BLIP models to enable semantic search through video content using natural language queries.

## 🚀 Demo Status

**Current Demo State:**
- ✅ Infrastructure: PostgreSQL + MinIO running
- ✅ Backend API: Running on http://localhost:8000
- ✅ Frontend UI: Running on http://localhost:8501
- ✅ Sample Video: Processed with 5 keyframes
- ✅ Search Index: FAISS with 5 vectors ready
- ✅ Web Interface: Fully functional with image display

**Quick Access:**
- **🌐 Web UI**: [http://localhost:8501](http://localhost:8501)
- **🔧 API Health**: [http://localhost:8000/health](http://localhost:8000/health)
- **📚 API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

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

# Fix NumPy compatibility (if needed)
pip install 'numpy<2.0'

```

## Quick Start

### 1. Start Infrastructure
```bash
cd infra && docker-compose up -d && cd ..
```

### 2. Start Backend API
```bash
# Method 1: Direct Python (background)
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload &

# Method 2: Python script (alternative)
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

### 4. Process Video (Optional)
```bash
# Run complete pipeline to process a video
python run_pipeline.py data/videos/your_video.mp4
```

## Complete Demo (Recommended)

```bash
# 1. Start infrastructure services
cd infra && docker-compose up -d && cd ..

# 2. Create and process sample video
mkdir -p data/videos data/frames artifacts faiss
ffmpeg -f lavfi -i testsrc=duration=10:size=320x240:rate=1 -pix_fmt yuv420p data/videos/demo.mp4 -y
python run_pipeline.py data/videos/demo.mp4

# 3. Start backend API (choose one method)
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload &
# OR: python backend/app.py &

# 4. Start frontend UI  
streamlit run ui/app.py --server.port 8501 &

# 5. Open browser and search
open http://localhost:8501

# ✅ Try these searches:
# - "colorful circle"
# - "black background"
# - "geometric patterns"
# - "bright colors"
```

## API Endpoints

- **Health Check**: `GET http://localhost:8000/health`
- **Semantic Search**: `GET http://localhost:8000/search?q=query&top_k=10`
- **Caption Search**: `GET http://localhost:8000/search/caption?q=query&top_k=10`

### Example API Usage

```bash
# Health check
curl http://localhost:8000/health

# Semantic search
curl "http://localhost:8000/search?q=colorful+circle&top_k=5"

# Caption search  
curl "http://localhost:8000/search/caption?q=circle&top_k=3"
```

## Architecture

```
SceneLens/
├── backend/          # FastAPI backend server
│   ├── app.py       # Main API application
│   └── search.py    # Search engine logic
├── ui/              # Streamlit frontend
│   └── app.py       # Web interface
├── pipeline/        # Video processing pipeline
│   ├── ingest.py    # Video ingestion
│   ├── keyframe.py  # Frame extraction
│   ├── captions.py  # AI caption generation
│   ├── vision_embed.py # CLIP embeddings
│   └── fuse_index.py   # Search index creation
├── infra/           # Infrastructure
│   └── docker-compose.yml # PostgreSQL + MinIO
└── requirements.txt # Python dependencies
```

## Features

- 🎬 **Video Processing**: Automatic keyframe extraction and analysis
- 🧠 **AI Models**: CLIP for vision, BLIP for captions
- 🔍 **Semantic Search**: Natural language video search
- 🖼️ **Visual Interface**: Clean Streamlit web UI
- 🚀 **Fast API**: RESTful backend with FastAPI
- 📊 **Vector Search**: FAISS-powered similarity search
- 🗄️ **Data Storage**: PostgreSQL + MinIO object storage
