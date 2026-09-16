"""
Unit tests for the Database layer (RDBMS + NoSQL).

Tests SQLAlchemy ORM operations (transactions, SARs, audit log) and
TinyDB document storage (investigations, chats) without requiring
a running API server.
"""

import sys
import tempfile
import shutil
from pathlib import Path

import pytest

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def temp_db_dir(monkeypatch, tmp_path):
    """Create a temporary database directory for each test.

    Patches the config paths so tests don't write to the real data/ directory.
    This ensures each test starts with a clean database.
    """
    import aml_detector.config as config
    import aml_detector.database as database

    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Patch config paths
    monkeypatch.setattr(config, "DB_DIR", db_dir)
    monkeypatch.setattr(config, "SQLITE_URL", f"sqlite:///{db_dir / 'test.db'}")
    monkeypatch.setattr(config, "TINYDB_INVESTIGATIONS_PATH", db_dir / "test_investigations.json")
    monkeypatch.setattr(config, "TINYDB_CHATS_PATH", db_dir / "test_chats.json")

    # Also patch the database module's imports (it reads config at import time)
    monkeypatch.setattr(database, "DB_DIR", db_dir)
    monkeypatch.setattr(database, "SQLITE_URL", f"sqlite:///{db_dir / 'test.db'}")
    monkeypatch.setattr(database, "TINYDB_INVESTIGATIONS_PATH", db_dir / "test_investigations.json")
    monkeypatch.setattr(database, "TINYDB_CHATS_PATH", db_dir / "test_chats.json")

    # Initialize both database backends
    database.init_rdbms()
    database.init_nosql()

    yield db_dir

    # Cleanup
    database.close_all()


# ===========================================================================
# RDBMS Tests (SQLAlchemy / SQLite)
# ===========================================================================

