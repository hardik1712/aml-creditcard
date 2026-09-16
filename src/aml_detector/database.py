"""
Database layer for the AML Fraud Detection system.

Provides two complementary storage backends:

1. **RDBMS (SQLite via SQLAlchemy)** — Structured, relational storage for:
   - Scored transactions with prediction results
   - SAR (Suspicious Activity Report) filings
   - API audit log entries

2. **NoSQL (TinyDB)** — Document-oriented JSON storage for:
   - Full agent investigation reports (deeply nested, variable-length)
   - Copilot chat conversation histories

Design decisions:
    - SQLite is used as the RDBMS for zero-setup portability. The SQLAlchemy
      ORM layer means switching to PostgreSQL is a one-line connection string
      change.
    - TinyDB stores data as plain JSON files. It demonstrates the same
      document-store patterns as MongoDB without requiring a running server.
    - Both databases auto-create on first access (no migrations needed).
"""

import datetime
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Boolean,
    Text,
    create_engine,
    desc,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from tinydb import TinyDB, Query

from aml_detector.config import (
    DB_DIR,
    SQLITE_URL,
    TINYDB_INVESTIGATIONS_PATH,
    TINYDB_CHATS_PATH,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# RDBMS Layer — SQLAlchemy ORM (SQLite)
# ===========================================================================


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""
    pass


class TransactionRecord(Base):
    """Stores every scored transaction with its prediction outcome.

    This is the primary audit table — every call to /predict or /predict/batch
    inserts a row here so there's a full history of what the model scored.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_id = Column(String(36), unique=True, nullable=False, index=True)
    scored_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False)

    # Raw transaction fields
    step = Column(Integer, nullable=False)
    type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    name_orig = Column(String(50), nullable=False, index=True)
    old_balance_orig = Column(Float, nullable=False)
    new_balance_orig = Column(Float, nullable=False)
    name_dest = Column(String(50), nullable=False, index=True)
    old_balance_dest = Column(Float, nullable=False)
    new_balance_dest = Column(Float, nullable=False)

    # Prediction results
    fraud_probability = Column(Float, nullable=False)
    risk_tier = Column(String(10), nullable=False, index=True)
    is_flagged = Column(Boolean, nullable=False)


class SARRecord(Base):
    """Stores generated Suspicious Activity Reports (FinCEN format).

    Linked to a transaction via tx_id. Only created when the agent determines
    a transaction warrants a SAR filing (typically HIGH/CRITICAL risk).
    """
    __tablename__ = "sar_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sar_id = Column(String(36), unique=True, nullable=False, index=True)
    tx_id = Column(String(36), nullable=False, index=True)
    filed_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False)

    institution = Column(String(100), nullable=False)
    primary_subject = Column(String(50), nullable=False)
    secondary_subject = Column(String(50), nullable=False)
    transaction_amount = Column(Float, nullable=False)
    transaction_type = Column(String(20), nullable=False)
    narrative_summary = Column(Text, nullable=False)
    regulatory_classification = Column(String(100), nullable=False)
    recommended_action = Column(String(30), nullable=False)


class AuditLog(Base):
    """API audit trail — records every significant action for compliance.

    This table answers questions like "who scored what, when?" and supports
    regulatory audit requirements for financial systems.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False)
    endpoint = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Engine & Session factory
# ---------------------------------------------------------------------------

_engine = None
_SessionFactory = None


def init_rdbms() -> sessionmaker:
    """Initialize the SQLite database engine and create all tables.

    Called once during FastAPI lifespan startup. Creates the database
    file and directory if they don't exist.

    Returns
    -------
    sessionmaker
        A configured session factory for creating database sessions.
    """
    global _engine, _SessionFactory

    # Ensure the database directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(SQLITE_URL, echo=False, future=True)
    Base.metadata.create_all(_engine)
    _SessionFactory = sessionmaker(bind=_engine)

    logger.info("RDBMS initialized: %s", SQLITE_URL)
    return _SessionFactory


