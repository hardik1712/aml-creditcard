"""
FastAPI REST API for AML fraud detection.

Loads the trained LightGBM model at startup and exposes endpoints for:
    - Health checks
    - Single and batch transaction scoring
    - Model info and metrics

Design decisions:
    - The API accepts raw transaction fields and engineers features internally.
      Callers don't need to know about the feature pipeline.
    - Velocity/graph features (orig_hist_count, orig_hist_volume, orig_out_degree,
      dest_in_degree, orig_degree_ratio) require historical context that isn't
      available for single-transaction scoring. They default to 0.
    - The model is loaded once at startup via a lifespan context manager.
"""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from aml_detector.config import (
    MODELS_DIR,
    OUTPUT_DIR,
    RISK_TIER_LOW,
    RISK_TIER_MEDIUM,
    RISK_TIER_HIGH,
    MAX_BATCH_SIZE,
)
from aml_detector.schemas import (
    TransactionRequest,
    PredictionResponse,
    BatchTransactionRequest,
    BatchPredictionResponse,
    ModelInfoResponse,
    HealthResponse,
    RiskTier,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global model reference (set during lifespan startup)
# ---------------------------------------------------------------------------
_model = None
_model_features: List[str] = []
_training_metrics: Dict[str, Any] = {}


def _classify_risk(probability: float) -> RiskTier:
    """Map a fraud probability to a risk tier."""
    if probability < RISK_TIER_LOW:
        return RiskTier.LOW
    elif probability < RISK_TIER_MEDIUM:
        return RiskTier.MEDIUM
    elif probability < RISK_TIER_HIGH:
        return RiskTier.HIGH
    else:
        return RiskTier.CRITICAL


def _transaction_to_features(tx: TransactionRequest) -> Dict[str, float]:
    """Convert a raw transaction request into the 22-feature vector the model expects.

    This mirrors the logic in features.py but for a single transaction without
    historical context. Velocity and graph features default to 0.
    """
    features = {}

    # Basic time features (1 step = 1 hour)
    features["hour_of_day"] = float(tx.step % 24)
    features["day_of_month"] = float(tx.step // 24)

    # Log-transformed amount
    features["amount_log"] = float(np.log1p(tx.amount))

    # One-hot encode transaction type
    for t in ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]:
        features[f"type_{t}"] = 1.0 if tx.type.value == t else 0.0

    # Discrepancy features
    orig_expected = tx.oldbalanceOrg - tx.amount
    features["orig_discrepancy"] = float(tx.newbalanceOrig - orig_expected)
    features["orig_is_balanced"] = 1.0 if abs(features["orig_discrepancy"]) <= 0.01 else 0.0

    dest_expected = tx.oldbalanceDest + tx.amount
    features["dest_discrepancy"] = float(tx.newbalanceDest - dest_expected)
    features["dest_is_balanced"] = 1.0 if abs(features["dest_discrepancy"]) <= 0.01 else 0.0

    # Velocity features — require historical data, default to 0
    features["orig_hist_count"] = 0.0
    features["orig_hist_volume"] = 0.0

    # Graph features — require full dataset, default to 0
    features["orig_out_degree"] = 0.0
    features["dest_in_degree"] = 0.0
    features["orig_degree_ratio"] = 0.0

    # Raw numeric columns
    features["amount"] = float(tx.amount)
    features["oldbalanceOrg"] = float(tx.oldbalanceOrg)
    features["newbalanceOrig"] = float(tx.newbalanceOrig)
    features["oldbalanceDest"] = float(tx.oldbalanceDest)
    features["newbalanceDest"] = float(tx.newbalanceDest)

    return features


def _predict_single(tx: TransactionRequest) -> PredictionResponse:
    """Score a single transaction."""
    features = _transaction_to_features(tx)

    # Build a DataFrame row in the exact feature order the model expects
    feature_row = pd.DataFrame([{f: features[f] for f in _model_features}])
    feature_row = feature_row.astype(np.float32)

    # Predict
    proba = float(_model.predict_proba(feature_row)[0, 1])
    risk_tier = _classify_risk(proba)

    return PredictionResponse(
        fraud_probability=round(proba, 6),
        risk_tier=risk_tier,
        is_flagged=proba >= RISK_TIER_LOW,
        features_used=features,
    )


# ---------------------------------------------------------------------------
# FastAPI app with lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model and metrics at startup, clean up on shutdown."""
    global _model, _model_features, _training_metrics

    model_path = MODELS_DIR / "lgb_model.joblib"
    if not model_path.exists():
        logger.error("Model file not found at %s", model_path)
        raise RuntimeError(
            f"Model not found at {model_path}. "
            "Run scripts/run_modeling.py first."
        )

    logger.info("Loading model from %s ...", model_path)
    _model = joblib.load(model_path)
    _model_features = _model.feature_name_
    logger.info("Model loaded. Features: %s", _model_features)

    # Load training metrics if available
    metrics_path = OUTPUT_DIR / "model_metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            _training_metrics = json.load(f)
        logger.info("Loaded training metrics from %s", metrics_path)

    yield  # App is running

    # Cleanup
    _model = None
    logger.info("Model unloaded.")


app = FastAPI(
    title="AML Fraud Detection API",
    description=(
        "Real-time fraud scoring for financial transactions using a LightGBM model "
        "trained on PaySim data. Supports single and batch prediction with risk "
        "tier classification."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check API health and model readiness."""
    return HealthResponse(
        status="healthy",
        model_loaded=_model is not None,
        version="1.0.0",
    )


@app.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
async def predict_single(transaction: TransactionRequest):
    """Score a single transaction for fraud risk.

    Accepts raw PaySim transaction fields. The API computes all engineered
    features internally.

    **Note**: Velocity and graph features (orig_hist_count, orig_hist_volume,
    orig_out_degree, dest_in_degree, orig_degree_ratio) require historical
    context and will default to 0 for single-transaction scoring.
    """
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    return _predict_single(transaction)


@app.post("/predict/batch", response_model=BatchPredictionResponse, tags=["Prediction"])
async def predict_batch(request: BatchTransactionRequest):
    """Score a batch of transactions for fraud risk.

    Accepts up to 1000 transactions at once. Returns individual predictions
    plus aggregate summary statistics.
    """
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    if len(request.transactions) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size {len(request.transactions)} exceeds maximum of {MAX_BATCH_SIZE}",
        )

    predictions = [_predict_single(tx) for tx in request.transactions]

    # Compute summary statistics
    probabilities = [p.fraud_probability for p in predictions]
    tier_counts = {}
    for p in predictions:
        tier_counts[p.risk_tier.value] = tier_counts.get(p.risk_tier.value, 0) + 1

    summary = {
        "total_scored": len(predictions),
        "flagged_count": sum(1 for p in predictions if p.is_flagged),
        "avg_probability": round(float(np.mean(probabilities)), 6),
        "max_probability": round(float(np.max(probabilities)), 6),
        "tier_distribution": tier_counts,
    }

    return BatchPredictionResponse(predictions=predictions, summary=summary)


@app.get("/model/info", response_model=ModelInfoResponse, tags=["Model"])
async def model_info():
    """Get model metadata: type, features, risk thresholds, and training metrics."""
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    return ModelInfoResponse(
        model_type=type(_model).__name__,
        n_features=len(_model_features),
        feature_names=list(_model_features),
        risk_thresholds={
            "LOW": RISK_TIER_LOW,
            "MEDIUM": RISK_TIER_MEDIUM,
            "HIGH": RISK_TIER_HIGH,
        },
        training_metrics=_training_metrics if _training_metrics else None,
    )


@app.get("/model/metrics", tags=["Model"])
async def model_metrics():
    """Return the saved training metrics (model_metrics.json)."""
    if not _training_metrics:
        raise HTTPException(status_code=404, detail="No training metrics available")
    return _training_metrics


# ---------------------------------------------------------------------------
# Serve Frontend UI
# ---------------------------------------------------------------------------
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    logger.warning("Frontend directory not found. UI will not be served.")
