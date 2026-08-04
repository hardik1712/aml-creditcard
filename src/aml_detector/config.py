"""
Centralized configuration for the AML detector project.

All magic numbers, file paths, and tunable thresholds live here.
In production, these would be pulled from environment variables or a
config file — keeping them centralized makes that migration trivial.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # two levels up from src/aml_detector/
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = OUTPUT_DIR / "figures"
MODELS_DIR = PROJECT_ROOT / "models"

# The main PaySim CSV file
PAYSIM_CSV = RAW_DATA_DIR / "PS_20174392719_1491204439457_log.csv"

# ---------------------------------------------------------------------------
# PaySim column names (avoids typos scattered across the codebase)
# ---------------------------------------------------------------------------
COL_STEP = "step"
COL_TYPE = "type"
COL_AMOUNT = "amount"
COL_NAME_ORIG = "nameOrig"
COL_OLD_BAL_ORIG = "oldbalanceOrg"
COL_NEW_BAL_ORIG = "newbalanceOrig"
COL_NAME_DEST = "nameDest"
COL_OLD_BAL_DEST = "oldbalanceDest"
COL_NEW_BAL_DEST = "newbalanceDest"
COL_IS_FRAUD = "isFraud"
COL_IS_FLAGGED = "isFlaggedFraud"

EXPECTED_COLUMNS = [
    COL_STEP, COL_TYPE, COL_AMOUNT,
    COL_NAME_ORIG, COL_OLD_BAL_ORIG, COL_NEW_BAL_ORIG,
    COL_NAME_DEST, COL_OLD_BAL_DEST, COL_NEW_BAL_DEST,
    COL_IS_FRAUD, COL_IS_FLAGGED,
]

# Transaction types in PaySim
TXTYPE_CASH_IN = "CASH_IN"
TXTYPE_CASH_OUT = "CASH_OUT"
TXTYPE_DEBIT = "DEBIT"
TXTYPE_PAYMENT = "PAYMENT"
TXTYPE_TRANSFER = "TRANSFER"
ALL_TX_TYPES = [TXTYPE_CASH_IN, TXTYPE_CASH_OUT, TXTYPE_DEBIT, TXTYPE_PAYMENT, TXTYPE_TRANSFER]

# ---------------------------------------------------------------------------
# AML thresholds & parameters
# ---------------------------------------------------------------------------
# US Bank Secrecy Act (BSA) Currency Transaction Report (CTR) threshold
STRUCTURING_THRESHOLD_USD = 10_000

# "Just under" band: transactions between $8,000 and $10,000 are suspicious
# because structurers intentionally stay below the reporting limit
STRUCTURING_BAND_LOW = 8_000
STRUCTURING_BAND_HIGH = STRUCTURING_THRESHOLD_USD

# Minimum number of sub-threshold transactions from one account to flag as
# potential smurfing (tunable — we'll refine in Phase 2)
MIN_SMURF_TX_COUNT = 5

# Fan-out/fan-in: minimum distinct counterparties to flag
MIN_FANOUT_COUNTERPARTIES = 5
MIN_FANIN_COUNTERPARTIES = 5

# Time window for velocity features (in PaySim "steps", where 1 step = 1 hour)
VELOCITY_WINDOW_STEPS = 24  # 24 hours

# Balance inconsistency tolerance (floating point rounding)
BALANCE_TOLERANCE = 0.01

# ---------------------------------------------------------------------------
# EDA settings
# ---------------------------------------------------------------------------
# Max rows to plot in distribution charts (for performance)
EDA_SAMPLE_SIZE = 500_000

# Figure DPI for saved plots
FIGURE_DPI = 150
FIGURE_SIZE = (14, 6)

# Top-N accounts to show in fan-out/fan-in charts
TOP_N_ACCOUNTS = 20

# ---------------------------------------------------------------------------
# API settings
# ---------------------------------------------------------------------------
API_HOST = "127.0.0.1"
API_PORT = 8000

# Risk tier thresholds (fraud probability boundaries)
RISK_TIER_LOW = 0.3       # probability < 0.3 → LOW
RISK_TIER_MEDIUM = 0.6    # 0.3 ≤ probability < 0.6 → MEDIUM
RISK_TIER_HIGH = 0.9      # 0.6 ≤ probability < 0.9 → HIGH
                          # probability ≥ 0.9 → CRITICAL

# Maximum batch size for /predict/batch
MAX_BATCH_SIZE = 1000

# ---------------------------------------------------------------------------
# Dashboard settings
# ---------------------------------------------------------------------------
DASHBOARD_PORT = 8501

