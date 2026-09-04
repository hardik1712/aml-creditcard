"""
Tests for the Autonomous AML Investigation Agent, SAR Generation, and Copilot.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aml_detector.api import app
from aml_detector.agent import (
    evaluate_risk_factors,
    determine_agent_action,
    generate_sar_report,
    investigate_transaction,
    handle_copilot_chat,
)
from aml_detector.schemas import (
    TransactionRequest,
    TransactionType,
    RiskTier,
    AgentAction,
)


@pytest.fixture(scope="module")
def client():
    """Create a test client with the model loaded via lifespan."""
    with TestClient(app) as c:
        yield c


SAMPLE_FRAUD_TRANSACTION = {
    "step": 12,
    "type": "TRANSFER",
    "amount": 181920.0,
    "nameOrig": "C1231006815",
    "oldbalanceOrg": 181920.0,
    "newbalanceOrig": 0.0,
    "nameDest": "M1979787155",
    "oldbalanceDest": 0.0,
    "newbalanceDest": 0.0,
}

SAMPLE_NORMAL_TRANSACTION = {
    "step": 14,
    "type": "PAYMENT",
    "amount": 42.50,
    "nameOrig": "C9988776655",
    "oldbalanceOrg": 500.0,
    "newbalanceOrig": 457.50,
    "nameDest": "M1122334455",
    "oldbalanceDest": 0.0,
    "newbalanceDest": 0.0,
}


class TestAgentLogic:
    """Unit tests for agent evaluation rules."""

    def test_evaluate_balance_drain_factor(self):
        tx = TransactionRequest(**SAMPLE_FRAUD_TRANSACTION)
        factors = evaluate_risk_factors(tx, proba=0.95, risk_tier=RiskTier.CRITICAL)
        assert any(f.factor == "Full Balance Drain" for f in factors)
        assert any(f.category == "Account Liquidation" for f in factors)

    def test_action_determination_critical(self):
        tx = TransactionRequest(**SAMPLE_FRAUD_TRANSACTION)
        factors = evaluate_risk_factors(tx, proba=0.95, risk_tier=RiskTier.CRITICAL)
        action = determine_agent_action(RiskTier.CRITICAL, 0.95, factors)
        assert action == AgentAction.FREEZE_ACCOUNT

    def test_action_determination_low(self):
        tx = TransactionRequest(**SAMPLE_NORMAL_TRANSACTION)
        factors = evaluate_risk_factors(tx, proba=0.01, risk_tier=RiskTier.LOW)
        action = determine_agent_action(RiskTier.LOW, 0.01, factors)
        assert action == AgentAction.AUTO_APPROVE

    def test_sar_generation_for_critical_risk(self):
        tx = TransactionRequest(**SAMPLE_FRAUD_TRANSACTION)
        factors = evaluate_risk_factors(tx, proba=0.95, risk_tier=RiskTier.CRITICAL)
        action = determine_agent_action(RiskTier.CRITICAL, 0.95, factors)
        sar = generate_sar_report(tx, 0.95, RiskTier.CRITICAL, factors, action)
        assert sar is not None
        assert sar.sar_id.startswith("SAR-")
        assert "SUSPICIOUS ACTIVITY NARRATIVE REPORT" in sar.narrative_summary
        assert sar.primary_subject == tx.nameOrig

    def test_sar_not_generated_for_low_risk(self):
        tx = TransactionRequest(**SAMPLE_NORMAL_TRANSACTION)
        factors = evaluate_risk_factors(tx, proba=0.01, risk_tier=RiskTier.LOW)
        action = determine_agent_action(RiskTier.LOW, 0.01, factors)
        sar = generate_sar_report(tx, 0.01, RiskTier.LOW, factors, action)
        assert sar is None


class TestAgentEndpoints:
    """Integration tests for agent FastAPI endpoints."""

    def test_agent_investigate_endpoint(self, client):
        response = client.post("/agent/investigate", json=SAMPLE_FRAUD_TRANSACTION)
        assert response.status_code == 200
        data = response.json()
        assert "fraud_probability" in data
        assert "recommended_action" in data
        assert "risk_factors" in data
        assert "agent_reasoning" in data
        assert len(data["risk_factors"]) > 0

    def test_agent_chat_endpoint(self, client):
        payload = {
            "query": "Why was this transaction flagged?",
            "transaction_context": SAMPLE_FRAUD_TRANSACTION,
            "history": [],
        }
        response = client.post("/agent/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "suggested_questions" in data
        assert len(data["suggested_questions"]) > 0

    def test_pipeline_stream_endpoints(self, client):
        # Start stream
        start_res = client.post("/pipeline/stream/start?speed_tps=2.0")
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "started"

        # Check status
        status_res = client.get("/pipeline/stream/status")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["is_running"] is True

        # Stop stream
        stop_res = client.post("/pipeline/stream/stop")
        assert stop_res.status_code == 200
        assert stop_res.json()["status"] == "stopped"

    def test_pipeline_process_batch_endpoint(self, client):
        payload = {"transactions": [SAMPLE_FRAUD_TRANSACTION, SAMPLE_NORMAL_TRANSACTION]}
        res = client.post("/pipeline/process-batch", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["total_processed"] == 2
        assert len(data["events"]) == 2
        assert "agent_action" in data["events"][0]
