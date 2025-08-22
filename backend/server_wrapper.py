#!/usr/bin/env python3
"""
Bazel wrapper for FastAPI server that uses venv Python directly.
"""
import os
import sys
import subprocess

def main():
    print("🚀 Starting FastAPI backend with Bazel...")
    
    # Use the venv Python directly with the backend app
    venv_python = "/Users/vamsisuhas/scenelens/.venv/bin/python"
    backend_app = "/Users/vamsisuhas/scenelens/backend/app.py"
    
    if os.path.exists(venv_python) and os.path.exists(backend_app):
        try:
            # Run using venv Python which has all packages
            subprocess.run([venv_python, backend_app], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ FastAPI failed: {e}")
            sys.exit(1)
    else:
        print("❌ Virtual environment or backend app not found")
        print(f"venv python: {venv_python}")
        print(f"backend app: {backend_app}")
        sys.exit(1)

if __name__ == "__main__":
    main()
