"""
CLI entry point to run the unified FastAPI application (Backend + Frontend).

Usage:
    python scripts/run_app.py
"""

import subprocess
import sys
from pathlib import Path

def main():
    print("Starting AML Fraud Detection Unified App (FastAPI + HTML Frontend)...")
    
    scripts_dir = Path(__file__).parent
    
    # Run API
    api_process = subprocess.Popen(
        [sys.executable, str(scripts_dir / "run_api.py")]
    )
    
    try:
        # Wait for process to complete
        api_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down service...")
        api_process.terminate()
        api_process.wait()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