def get_session() -> Session:
    """Get a new database session from the factory."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_rdbms() first.")
    return _SessionFactory()


# ---------------------------------------------------------------------------
# RDBMS CRUD operations
# ---------------------------------------------------------------------------


def save_transaction(
    tx_data: Dict[str, Any],
    fraud_probability: float,
    risk_tier: str,
    is_flagged: bool,
) -> str:
    """Persist a scored transaction to the RDBMS.

    Parameters
    ----------
    tx_data : dict
        Raw transaction fields (step, type, amount, etc.)
    fraud_probability : float
        Model-predicted fraud probability.
    risk_tier : str
        Classified risk tier (LOW/MEDIUM/HIGH/CRITICAL).
    is_flagged : bool
        Whether the transaction was flagged as suspicious.

    Returns
    -------
    str
        Generated transaction ID (UUID).
    """
    tx_id = str(uuid.uuid4())
    session = get_session()
    try:
        record = TransactionRecord(
            tx_id=tx_id,
            step=tx_data.get("step", 0),
            type=tx_data.get("type", "UNKNOWN"),
            amount=tx_data.get("amount", 0.0),
            name_orig=tx_data.get("nameOrig", ""),
            old_balance_orig=tx_data.get("oldbalanceOrg", 0.0),
            new_balance_orig=tx_data.get("newbalanceOrig", 0.0),
            name_dest=tx_data.get("nameDest", ""),
            old_balance_dest=tx_data.get("oldbalanceDest", 0.0),
            new_balance_dest=tx_data.get("newbalanceDest", 0.0),
            fraud_probability=fraud_probability,
            risk_tier=risk_tier,
            is_flagged=is_flagged,
        )
        session.add(record)
        session.commit()
        logger.debug("Saved transaction %s to RDBMS", tx_id)
        return tx_id
    except Exception:
        session.rollback()
        logger.exception("Failed to save transaction to RDBMS")
        raise
    finally:
        session.close()


def save_sar(tx_id: str, sar_data: Dict[str, Any]) -> str:
    """Persist a SAR report to the RDBMS.

    Parameters
    ----------
    tx_id : str
        Associated transaction ID.
    sar_data : dict
        SAR report fields from the agent.

    Returns
    -------
    str
        The SAR ID.
    """
    session = get_session()
    try:
        record = SARRecord(
            sar_id=sar_data.get("sar_id", str(uuid.uuid4())),
            tx_id=tx_id,
            institution=sar_data.get("institution", "AML Autonomous Core Sentinel"),
            primary_subject=sar_data.get("primary_subject", ""),
            secondary_subject=sar_data.get("secondary_subject", ""),
            transaction_amount=sar_data.get("transaction_amount", 0.0),
            transaction_type=sar_data.get("transaction_type", ""),
            narrative_summary=sar_data.get("narrative_summary", ""),
            regulatory_classification=sar_data.get("regulatory_classification", ""),
            recommended_action=sar_data.get("recommended_action", ""),
        )
        session.add(record)
        session.commit()
        sar_id = record.sar_id
        logger.debug("Saved SAR %s for transaction %s", sar_id, tx_id)
        return sar_id
    except Exception:
        session.rollback()
        logger.exception("Failed to save SAR to RDBMS")
        raise
    finally:
        session.close()


def log_audit(endpoint: str, action: str, details: Optional[str] = None) -> None:
    """Write an entry to the audit log."""
    session = get_session()
    try:
        session.add(AuditLog(endpoint=endpoint, action=action, details=details))
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to write audit log")
    finally:
        session.close()


def query_transactions(
    risk_tier: Optional[str] = None,
    flagged_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Query stored transactions with optional filters.

    Parameters
    ----------
    risk_tier : str, optional
        Filter by risk tier (LOW/MEDIUM/HIGH/CRITICAL).
    flagged_only : bool
        If True, return only flagged transactions.
    limit : int
        Maximum results to return.
    offset : int
        Pagination offset.

    Returns
    -------
    list of dict
        Matching transaction records.
    """
    session = get_session()
    try:
        q = session.query(TransactionRecord)
        if risk_tier:
            q = q.filter(TransactionRecord.risk_tier == risk_tier.upper())
        if flagged_only:
            q = q.filter(TransactionRecord.is_flagged.is_(True))
        q = q.order_by(desc(TransactionRecord.scored_at))
        records = q.offset(offset).limit(limit).all()
        return [_tx_record_to_dict(r) for r in records]
    finally:
        session.close()


