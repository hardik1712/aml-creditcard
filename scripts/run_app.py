"""
CLI entry point to run the unified AML Fraud Detection application.

In dev mode (default):
  - Starts FastAPI via uvicorn (port 8000)
  - Starts Vite dev server (port 5173) with hot reload

In production: build the frontend first with `cd frontend && npm run build`,
then just run `python scripts/run_api.py`.

Usage:
    python scripts/run_app.py           # dev mode
    python scripts/run_app.py --prod    # production (FastAPI serves dist/)
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main():
    args = sys.argv[1:]
    prod = '--prod' in args

    print("AML Fraud Detection -- Unified App")

    if prod:
        print(">> Production mode: FastAPI serving frontend/dist/")
        print("   Visit: http://127.0.0.1:8000")
        api = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "run_api.py")])
        try:
            api.wait()
        except KeyboardInterrupt:
            api.terminate()
            api.wait()
    else:
        print(">> Dev mode: Vite (port 5173) + FastAPI (port 8000)")
        print("   Visit: http://localhost:5173")
        api   = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "run_api.py")])
        vite  = subprocess.Popen(["npm", "run", "dev"], cwd=str(ROOT / "frontend"), shell=True)
        try:
            api.wait()
            vite.wait()
        except KeyboardInterrupt:
            print("\nShutting down…")
            api.terminate()
            vite.terminate()
            api.wait()
            vite.wait()
            print("Done.")


if __name__ == "__main__":
    main()

