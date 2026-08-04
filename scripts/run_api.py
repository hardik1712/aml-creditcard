"""
CLI entry point for the FastAPI server.

Usage:
    python scripts/run_api.py
    python scripts/run_api.py --host 0.0.0.0 --port 8080
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aml_detector.config import API_HOST, API_PORT


def main():
    parser = argparse.ArgumentParser(description="Run the AML Fraud Detection API")
    parser.add_argument("--host", type=str, default=API_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=API_PORT, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "aml_detector.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