def get_transaction_by_id(tx_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a specific transaction by its ID."""
    session = get_session()
    try:
        record = session.query(TransactionRecord).filter_by(tx_id=tx_id).first()
        return _tx_record_to_dict(record) if record else None
    finally:
        session.close()


def query_sars(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List all SAR reports, newest first."""
    session = get_session()
    try:
        records = (
            session.query(SARRecord)
            .order_by(desc(SARRecord.filed_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_sar_record_to_dict(r) for r in records]
    finally:
        session.close()


def get_db_stats() -> Dict[str, Any]:
    """Aggregate database statistics for the /db/stats endpoint."""
    session = get_session()
    try:
        total_tx = session.query(TransactionRecord).count()
        flagged_tx = session.query(TransactionRecord).filter_by(is_flagged=True).count()
        total_sars = session.query(SARRecord).count()
        total_audits = session.query(AuditLog).count()

        # Risk tier distribution
        tier_dist = {}
        for tier in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            count = session.query(TransactionRecord).filter_by(risk_tier=tier).count()
            if count > 0:
                tier_dist[tier] = count

        return {
            "rdbms": {
                "total_transactions": total_tx,
                "flagged_transactions": flagged_tx,
                "total_sars": total_sars,
                "total_audit_entries": total_audits,
                "tier_distribution": tier_dist,
            },
            "nosql": {
                "total_investigations": get_investigation_count(),
                "total_chat_sessions": get_chat_count(),
            },
        }
    finally:
        session.close()


def _tx_record_to_dict(record: TransactionRecord) -> Dict[str, Any]:
    """Convert a TransactionRecord ORM object to a plain dictionary."""
    return {
        "tx_id": record.tx_id,
        "scored_at": record.scored_at.isoformat() if record.scored_at else None,
        "step": record.step,
        "type": record.type,
        "amount": record.amount,
        "nameOrig": record.name_orig,
        "oldbalanceOrg": record.old_balance_orig,
        "newbalanceOrig": record.new_balance_orig,
        "nameDest": record.name_dest,
        "oldbalanceDest": record.old_balance_dest,
        "newbalanceDest": record.new_balance_dest,
        "fraud_probability": record.fraud_probability,
        "risk_tier": record.risk_tier,
        "is_flagged": record.is_flagged,
    }


def _sar_record_to_dict(record: SARRecord) -> Dict[str, Any]:
    """Convert a SARRecord ORM object to a plain dictionary."""
    return {
        "sar_id": record.sar_id,
        "tx_id": record.tx_id,
        "filed_at": record.filed_at.isoformat() if record.filed_at else None,
        "institution": record.institution,
        "primary_subject": record.primary_subject,
        "secondary_subject": record.secondary_subject,
        "transaction_amount": record.transaction_amount,
        "transaction_type": record.transaction_type,
        "narrative_summary": record.narrative_summary,
        "regulatory_classification": record.regulatory_classification,
        "recommended_action": record.recommended_action,
    }


# ===========================================================================
# NoSQL Layer — TinyDB (Document Store)
# ===========================================================================

_investigations_db: Optional[TinyDB] = None
_chats_db: Optional[TinyDB] = None


def init_nosql() -> None:
    """Initialize TinyDB document stores for investigations and chats.

    Called once during FastAPI lifespan startup. Creates the JSON files
    and directory if they don't exist.
    """
    global _investigations_db, _chats_db

    DB_DIR.mkdir(parents=True, exist_ok=True)

    _investigations_db = TinyDB(str(TINYDB_INVESTIGATIONS_PATH))
    _chats_db = TinyDB(str(TINYDB_CHATS_PATH))

    logger.info(
        "NoSQL initialized: investigations=%s, chats=%s",
        TINYDB_INVESTIGATIONS_PATH,
        TINYDB_CHATS_PATH,
    )


def save_investigation(tx_id: str, investigation_data: Dict[str, Any]) -> int:
    """Store a full agent investigation report as a NoSQL document.

    The investigation contains deeply nested, variable-length data (risk
    factors, agent reasoning, SAR narratives) that maps naturally to a
    document store rather than relational tables.

    Parameters
    ----------
    tx_id : str
        Associated transaction ID (links to the RDBMS record).
    investigation_data : dict
        Full investigation response from the agent.

    Returns
    -------
    int
        TinyDB document ID.
    """
    if _investigations_db is None:
        raise RuntimeError("NoSQL not initialized. Call init_nosql() first.")

    doc = {
        "tx_id": tx_id,
        "investigated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "data": investigation_data,
    }
    doc_id = _investigations_db.insert(doc)
    logger.debug("Saved investigation for tx %s (doc_id=%d)", tx_id, doc_id)
    return doc_id


def get_investigation(tx_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an investigation report by transaction ID."""
    if _investigations_db is None:
        raise RuntimeError("NoSQL not initialized. Call init_nosql() first.")

    InvQuery = Query()
    results = _investigations_db.search(InvQuery.tx_id == tx_id)
    return results[0] if results else None


def get_all_investigations(limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve all investigation documents, most recent first."""
    if _investigations_db is None:
        raise RuntimeError("NoSQL not initialized. Call init_nosql() first.")

    all_docs = _investigations_db.all()
    # Sort by investigated_at descending
    all_docs.sort(key=lambda d: d.get("investigated_at", ""), reverse=True)
    return all_docs[:limit]


def save_chat(session_id: str, query: str, response: str, context: Optional[Dict] = None) -> int:
    """Store a copilot chat exchange as a NoSQL document.

    Chat histories are inherently unstructured — varying lengths, optional
    context, nested conversation threads — making them a natural fit for
    document storage.

    Parameters
    ----------
    session_id : str
        Chat session identifier.
    query : str
        User's query text.
    response : str
        Copilot's response text.
    context : dict, optional
        Transaction context if any.

    Returns
    -------
    int
        TinyDB document ID.
    """
    if _chats_db is None:
        raise RuntimeError("NoSQL not initialized. Call init_nosql() first.")

    doc = {
        "session_id": session_id,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "query": query,
        "response": response,
        "context": context,
    }
    doc_id = _chats_db.insert(doc)
    logger.debug("Saved chat exchange (session=%s, doc_id=%d)", session_id, doc_id)
    return doc_id


def get_chat_history(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve all chat exchanges for a given session."""
    if _chats_db is None:
        raise RuntimeError("NoSQL not initialized. Call init_nosql() first.")

    ChatQuery = Query()
    results = _chats_db.search(ChatQuery.session_id == session_id)
    results.sort(key=lambda d: d.get("timestamp", ""))
    return results


def get_investigation_count() -> int:
    """Return total number of stored investigation documents."""
    if _investigations_db is None:
        return 0
    return len(_investigations_db)


def get_chat_count() -> int:
    """Return total number of stored chat documents."""
    if _chats_db is None:
        return 0
    return len(_chats_db)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def close_all() -> None:
    """Close all database connections. Called during shutdown."""
    global _engine, _SessionFactory, _investigations_db, _chats_db

    if _engine:
        _engine.dispose()
        _engine = None
        _SessionFactory = None
        logger.info("RDBMS connection closed.")

    if _investigations_db:
        _investigations_db.close()
        _investigations_db = None

    if _chats_db:
        _chats_db.close()
        _chats_db = None

    logger.info("All database connections closed.")
