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


# ---------------------------------------------------------------------------
# File Upload schemas
# ---------------------------------------------------------------------------

class ColumnMapping(BaseModel):
    """Mapping from PaySim field names to actual file column names."""
    step: Optional[str] = Field(None, description="Column for time step")
    type: Optional[str] = Field(None, description="Column for transaction type")
    amount: Optional[str] = Field(None, description="Column for transaction amount")
    nameOrig: Optional[str] = Field(None, description="Column for originator account ID")
    oldbalanceOrg: Optional[str] = Field(None, description="Column for originator balance before")
    newbalanceOrig: Optional[str] = Field(None, description="Column for originator balance after")
    nameDest: Optional[str] = Field(None, description="Column for destination account ID")
    oldbalanceDest: Optional[str] = Field(None, description="Column for destination balance before")
    newbalanceDest: Optional[str] = Field(None, description="Column for destination balance after")


class UploadPreviewResponse(BaseModel):
    """Response from the /upload/preview endpoint."""
    filename: str = Field(..., description="Original filename")
    total_rows: int = Field(..., description="Total number of rows in the file")
    columns: List[str] = Field(..., description="List of column names in the file")
    preview_rows: List[Dict[str, Any]] = Field(..., description="First 5 rows of data")
    auto_mapping: Dict[str, Optional[str]] = Field(
        ..., description="Auto-detected column mapping (PaySim field → file column)"
    )


class UploadSummary(BaseModel):
    """Aggregate summary for a scored file upload."""
    total_scored: int = Field(..., description="Number of transactions scored")
    flagged_count: int = Field(..., description="Number of transactions flagged")
    avg_probability: float = Field(..., description="Average fraud probability")
    max_probability: float = Field(..., description="Maximum fraud probability")
    tier_distribution: Dict[str, int] = Field(..., description="Count of each risk tier")


class UploadPredictionResponse(BaseModel):
    """Full response from the /upload endpoint."""
    filename: str = Field(..., description="Original filename")
    total_rows: int = Field(..., description="Total rows in original file")
    column_mapping: Dict[str, Optional[str]] = Field(
        ..., description="Column mapping that was used"
    )
    warnings: List[str] = Field(default_factory=list, description="Any warnings during parsing")
    predictions: List[PredictionResponse] = Field(..., description="Per-transaction predictions")
    summary: UploadSummary = Field(..., description="Aggregate statistics")


# ---------------------------------------------------------------------------
# Agentic Pipeline & Investigation Schemas
# ---------------------------------------------------------------------------

class AgentAction(str, Enum):
    """Action determined by the autonomous AML agent."""
    AUTO_APPROVE = "AUTO_APPROVE"
    MONITOR = "MONITOR"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCK_TRANSACTION = "BLOCK_TRANSACTION"
    FREEZE_ACCOUNT = "FREEZE_ACCOUNT"


class RiskFactor(BaseModel):
    """Specific risk factor or anomaly identified by the agent."""
    category: str = Field(..., description="Category (e.g., Balance Discrepancy, Structuring, Velocity)")
    factor: str = Field(..., description="Short factor label")
    severity: str = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL")
    description: str = Field(..., description="Detailed explanation of the anomaly")


class SARReport(BaseModel):
    """Suspicious Activity Report (FinCEN compliant format)."""
    sar_id: str = Field(..., description="Unique SAR Filing Reference ID")
    filing_date: str = Field(..., description="Filing timestamp")
    institution: str = Field(default="AML Autonomous Core Sentinel", description="Filing Institution")
    primary_subject: str = Field(..., description="Originator account identifier")
    secondary_subject: str = Field(..., description="Destination account identifier")
    transaction_amount: float = Field(..., description="Reportable amount in USD")
    transaction_type: str = Field(..., description="Transaction type")
    suspicious_indicators: List[str] = Field(..., description="List of regulatory red flags")
    narrative_summary: str = Field(..., description="Comprehensive FinCEN compliance narrative")
    regulatory_classification: str = Field(..., description="e.g. BSA / AML Structuring / Money Laundering")
    recommended_action: AgentAction = Field(..., description="Recommended containment action")


class AgentInvestigationResponse(BaseModel):
    """Complete diagnostic report produced by the AML Investigation Agent."""
    transaction: TransactionRequest = Field(..., description="Original transaction details")
    fraud_probability: float = Field(..., description="ML Model fraud probability")
    risk_tier: RiskTier = Field(..., description="Risk tier")
    recommended_action: AgentAction = Field(..., description="Autonomous action")
    risk_factors: List[RiskFactor] = Field(..., description="Decomposed risk indicators")
    agent_reasoning: str = Field(..., description="Agent synthesis and decision justification")
    sar_report: Optional[SARReport] = Field(None, description="Generated SAR if risk threshold is met")


class AgentChatMessage(BaseModel):
    """Individual message in copilot conversation history."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text")


class AgentChatRequest(BaseModel):
    """Request for AML Compliance Copilot interactive chat."""
    query: str = Field(..., description="User query or instruction")
    transaction_context: Optional[TransactionRequest] = Field(None, description="Active transaction context if any")
    history: List[AgentChatMessage] = Field(default_factory=list, description="Recent conversation history")


class AgentChatResponse(BaseModel):
    """Response from AML Compliance Copilot."""
    response: str = Field(..., description="Agent assistant reply")
    suggested_questions: List[str] = Field(default_factory=list, description="Follow-up investigation queries")


class PipelineTransactionEvent(BaseModel):
    """Live transaction event processed through the agentic pipeline."""
    tx_id: str = Field(..., description="Transaction tracking ID")
    timestamp: str = Field(..., description="Event timestamp")
    step: int = Field(..., description="Time step")
    type: str = Field(..., description="Transaction type")
    amount: float = Field(..., description="Amount")
    nameOrig: str = Field(..., description="Sender account")
    nameDest: str = Field(..., description="Receiver account")
    oldbalanceOrg: float = Field(..., description="Sender balance before")
    newbalanceOrig: float = Field(..., description="Sender balance after")
    oldbalanceDest: float = Field(..., description="Receiver balance before")
    newbalanceDest: float = Field(..., description="Receiver balance after")
    fraud_probability: float = Field(..., description="Scored fraud probability")
    risk_tier: RiskTier = Field(..., description="Risk tier")
    agent_action: AgentAction = Field(..., description="Autonomous action applied")
    sar_generated: bool = Field(..., description="Whether a SAR was created")
    sar_id: Optional[str] = Field(None, description="Associated SAR ID if generated")


class PipelineStreamStatus(BaseModel):
    """Status of the automated background transaction stream."""
    is_running: bool = Field(..., description="Whether automated ingestion is active")
    speed_tps: float = Field(..., description="Transactions per second target")
    total_ingested: int = Field(..., description="Total transactions ingested")
    total_approved: int = Field(..., description="Count of auto-approved transactions")
    total_flagged: int = Field(..., description="Count of flagged/monitored transactions")
    total_sars_generated: int = Field(..., description="Count of SARs generated")
    recent_events: List[PipelineTransactionEvent] = Field(default_factory=list, description="Latest stream events")

