"""
Machine learning models for AML fraud detection.

Handles training (with class imbalance optimization), evaluation, and explainability.
"""

import logging
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import (
    precision_score, recall_score, f1_score, 
    average_precision_score, confusion_matrix
)
import shap
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

from aml_detector.config import FIGURES_DIR, FIGURE_DPI, FIGURE_SIZE

logger = logging.getLogger(__name__)

def train_lightgbm(X_train: pd.DataFrame, y_train: pd.Series) -> lgb.LGBMClassifier:
    """Train a LightGBM classifier with built-in class weight handling.
    
    Why LightGBM?
        - Blazing fast on 6M+ rows compared to XGBoost/RandomForest.
        - Handles missing values natively.
        - 'is_unbalance=True' automatically adjusts weights inversely proportional 
          to class frequencies, which avoids the massive RAM/time cost of SMOTE.
    """
    logger.info("Training LightGBM model on %d rows...", len(X_train))
    
    model = lgb.LGBMClassifier(
        n_estimators=150,
        learning_rate=0.05,
        max_depth=7,
        num_leaves=63,
        is_unbalance=True, # Critical for 774:1 imbalance
        random_state=42,
        n_jobs=-1
    )
    
    # Cast to float32 to prevent C-level pointer access violations in LightGBM on Windows
    # when reading from parquet files with mixed precision types
    X_train_clean = X_train.astype(np.float32)
    y_train_clean = y_train.astype(np.int32)
    
    model.fit(X_train_clean, y_train_clean)
    logger.info("Model training complete.")
    return model


def evaluate_model(model: Any, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, Any]:
    """Evaluate the model using metrics appropriate for severe imbalance."""
    logger.info("Evaluating model on %d test rows...", len(X_test))
    
    X_test_clean = X_test.astype(np.float32)
    y_pred = model.predict(X_test_clean)
    y_prob = model.predict_proba(X_test_clean)[:, 1]
    
    # Standard metrics
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    # PR-AUC (Precision-Recall Area Under Curve)
    # This is much more sensitive to false positives on imbalanced data than ROC-AUC
    pr_auc = average_precision_score(y_test, y_prob)
    
    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    metrics = {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "pr_auc": float(pr_auc),
        "confusion_matrix": {
            "True Negatives": int(tn),
            "False Positives": int(fp),
            "False Negatives": int(fn),
            "True Positives": int(tp)
        }
    }
    
    logger.info("Evaluation Results:")
    logger.info(f"  PR-AUC:    {pr_auc:.4f}")
    logger.info(f"  Precision: {precision:.4f}")
    logger.info(f"  Recall:    {recall:.4f}")
    logger.info(f"  F1 Score:  {f1:.4f}")
    logger.info(f"  Confusion Matrix: TP={tp}, FP={fp}, FN={fn}, TN={tn}")
    
    return metrics


def extract_shap_values(model: Any, X_sample: pd.DataFrame, filename: str = "08_shap_summary.png"):
    """Extract and plot SHAP values to explain model decisions.
    
    SHAP explains the *why* behind the model's predictions, which is 
    essential for AML compliance and investigation teams.
    """
    logger.info("Computing SHAP values for explainability...")
    
    # SHAP TreeExplainer is extremely fast for LightGBM
    X_sample_clean = X_sample.astype(np.float32)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample_clean)
    
    # LightGBM binary classification sometimes returns a list of [negative_class_shap, positive_class_shap]
    # We want the positive class (fraud)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    
    # Generate summary plot
    fig = plt.figure(figsize=FIGURE_SIZE)
    # summary_plot creates its own figure by default if not passed, but we can capture the current axis
    ax = plt.gca()
    shap.summary_plot(shap_values, X_sample_clean, show=False)
    
    # Save figure
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FIGURES_DIR / filename
    plt.savefig(out_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close()
    
    logger.info(f"SHAP summary plot saved to {out_path}")
