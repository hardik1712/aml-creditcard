"""
Pydantic schemas for the AML detector REST API.

Defines request/response models for transaction scoring endpoints.
All validation (type constraints, value ranges) is enforced at the API
boundary so downstream code can trust the data.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TransactionType(str, Enum):
    """Valid PaySim transaction types."""
    CASH_IN = "CASH_IN"
    CASH_OUT = "CASH_OUT"
    DEBIT = "DEBIT"
    PAYMENT = "PAYMENT"
    TRANSFER = "TRANSFER"


class RiskTier(str, Enum):
    """Risk classification tiers based on fraud probability."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransactionRequest(BaseModel):
    """Input schema for a single transaction to score.

    Mirrors the raw PaySim CSV columns. The API will compute all
    engineered features internally — callers just send raw fields.
    """
    step: int = Field(..., ge=1, description="Time step (1 step = 1 hour)")
    type: TransactionType = Field(..., description="Transaction type")
    amount: float = Field(..., ge=0, description="Transaction amount in USD")
    nameOrig: str = Field(..., min_length=1, description="Originator account ID")
    oldbalanceOrg: float = Field(..., ge=0, description="Originator balance before transaction")
    newbalanceOrig: float = Field(..., ge=0, description="Originator balance after transaction")
    nameDest: str = Field(..., min_length=1, description="Destination account ID")
    oldbalanceDest: float = Field(..., ge=0, description="Destination balance before transaction")
    newbalanceDest: float = Field(..., ge=0, description="Destination balance after transaction")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "step": 1,
                    "type": "TRANSFER",
                    "amount": 9839.64,
                    "nameOrig": "C1231006815",
                    "oldbalanceOrg": 170136.0,
                    "newbalanceOrig": 160296.36,
                    "nameDest": "M1979787155",
                    "oldbalanceDest": 0.0,
                    "newbalanceDest": 0.0,
                }
            ]
        }
    }


class PredictionResponse(BaseModel):
    """Output schema for a single transaction prediction."""
    fraud_probability: float = Field(..., ge=0, le=1, description="Probability of fraud (0–1)")
    risk_tier: RiskTier = Field(..., description="Risk classification tier")
    is_flagged: bool = Field(..., description="Whether the transaction is flagged as suspicious")
    features_used: Dict[str, float] = Field(..., description="Engineered feature values used for prediction")


class BatchTransactionRequest(BaseModel):
    """Input schema for batch transaction scoring."""
    transactions: List[TransactionRequest] = Field(
        ..., min_length=1, max_length=1000,
        description="List of transactions to score (max 1000)"
    )


class BatchPredictionResponse(BaseModel):
    """Output schema for batch transaction predictions."""
    predictions: List[PredictionResponse] = Field(..., description="Predictions for each transaction")
    summary: Dict[str, Any] = Field(..., description="Aggregate statistics for the batch")


class ModelInfoResponse(BaseModel):
    """Model metadata response."""
    model_type: str = Field(..., description="Type of ML model")
    n_features: int = Field(..., description="Number of input features")
    feature_names: List[str] = Field(..., description="Ordered list of feature names")
    risk_thresholds: Dict[str, float] = Field(..., description="Risk tier probability boundaries")
    training_metrics: Optional[Dict[str, Any]] = Field(None, description="Performance metrics from training")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    model_loaded: bool = Field(..., description="Whether the model is loaded and ready")
    version: str = Field(..., description="API version")
