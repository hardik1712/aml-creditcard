"""
CLI entry point for running the feature engineering pipeline.

Usage:
    python scripts/run_features.py
    python scripts/run_features.py --nrows 100000

Reads the raw PaySim CSV, applies feature engineering, and saves
the feature matrix X and target y to data/processed/ as a Parquet file.
"""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aml_detector.data_loader import load_paysim
from aml_detector.features import build_feature_matrix
from aml_detector.config import PROCESSED_DATA_DIR, OUTPUT_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("run_features")

def main():
    parser = argparse.ArgumentParser(description="Run Feature Engineering pipeline")
    parser.add_argument("--nrows", type=int, default=None, help="Load only N rows")
    args = parser.parse_args()

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("PHASE 2: LOADING RAW DATA")
    logger.info("=" * 70)
    
    df = load_paysim(nrows=args.nrows)

    logger.info("=" * 70)
    logger.info("PHASE 2: ENGINEERING FEATURES")
    logger.info("=" * 70)
    
    X, y = build_feature_matrix(df)
    
    # Combine X and y for saving
    df_processed = X.copy()
    df_processed["isFraud"] = y.astype("int8")

    out_path = PROCESSED_DATA_DIR / "paysim_features.parquet"
    logger.info(f"Saving processed dataset to {out_path}...")
    
    df_processed.to_parquet(out_path, engine="pyarrow", compression="snappy")
    
    file_size_mb = out_path.stat().st_size / (1024 * 1024)
    logger.info(f"Saved successfully! File size: {file_size_mb:.1f} MB")
    logger.info("Feature engineering pipeline complete.")

if __name__ == "__main__":
    main()
