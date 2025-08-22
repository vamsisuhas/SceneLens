# SceneLens - Video Search with AI

SceneLens is a video search system that uses CLIP and BLIP models to enable semantic search through video content using natural language queries.

## Week 1 Setup and Pipeline

### Prerequisites

1. **Python 3.11+**: Already configured in your Bazel WORKSPACE
2. **Bazel**: For building and running the project
3. **Docker**: For PostgreSQL and MinIO services
4. **FFmpeg**: For video processing

Install FFmpeg:
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/
```

### Quick Start (WORKING Pure Bazel Solution)

**Prerequisites:**
```bash
# 1. Install Python packages (one-time setup)
pip install -r requirements.txt

# 2. Start infrastructure services  
cd infra && docker-compose up -d && cd ..

# 3. Set Bazel 7 PATH (required for compatibility)
export PATH="/opt/homebrew/opt/bazel@7/bin:$PATH"
```

**Run SceneLens:**
```bash
# 1. Run complete pipeline
bazel run //:pipeline -- samples/sample_video.mp4

# 2. Start backend API (runs in background)
bazel run //backend:server &
# ✅ API available at: http://localhost:8000

# 3. Start Streamlit UI  
bazel run //ui:app
# ✅ UI available at: http://localhost:8501
```

**🎯 Everything runs through pure Bazel!**

5. **Start UI (in another terminal)**
   ```bash
   bazel run //ui:app
   ```

6. **Open in Browser**
   - UI: http://localhost:8501
   - API Docs: http://localhost:8000/docs
   - MinIO Console: http://localhost:9001

### Manual Pipeline Steps

If you prefer to run steps individually:

```bash
# 1. Ingest video
bazel run //pipeline:ingest -- data/videos/sample.mp4

# 2. Extract keyframes
bazel run //pipeline:keyframe -- data/videos/sample.mp4

# 3. Generate captions
bazel run //pipeline:captions -- data/frames/sample

# 4. Generate embeddings
bazel run //pipeline:vision_embed -- data/frames/sample

# 5. Build search index
bazel run //pipeline:fuse_index -- artifacts/embeddings.json --captions artifacts/captions.json
```

### Project Structure

```
scenelens/
├── WORKSPACE              # Bazel workspace configuration
├── BUILD                  # Root build file
├── requirements_lock.txt  # Python dependencies
├── infra/                 # Docker infrastructure
│   ├── docker-compose.yml
│   └── init.sql
├── pipeline/              # Data processing pipeline
│   ├── BUILD
│   ├── ingest.py         # Video ingestion
│   ├── keyframe.py       # Keyframe extraction
│   ├── captions.py       # BLIP-2 caption generation
│   ├── vision_embed.py   # CLIP embedding generation
│   ├── fuse_index.py     # FAISS index building
│   ├── models.py         # Database models
│   └── database.py       # Database connection
├── backend/               # FastAPI search API
│   ├── BUILD
│   ├── app.py            # FastAPI application
│   └── search.py         # Search engine
├── ui/                    # Streamlit user interface
│   ├── BUILD
│   └── proto/app.py      # Streamlit app
└── scripts/               # Utility scripts
    ├── BUILD
    └── run_pipeline.py   # Complete pipeline runner
```

### Data Flow

1. **Video** → Ingest → Standardized MP4
2. **MP4** → Keyframes → JPEG frames at regular intervals
3. **Frames** → BLIP-2 → Text captions
4. **Frames** → CLIP → Vector embeddings
5. **Embeddings** → FAISS → Searchable index
6. **Metadata** → PostgreSQL → Structured data

### Search Types

- **Semantic Search**: Uses CLIP embeddings for visual similarity
- **Caption Search**: Text matching in generated captions

### Example Queries

- "a person walking"
- "drone flying over landscape"
- "car on highway"
- "people in meeting"
- "sunset over mountains"

### Troubleshooting

**FAISS Index Issues**:
- Make sure embeddings were generated successfully
- Check that `faiss/keyframes.index` exists

**Model Download Issues**:
- First run downloads large models (1-2GB total)
- Ensure stable internet connection
- Models are cached in `~/.cache/huggingface/`

**Database Connection Issues**:
- Ensure Docker services are running: `docker-compose ps`
- Check logs: `docker-compose logs postgres`

**FFmpeg Issues**:
- Ensure FFmpeg is installed and in PATH
- Test with: `ffmpeg -version`

### Development

**Running Tests**:
```bash
bazel test //...
```

**Building Specific Targets**:
```bash
bazel build //pipeline:captions
bazel build //backend:server
```

**Viewing Dependencies**:
```bash
bazel query --output=graph //... | dot -Tpng -o deps.png
```

### Configuration

**Database**: Edit `infra/docker-compose.yml` for different credentials
**Models**: Change model names in Python files for different CLIP/BLIP variants
**Paths**: Modify paths in scripts for different data directories

### Next Steps (Week 2+)

- Add more sophisticated scene detection
- Implement temporal video understanding
- Add user feedback and model fine-tuning
- Build React-based UI
- Add video streaming capabilities
