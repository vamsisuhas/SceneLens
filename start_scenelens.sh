#!/bin/bash

# SceneLens Startup Script for HPC Cluster
# This script starts MinIO, installs dependencies, and launches the backend

echo "🚀 Starting SceneLens System..."

# Set MinIO credentials
export MINIO_ROOT_USER=scenelens
export MINIO_ROOT_PASSWORD=scenelens_dev123

echo "✅ MinIO credentials set"

# Load required modules
module load singularity/4.1.4
echo "✅ Singularity module loaded"

# Create minio_data directory if it doesn't exist
mkdir -p ./minio_data
echo "✅ MinIO data directory ready"

# Start MinIO server
echo "🔄 Starting MinIO server..."
singularity run --bind ./minio_data:/data docker://minio/minio:latest server /data --console-address ":9001" &
MINIO_PID=$!
echo "✅ MinIO started with PID: $MINIO_PID"

# Wait a moment for MinIO to start
sleep 5

# Install Python dependencies
echo "🔄 Installing Python dependencies..."
# Use python -m pip to ensure we use the correct Python from the active environment
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo "✅ Dependencies installed"

export CUDA_VISIBLE_DEVICES=""

# Start backend
echo "🔄 Starting backend server..."
python backend/app.py &
BACKEND_PID=$!
echo "✅ Backend started with PID: $BACKEND_PID"

# Wait a moment for backend to start
sleep 10

# Start frontend
echo "🔄 Starting frontend server..."
streamlit run ui/app.py --server.port 8501 &
echo "✅ Frontend started with PID: $FRONTEND_PID"

#grok the frontend
curl -X POST "http://localhost:8000/ngrok/start" \
  -H "Content-Type: application/json" \
  -d '{"auth_token": "32qJL8cRP6eJJgmmHFpnAKZimQO_6jPm5CoVDCnKuuXmQGu7n", "port": 8501}'

# Check if services are running
echo "🔍 Checking service status..."
ps aux | grep -E "(minio|python)" | grep -v grep

echo "🎉 SceneLens System Started Successfully!"
echo "📊 MinIO Console: http://localhost:9001"
echo "🔧 Backend API: http://localhost:8000"
echo "🌐 Frontend: http://localhost:8501"
echo "   curl -s http://localhost:8000/health | python -m json.tool"
