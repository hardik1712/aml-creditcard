"""
CLI entry point for running the ML modeling pipeline.

Usage:
    python scripts/run_modeling.py
    python scripts/run_modeling.py --sample 0.1  # Train on 10% of data for quick iteration

This script:
    1. Loads the engineered feature matrix (Parquet)
    2. Splits into train/test sets (stratified)
    3. Trains a LightGBM model
    4. Evaluates performance (PR-AUC, F1, Confusion Matrix)
    5. Extracts SHAP values and saves summary plot
    6. Saves the trained model
"""

import argparse
import logging
import sys
import json
from pathlib import Path
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aml_detector.models import train_lightgbm, evaluate_model, extract_shap_values
from aml_detector.config import PROCESSED_DATA_DIR, OUTPUT_DIR, MODELS_DIR, COL_IS_FRAUD

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIR / "modeling_log.txt", mode="w")
    ]
)
logger = logging.getLogger("run_modeling")


def main():
    parser = argparse.ArgumentParser(description="Run ML Modeling Pipeline")
    parser.add_argument("--sample", type=float, default=1.0, help="Fraction of data to use (e.g., 0.1 for 10%)")
    args = parser.parse_args()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data_path = PROCESSED_DATA_DIR / "paysim_features.parquet"
    if not data_path.exists():
        logger.error(f"Features file not found at {data_path}. Run scripts/run_features.py first.")
        sys.exit(1)

    logger.info("=" * 70)
    logger.info("PHASE 3: LOADING FEATURES")
    logger.info("=" * 70)
    
    df = pd.read_parquet(data_path)
    logger.info(f"Loaded {len(df):,} rows.")
    
    if args.sample < 1.0:
        # Stratified sampling to preserve fraud ratio
        df, _ = train_test_split(df, train_size=args.sample, stratify=df[COL_IS_FRAUD], random_state=42)
        logger.info(f"Sampled down to {len(df):,} rows ({args.sample*100}%).")

    # Separate X and y
    y = df[COL_IS_FRAUD]
    X = df.drop(columns=[COL_IS_FRAUD])
    
    logger.info("=" * 70)
    logger.info("PHASE 3: TRAIN / TEST SPLIT")
    logger.info("=" * 70)
    
    # Stratified split is crucial for highly imbalanced data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    
    logger.info(f"Train size: {len(X_train):,} | Test size: {len(X_test):,}")
    logger.info(f"Fraud in train: {y_train.sum():,} | Fraud in test: {y_test.sum():,}")

    logger.info("=" * 70)
    logger.info("PHASE 3: MODEL TRAINING (LightGBM)")
    logger.info("=" * 70)
    
    model = train_lightgbm(X_train, y_train)

    logger.info("=" * 70)
    logger.info("PHASE 3: EVALUATION")
    logger.info("=" * 70)
    
    metrics = evaluate_model(model, X_test, y_test)
    
    # Save metrics
    metrics_path = OUTPUT_DIR / "model_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    
    logger.info("=" * 70)
    logger.info("PHASE 3: EXPLAINABILITY (SHAP)")
    logger.info("=" * 70)
    
    # SHAP on 6M rows is slow. Sample 10k rows from test set for the plot
    shap_sample_size = min(10000, len(X_test))
    X_shap = X_test.sample(shap_sample_size, random_state=42)
    extract_shap_values(model, X_shap)
    
    logger.info("=" * 70)
    logger.info("PHASE 3: SAVING MODEL")
    logger.info("=" * 70)
    
    model_path = MODELS_DIR / "lgb_model.joblib"
    joblib.dump(model, model_path)
    logger.info(f"Model saved to {model_path}")
    logger.info("Modeling pipeline complete.")


if __name__ == "__main__":
    main()