class TestTransactionCRUD:
    """Test CRUD operations for the TransactionRecord ORM model."""

    SAMPLE_TX = {
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

    def test_save_transaction_returns_uuid(self):
        """save_transaction should return a valid UUID string."""
        from aml_detector.database import save_transaction

        tx_id = save_transaction(
            tx_data=self.SAMPLE_TX,
            fraud_probability=0.95,
            risk_tier="CRITICAL",
            is_flagged=True,
        )
        assert tx_id is not None
        assert len(tx_id) == 36  # UUID format: 8-4-4-4-12

    def test_retrieve_transaction_by_id(self):
        """Saved transactions should be retrievable by their ID."""
        from aml_detector.database import save_transaction, get_transaction_by_id

        tx_id = save_transaction(
            tx_data=self.SAMPLE_TX,
            fraud_probability=0.87,
            risk_tier="HIGH",
            is_flagged=True,
        )
        record = get_transaction_by_id(tx_id)

        assert record is not None
        assert record["tx_id"] == tx_id
        assert record["amount"] == 181920.0
        assert record["risk_tier"] == "HIGH"
        assert record["fraud_probability"] == 0.87

    def test_query_transactions_no_filter(self):
        """query_transactions with no filters should return all records."""
        from aml_detector.database import save_transaction, query_transactions

        # Insert 3 transactions
        for i in range(3):
            tx = {**self.SAMPLE_TX, "amount": 100.0 * (i + 1)}
            save_transaction(tx, fraud_probability=0.1 * i, risk_tier="LOW", is_flagged=False)

        results = query_transactions()
        assert len(results) == 3

    def test_query_transactions_filter_by_risk_tier(self):
        """query_transactions should filter by risk_tier."""
        from aml_detector.database import save_transaction, query_transactions

        save_transaction(self.SAMPLE_TX, 0.95, "CRITICAL", True)
        save_transaction({**self.SAMPLE_TX, "amount": 50.0}, 0.1, "LOW", False)
        save_transaction({**self.SAMPLE_TX, "amount": 75.0}, 0.5, "MEDIUM", True)

        critical = query_transactions(risk_tier="CRITICAL")
        assert len(critical) == 1
        assert critical[0]["risk_tier"] == "CRITICAL"

        low = query_transactions(risk_tier="LOW")
        assert len(low) == 1
        assert low[0]["risk_tier"] == "LOW"

    def test_query_transactions_flagged_only(self):
        """query_transactions with flagged_only should filter unflagged records."""
        from aml_detector.database import save_transaction, query_transactions

        save_transaction(self.SAMPLE_TX, 0.95, "CRITICAL", True)
        save_transaction({**self.SAMPLE_TX, "amount": 10.0}, 0.05, "LOW", False)

        flagged = query_transactions(flagged_only=True)
        assert len(flagged) == 1
        assert flagged[0]["is_flagged"] is True

    def test_query_transactions_pagination(self):
        """query_transactions should support limit and offset."""
        from aml_detector.database import save_transaction, query_transactions

        for i in range(5):
            save_transaction(
                {**self.SAMPLE_TX, "amount": float(i)},
                0.1, "LOW", False,
            )

        page1 = query_transactions(limit=2, offset=0)
        page2 = query_transactions(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        # Pages should not overlap
        ids1 = {r["tx_id"] for r in page1}
        ids2 = {r["tx_id"] for r in page2}
        assert ids1.isdisjoint(ids2)

    def test_nonexistent_transaction_returns_none(self):
        """get_transaction_by_id should return None for unknown IDs."""
        from aml_detector.database import get_transaction_by_id

        assert get_transaction_by_id("nonexistent-uuid") is None


class TestSARCRUD:
    """Test CRUD operations for the SARRecord ORM model."""

    SAMPLE_SAR = {
        "sar_id": "SAR-TEST-001",
        "institution": "AML Autonomous Core Sentinel",
        "primary_subject": "C1231006815",
        "secondary_subject": "M1979787155",
        "transaction_amount": 181920.0,
        "transaction_type": "TRANSFER",
        "narrative_summary": "Suspicious full balance drain detected.",
        "regulatory_classification": "BSA / AML / Account Liquidation",
        "recommended_action": "FREEZE_ACCOUNT",
    }

    def test_save_sar(self):
        """save_sar should persist a SAR record."""
        from aml_detector.database import save_sar, query_sars

        sar_id = save_sar("test-tx-123", self.SAMPLE_SAR)
        assert sar_id == "SAR-TEST-001"

        sars = query_sars()
        assert len(sars) == 1
        assert sars[0]["sar_id"] == "SAR-TEST-001"
        assert sars[0]["tx_id"] == "test-tx-123"

    def test_query_sars_ordering(self):
        """query_sars should return results newest first."""
        from aml_detector.database import save_sar, query_sars
        import time

        save_sar("tx-1", {**self.SAMPLE_SAR, "sar_id": "SAR-001"})
        time.sleep(0.1)
        save_sar("tx-2", {**self.SAMPLE_SAR, "sar_id": "SAR-002"})

        sars = query_sars()
        assert len(sars) == 2
        # Most recent should be first
        assert sars[0]["sar_id"] == "SAR-002"


class TestAuditLog:
    """Test the audit logging functionality."""

    def test_log_audit_entry(self):
        """log_audit should write an entry without raising."""
        from aml_detector.database import log_audit

        # Should not raise
        log_audit("/test", "unit_test", "Testing audit log")

    def test_audit_entries_accumulate(self):
        """Multiple audit entries should be persisted."""
        from aml_detector.database import log_audit, get_db_stats

        log_audit("/test1", "action1")
        log_audit("/test2", "action2")
        log_audit("/test3", "action3")

        stats = get_db_stats()
        assert stats["rdbms"]["total_audit_entries"] >= 3


# ===========================================================================
# NoSQL Tests (TinyDB)
# ===========================================================================

class TestInvestigationStore:
    """Test TinyDB document storage for investigation reports."""

    SAMPLE_INVESTIGATION = {
        "fraud_probability": 0.95,
        "risk_tier": "CRITICAL",
        "recommended_action": "FREEZE_ACCOUNT",
        "risk_factors": [
            {
                "category": "Account Liquidation",
                "factor": "Full Balance Drain",
                "severity": "CRITICAL",
                "description": "Full balance drained in single operation.",
            }
        ],
        "agent_reasoning": "Multiple critical risk indicators identified.",
    }

    def test_save_investigation(self):
        """save_investigation should return a positive document ID."""
        from aml_detector.database import save_investigation

        doc_id = save_investigation("tx-inv-001", self.SAMPLE_INVESTIGATION)
        assert doc_id > 0

    def test_retrieve_investigation(self):
        """get_investigation should return the stored document."""
        from aml_detector.database import save_investigation, get_investigation

        save_investigation("tx-inv-002", self.SAMPLE_INVESTIGATION)
        doc = get_investigation("tx-inv-002")

        assert doc is not None
        assert doc["tx_id"] == "tx-inv-002"
        assert doc["data"]["risk_tier"] == "CRITICAL"
        assert len(doc["data"]["risk_factors"]) == 1

    def test_investigation_not_found(self):
        """get_investigation should return None for unknown tx_id."""
        from aml_detector.database import get_investigation

        assert get_investigation("nonexistent") is None

    def test_list_all_investigations(self):
        """get_all_investigations should return all stored documents."""
        from aml_detector.database import save_investigation, get_all_investigations

        save_investigation("tx-1", {"tier": "LOW"})
        save_investigation("tx-2", {"tier": "HIGH"})
        save_investigation("tx-3", {"tier": "CRITICAL"})

        docs = get_all_investigations()
        assert len(docs) == 3

    def test_investigation_count(self):
        """get_investigation_count should track document count."""
        from aml_detector.database import save_investigation, get_investigation_count

        assert get_investigation_count() == 0
        save_investigation("tx-1", {"data": "test"})
        assert get_investigation_count() == 1


class TestCopilotChatStore:
    """Test TinyDB document storage for copilot chat histories."""

    def test_save_chat(self):
        """save_chat should return a positive document ID."""
        from aml_detector.database import save_chat

        doc_id = save_chat(
            session_id="sess-001",
            query="What is AML?",
            response="Anti-Money Laundering is...",
        )
        assert doc_id > 0

    def test_retrieve_chat_history(self):
        """get_chat_history should return all chats for a session."""
        from aml_detector.database import save_chat, get_chat_history

        save_chat("sess-002", "Question 1", "Answer 1")
        save_chat("sess-002", "Question 2", "Answer 2")
        save_chat("sess-other", "Other question", "Other answer")

        history = get_chat_history("sess-002")
        assert len(history) == 2
        assert history[0]["query"] == "Question 1"
        assert history[1]["query"] == "Question 2"

    def test_chat_with_context(self):
        """save_chat with transaction context should store it."""
        from aml_detector.database import save_chat, get_chat_history

        context = {"amount": 10000.0, "type": "TRANSFER"}
        save_chat("sess-ctx", "Analyze this", "Analysis...", context=context)

        history = get_chat_history("sess-ctx")
        assert len(history) == 1
        assert history[0]["context"]["amount"] == 10000.0


class TestDatabaseStats:
    """Test the aggregate statistics function."""

    def test_stats_empty_database(self):
        """get_db_stats should work on an empty database."""
        from aml_detector.database import get_db_stats

        stats = get_db_stats()
        assert stats["rdbms"]["total_transactions"] == 0
        assert stats["rdbms"]["total_sars"] == 0
        assert stats["nosql"]["total_investigations"] == 0
        assert stats["nosql"]["total_chat_sessions"] == 0

    def test_stats_with_data(self):
        """get_db_stats should reflect stored records."""
        from aml_detector.database import (
            save_transaction, save_sar, save_investigation,
            save_chat, get_db_stats,
        )

        save_transaction(
            {"step": 1, "type": "TRANSFER", "amount": 100.0,
             "nameOrig": "A", "oldbalanceOrg": 100.0, "newbalanceOrig": 0.0,
             "nameDest": "B", "oldbalanceDest": 0.0, "newbalanceDest": 100.0},
            fraud_probability=0.9, risk_tier="CRITICAL", is_flagged=True,
        )
        save_sar("tx-1", {
            "sar_id": "SAR-STAT-01",
            "institution": "Test",
            "primary_subject": "A",
            "secondary_subject": "B",
            "transaction_amount": 100.0,
            "transaction_type": "TRANSFER",
            "narrative_summary": "Test",
            "regulatory_classification": "Test",
            "recommended_action": "FREEZE_ACCOUNT",
        })
        save_investigation("inv-1", {"test": True})
        save_chat("chat-1", "Q", "A")

        stats = get_db_stats()
        assert stats["rdbms"]["total_transactions"] == 1
        assert stats["rdbms"]["flagged_transactions"] == 1
        assert stats["rdbms"]["total_sars"] == 1
        assert stats["rdbms"]["tier_distribution"]["CRITICAL"] == 1
        assert stats["nosql"]["total_investigations"] == 1
        assert stats["nosql"]["total_chat_sessions"] == 1
