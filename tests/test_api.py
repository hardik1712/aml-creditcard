"""
Tests for the FastAPI AML detection API.

Uses FastAPI's TestClient (no actual server needed).
Tests cover health check, single prediction, batch prediction,
model info, and input validation.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient
from aml_detector.api import app


@pytest.fixture(scope="module")
def client():
    """Create a test client with the model loaded via lifespan."""
    with TestClient(app) as c:
        yield c


# A valid sample transaction for reuse across tests
SAMPLE_TRANSACTION = {
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


class TestHealthCheck:
    """Tests for GET /health."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_model_loaded(self, client):
        data = client.get("/health").json()
        assert data["model_loaded"] is True
        assert data["status"] == "healthy"

    def test_health_has_version(self, client):
        data = client.get("/health").json()
        assert "version" in data


class TestSinglePrediction:
    """Tests for POST /predict."""

    def test_predict_returns_200(self, client):
        response = client.post("/predict", json=SAMPLE_TRANSACTION)
        assert response.status_code == 200

    def test_predict_has_probability(self, client):
        data = client.post("/predict", json=SAMPLE_TRANSACTION).json()
        assert "fraud_probability" in data
        assert 0 <= data["fraud_probability"] <= 1

    def test_predict_has_risk_tier(self, client):
        data = client.post("/predict", json=SAMPLE_TRANSACTION).json()
        assert data["risk_tier"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_predict_has_features(self, client):
        data = client.post("/predict", json=SAMPLE_TRANSACTION).json()
        assert "features_used" in data
        assert "amount_log" in data["features_used"]
        assert "orig_discrepancy" in data["features_used"]

    def test_predict_cash_out_type(self, client):
        """Test with a CASH_OUT transaction."""
        tx = SAMPLE_TRANSACTION.copy()
        tx["type"] = "CASH_OUT"
        data = client.post("/predict", json=tx).json()
        assert data["features_used"]["type_CASH_OUT"] == 1.0
        assert data["features_used"]["type_TRANSFER"] == 0.0

    def test_predict_invalid_type_returns_422(self, client):
        """Invalid transaction type should return 422."""
        tx = SAMPLE_TRANSACTION.copy()
        tx["type"] = "INVALID_TYPE"
        response = client.post("/predict", json=tx)
        assert response.status_code == 422

    def test_predict_missing_field_returns_422(self, client):
        """Missing required field should return 422."""
        tx = {"step": 1, "type": "TRANSFER"}  # Missing most fields
        response = client.post("/predict", json=tx)
        assert response.status_code == 422

    def test_predict_negative_amount_returns_422(self, client):
        """Negative amount should be rejected by validation."""
        tx = SAMPLE_TRANSACTION.copy()
        tx["amount"] = -100.0
        response = client.post("/predict", json=tx)
        assert response.status_code == 422


class TestBatchPrediction:
    """Tests for POST /predict/batch."""

    def test_batch_returns_200(self, client):
        payload = {"transactions": [SAMPLE_TRANSACTION]}
        response = client.post("/predict/batch", json=payload)
        assert response.status_code == 200

    def test_batch_returns_correct_count(self, client):
        txns = [SAMPLE_TRANSACTION, SAMPLE_TRANSACTION, SAMPLE_TRANSACTION]
        payload = {"transactions": txns}
        data = client.post("/predict/batch", json=payload).json()
        assert len(data["predictions"]) == 3
        assert data["summary"]["total_scored"] == 3

    def test_batch_has_summary(self, client):
        payload = {"transactions": [SAMPLE_TRANSACTION]}
        data = client.post("/predict/batch", json=payload).json()
        summary = data["summary"]
        assert "total_scored" in summary
        assert "flagged_count" in summary
        assert "avg_probability" in summary
        assert "tier_distribution" in summary

    def test_batch_empty_returns_422(self, client):
        """Empty transaction list should fail validation."""
        payload = {"transactions": []}
        response = client.post("/predict/batch", json=payload)
        assert response.status_code == 422


class TestModelInfo:
    """Tests for GET /model/info."""

    def test_model_info_returns_200(self, client):
        response = client.get("/model/info")
        assert response.status_code == 200

    def test_model_info_has_features(self, client):
        data = client.get("/model/info").json()
        assert data["n_features"] == 22
        assert "amount_log" in data["feature_names"]

    def test_model_info_has_thresholds(self, client):
        data = client.get("/model/info").json()
        assert "risk_thresholds" in data
        assert "LOW" in data["risk_thresholds"]

    def test_model_info_has_type(self, client):
        data = client.get("/model/info").json()
        assert data["model_type"] == "LGBMClassifier"


class TestModelMetrics:
    """Tests for GET /model/metrics."""

    def test_metrics_returns_200(self, client):
        response = client.get("/model/metrics")
        assert response.status_code == 200

    def test_metrics_has_expected_keys(self, client):
        data = client.get("/model/metrics").json()
        assert "precision" in data
        assert "recall" in data
        assert "f1" in data
        assert "pr_auc" in data
