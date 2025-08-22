#!/usr/bin/env python3
"""
Bazel wrapper for Streamlit UI that uses venv Python directly.
"""
import os
import sys
import subprocess

def main():
    print("🚀 Starting Streamlit UI with Bazel...")
    
    # Use the venv Python directly with streamlit
    venv_python = "/Users/vamsisuhas/scenelens/.venv/bin/python"
    ui_app = "/Users/vamsisuhas/scenelens/ui/proto/app.py"
    
    if os.path.exists(venv_python) and os.path.exists(ui_app):
        try:
            # Run streamlit using venv Python which has all packages
            subprocess.run([
                venv_python, "-m", "streamlit", "run", 
                ui_app, "--server.port", "8501"
            ], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Streamlit failed: {e}")
            sys.exit(1)
    else:
        print("❌ Virtual environment or UI app not found")
        print(f"venv python: {venv_python}")
        print(f"UI app: {ui_app}")
        sys.exit(1)

if __name__ == "__main__":
    main()
