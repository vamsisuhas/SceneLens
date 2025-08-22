# SceneLens - Video Search with AI

SceneLens is a video search system that uses CLIP and BLIP models to enable semantic search through video content using natural language queries.

## Week 1 Setup and Pipeline

### Prerequisites & Installation

**Fresh Device Setup (Complete Installation Guide):**

#### 1. **Install System Dependencies**

**macOS:**
```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install python@3.11 ffmpeg docker

# Install Bazel 7 (required version)
brew install bazel@7
export PATH="/opt/homebrew/opt/bazel@7/bin:$PATH"
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

# Install Bazel 7
sudo apt install apt-transport-https curl gnupg -y
curl -fsSL https://bazel.build/bazel-release.pub.gpg | gpg --dearmor >bazel-archive-keyring.gpg
sudo mv bazel-archive-keyring.gpg /usr/share/keyrings
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/bazel-archive-keyring.gpg] https://storage.googleapis.com/bazel-apt stable jdk1.8" | sudo tee /etc/apt/sources.list.d/bazel.list
sudo apt update && sudo apt install bazel-7.6.1 -y
```

**Windows:**
```bash
# Install Python 3.11 from python.org
# Download FFmpeg from https://ffmpeg.org/
# Install Docker Desktop from docker.com
# Install Bazelisk from GitHub releases
# Add all to PATH environment variable
```

#### 2. **Clone & Setup Project**
```bash
# Clone the repository
git clone https://github.com/vamsisuhas/SceneLens.git
cd SceneLens

# Make Bazel 7 permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export PATH="/opt/homebrew/opt/bazel@7/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Quick Start (Clean Bazel Architecture)

**One-Time Setup:**
```bash
# 1. Set Bazel 7 PATH (add to ~/.zshrc to make permanent)
export PATH="/opt/homebrew/opt/bazel@7/bin:$PATH"

# 2. Install Python packages (one-time only)
pip install -r requirements.txt

# 3. Start infrastructure services  
cd infra && docker-compose up -d && cd ..
```

**Run SceneLens:**
```bash
# Set Bazel PATH (if not permanent)
export PATH="/opt/homebrew/opt/bazel@7/bin:$PATH"

# Start backend API
bazel run //backend:server &
# ✅ API: http://localhost:8000

# Start Streamlit UI  
bazel run //ui:app
# ✅ UI: http://localhost:8501

# Run complete pipeline (optional)
bazel run //:pipeline -- data/videos/tiny_demo.mp4
```

**Quick Demo:**
```bash
# Start services and test with sample video
bazel run //backend:server &
bazel run //ui:app &
bazel run //:pipeline -- data/videos/tiny_demo.mp4

# Open browser: http://localhost:8501
# Search for: "pink sky" or "water"
```