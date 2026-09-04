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
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
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
    UploadPreviewResponse,
    UploadPredictionResponse,
    UploadSummary,
    AgentAction,
    AgentInvestigationResponse,
    AgentChatRequest,
    AgentChatResponse,
    PipelineTransactionEvent,
    PipelineStreamStatus,
)
from aml_detector.file_parser import (
    parse_uploaded_file,
    auto_map_columns,
    validate_and_transform,
)
from aml_detector.agent import (
    investigate_transaction,
    handle_copilot_chat,
    determine_agent_action,
    evaluate_risk_factors,
    generate_sar_report,
)
from aml_detector.stream_simulator import stream_simulator

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

    # Wire up the transaction stream processor for the agentic pipeline
    stream_simulator.set_processor(_process_stream_transaction)

    yield  # App is running

    # Cleanup
    stream_simulator.stop()
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
# File Upload endpoints
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/upload/preview", response_model=UploadPreviewResponse, tags=["Upload"])
async def upload_preview(file: UploadFile = File(...)):
    """Upload a CSV/Excel file and preview its contents + auto-detected column mapping.

    Returns the first 5 rows and the auto-detected mapping so the user can
    review and adjust before scoring.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f}MB). Maximum is 10MB.",
        )

    try:
        df = parse_uploaded_file(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    mapping = auto_map_columns(df)

    # Build preview rows (first 5), converting to JSON-safe types
    preview_df = df.head(5)
    preview_rows = []
    for _, row in preview_df.iterrows():
        row_dict = {}
        for col in preview_df.columns:
            val = row[col]
            if hasattr(val, "item"):
                val = val.item()
            if pd.isna(val):
                val = None
            row_dict[str(col)] = val
        preview_rows.append(row_dict)

    return UploadPreviewResponse(
        filename=file.filename,
        total_rows=len(df),
        columns=[str(c) for c in df.columns],
        preview_rows=preview_rows,
        auto_mapping=mapping,
    )


@app.post("/upload", response_model=UploadPredictionResponse, tags=["Upload"])
async def upload_and_score(
    file: UploadFile = File(...),
    mapping_json: Optional[str] = None,
):
    """Upload a CSV/Excel file and score all transactions for fraud risk.

    Optionally provide a JSON string of column mappings to override the
    auto-detection. Format: {"amount": "My Amount Column", ...}
    """
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f}MB). Maximum is 10MB.",
        )

    # Parse the file
    try:
        df = parse_uploaded_file(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    total_rows = len(df)

    # Determine column mapping
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid mapping_json format")
    else:
        mapping = auto_map_columns(df)

    # Validate and transform
    try:
        transactions, warnings = validate_and_transform(df, mapping)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not transactions:
        raise HTTPException(
            status_code=400,
            detail="No valid transactions found after parsing and validation.",
        )

    # Score all transactions (in chunks to avoid memory issues)
    all_predictions = []
    chunk_size = MAX_BATCH_SIZE
    for i in range(0, len(transactions), chunk_size):
        chunk = transactions[i : i + chunk_size]
        for tx_dict in chunk:
            tx = TransactionRequest(**tx_dict)
            pred = _predict_single(tx)
            all_predictions.append(pred)

    # Compute summary
    probabilities = [p.fraud_probability for p in all_predictions]
    tier_counts: Dict[str, int] = {}
    for p in all_predictions:
        tier_counts[p.risk_tier.value] = tier_counts.get(p.risk_tier.value, 0) + 1

    summary = UploadSummary(
        total_scored=len(all_predictions),
        flagged_count=sum(1 for p in all_predictions if p.is_flagged),
        avg_probability=round(float(np.mean(probabilities)), 6),
        max_probability=round(float(np.max(probabilities)), 6),
        tier_distribution=tier_counts,
    )

    return UploadPredictionResponse(
        filename=file.filename,
        total_rows=total_rows,
        column_mapping=mapping,
        warnings=warnings,
        predictions=all_predictions,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Agentic Pipeline & Investigation Endpoints
# ---------------------------------------------------------------------------

async def _process_stream_transaction(tx: TransactionRequest) -> PipelineTransactionEvent:
    """Internal helper to score and triage a streaming transaction through the agent."""
    import datetime, uuid
    pred = _predict_single(tx)
    investigation = investigate_transaction(tx, pred.fraud_probability, pred.risk_tier)
    tx_id = f"TX-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")

    return PipelineTransactionEvent(
        tx_id=tx_id,
        timestamp=timestamp,
        step=tx.step,
        type=tx.type.value,
        amount=tx.amount,
        nameOrig=tx.nameOrig,
        nameDest=tx.nameDest,
        oldbalanceOrg=tx.oldbalanceOrg,
        newbalanceOrig=tx.newbalanceOrig,
        oldbalanceDest=tx.oldbalanceDest,
        newbalanceDest=tx.newbalanceDest,
        fraud_probability=pred.fraud_probability,
        risk_tier=pred.risk_tier,
        agent_action=investigation.recommended_action,
        sar_generated=investigation.sar_report is not None,
        sar_id=investigation.sar_report.sar_id if investigation.sar_report else None,
    )


@app.post("/agent/investigate", response_model=AgentInvestigationResponse, tags=["Agent"])
async def agent_investigate(transaction: TransactionRequest):
    """Execute autonomous deep investigation and SAR drafting on a single transaction."""
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    pred = _predict_single(transaction)
    return investigate_transaction(transaction, pred.fraud_probability, pred.risk_tier)


@app.post("/agent/chat", response_model=AgentChatResponse, tags=["Agent"])
async def agent_chat(request: AgentChatRequest):
    """Interactive Compliance Copilot conversational assistant."""
    return handle_copilot_chat(
        query=request.query,
        tx_context=request.transaction_context,
        history=request.history,
    )


@app.post("/pipeline/stream/start", tags=["Pipeline"])
async def start_pipeline_stream(speed_tps: float = 1.0):
    """Start automated live transaction feed simulation."""
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    stream_simulator.start(speed_tps=speed_tps)
    return {"status": "started", "speed_tps": stream_simulator.speed_tps}


@app.post("/pipeline/stream/stop", tags=["Pipeline"])
async def stop_pipeline_stream():
    """Stop the automated transaction stream."""
    stream_simulator.stop()
    return {"status": "stopped"}


@app.post("/pipeline/stream/reset", tags=["Pipeline"])
async def reset_pipeline_stream():
    """Reset stream history and counters."""
    stream_simulator.reset_stats()
    return {"status": "reset"}


@app.get("/pipeline/stream/status", response_model=PipelineStreamStatus, tags=["Pipeline"])
async def get_pipeline_stream_status():
    """Retrieve current stream status, statistics, and recent events."""
    return stream_simulator.get_status()


@app.post("/pipeline/process-batch", tags=["Pipeline"])
async def process_pipeline_batch(request: BatchTransactionRequest):
    """Ingest, score, triage, and execute agent decisions on a batch of transactions."""
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    events = []
    for tx in request.transactions:
        event = await _process_stream_transaction(tx)
        events.append(event)

    return {"events": events, "total_processed": len(events)}


# ---------------------------------------------------------------------------
# Serve Frontend UI (Vite production build)
# ---------------------------------------------------------------------------
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    logger.warning("Frontend dist/ not found. Run 'npm run build' in frontend/ to build the UI.")
