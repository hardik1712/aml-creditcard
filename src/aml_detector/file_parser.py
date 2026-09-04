"""
File parser for uploaded transaction data (CSV / Excel).

Handles:
    - Reading CSV and Excel files into a pandas DataFrame
    - Auto-mapping user column names to the 9 required PaySim fields
    - Validating and filling missing optional columns with sensible defaults
"""

import io
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required and optional field definitions
# ---------------------------------------------------------------------------

# Fields that MUST be present (or mappable) for scoring to work
REQUIRED_FIELDS = ["type", "amount", "nameOrig", "nameDest"]

# Fields that are useful but can default to 0 if missing
OPTIONAL_FIELDS_WITH_DEFAULTS = {
    "step": 1,
    "oldbalanceOrg": 0.0,
    "newbalanceOrig": 0.0,
    "oldbalanceDest": 0.0,
    "newbalanceDest": 0.0,
}

ALL_FIELDS = REQUIRED_FIELDS + list(OPTIONAL_FIELDS_WITH_DEFAULTS.keys())

# ---------------------------------------------------------------------------
# Synonym dictionary for fuzzy column matching
# ---------------------------------------------------------------------------
# Maps each PaySim field to a list of common aliases (all lowercased for
# case-insensitive matching). The first exact match wins.

COLUMN_SYNONYMS: Dict[str, List[str]] = {
    "step": [
        "step", "time_step", "timestep", "hour", "time", "period",
        "time_period", "timestamp",
    ],
    "type": [
        "type", "transaction_type", "txn_type", "trans_type",
        "transaction type", "txn type", "tx_type", "category",
    ],
    "amount": [
        "amount", "transaction_amount", "txn_amount", "value", "sum",
        "transaction amount", "txn amount", "transfer_amount",
        "transfer amount", "payment_amount", "payment amount",
    ],
    "nameOrig": [
        "nameorig", "name_orig", "sender", "from", "originator",
        "source_account", "source account", "from_account", "from account",
        "payer", "sender_id", "sender id", "orig_account", "orig account",
        "originator_id", "originator id", "sender_account", "sender account",
    ],
    "oldbalanceOrg": [
        "oldbalanceorg", "old_balance_org", "oldbalance_org",
        "sender_balance_before", "sender balance before",
        "orig_balance_before", "orig balance before",
        "old_balance_sender", "balance_before_sender",
        "sender_old_balance", "sender old balance",
    ],
    "newbalanceOrig": [
        "newbalanceorig", "new_balance_orig", "newbalance_orig",
        "sender_balance_after", "sender balance after",
        "orig_balance_after", "orig balance after",
        "new_balance_sender", "balance_after_sender",
        "sender_new_balance", "sender new balance",
    ],
    "nameDest": [
        "namedest", "name_dest", "receiver", "to", "destination",
        "dest_account", "dest account", "to_account", "to account",
        "payee", "beneficiary", "receiver_id", "receiver id",
        "destination_id", "destination id", "recipient",
        "receiver_account", "receiver account",
    ],
    "oldbalanceDest": [
        "oldbalancedest", "old_balance_dest", "oldbalance_dest",
        "receiver_balance_before", "receiver balance before",
        "dest_balance_before", "dest balance before",
        "old_balance_receiver", "balance_before_receiver",
        "receiver_old_balance", "receiver old balance",
    ],
    "newbalanceDest": [
        "newbalancedest", "new_balance_dest", "newbalance_dest",
        "receiver_balance_after", "receiver balance after",
        "dest_balance_after", "dest balance after",
        "new_balance_receiver", "balance_after_receiver",
        "receiver_new_balance", "receiver new balance",
    ],
}

# Valid transaction types the model understands
VALID_TX_TYPES = {"CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_uploaded_file(
    file_bytes: bytes,
    filename: str,
) -> pd.DataFrame:
    """Read an uploaded CSV or Excel file into a DataFrame.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        filename: Original filename (used to determine format).

    Returns:
        A pandas DataFrame with the file's contents.

    Raises:
        ValueError: If the file format is unsupported or the file is empty.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    else:
        raise ValueError(
            f"Unsupported file format '.{ext}'. "
            "Please upload a .csv, .xlsx, or .xls file."
        )

    if df.empty:
        raise ValueError("The uploaded file is empty (0 rows).")

    logger.info("Parsed %s: %d rows × %d columns", filename, len(df), len(df.columns))
    return df


# ---------------------------------------------------------------------------
# Auto-mapping
# ---------------------------------------------------------------------------

def auto_map_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Auto-detect which file columns correspond to the 9 PaySim fields.

    Uses case-insensitive matching against the synonym dictionary.

    Args:
        df: The parsed DataFrame.

    Returns:
        A dict mapping PaySim field names to detected file column names.
        If a field can't be matched, its value is None.
    """
    file_columns = list(df.columns)
    # Build a lowercase lookup: lowered_name → original_name
    lower_to_original = {str(c).lower().strip(): c for c in file_columns}

    mapping: Dict[str, Optional[str]] = {}
    used_columns: set = set()

    for field, synonyms in COLUMN_SYNONYMS.items():
        matched = None
        for synonym in synonyms:
            if synonym in lower_to_original and lower_to_original[synonym] not in used_columns:
                matched = lower_to_original[synonym]
                used_columns.add(matched)
                break
        mapping[field] = matched

    logger.info("Auto-mapped columns: %s", mapping)
    return mapping


# ---------------------------------------------------------------------------
# Validation & transformation
# ---------------------------------------------------------------------------

def validate_and_transform(
    df: pd.DataFrame,
    mapping: Dict[str, Optional[str]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Apply column mapping, validate, fill defaults, and return transaction dicts.

    Args:
        df: The parsed DataFrame.
        mapping: A dict mapping PaySim field names to file column names.

    Returns:
        A tuple of (transactions, warnings).
        - transactions: List of dicts ready for the prediction API.
        - warnings: List of human-readable warning messages.
    """
    warnings: List[str] = []

    # Check required fields
    missing_required = [
        f for f in REQUIRED_FIELDS if mapping.get(f) is None
    ]
    if missing_required:
        raise ValueError(
            f"Missing required columns (could not auto-detect): "
            f"{', '.join(missing_required)}. "
            f"Available columns: {list(df.columns)}"
        )

    # Build a renamed DataFrame with only the mapped columns
    rename_map = {}
    for field, col in mapping.items():
        if col is not None:
            rename_map[col] = field

    df_mapped = df.rename(columns=rename_map)

    # Fill optional fields with defaults if not present
    for field, default_val in OPTIONAL_FIELDS_WITH_DEFAULTS.items():
        if field not in df_mapped.columns:
            df_mapped[field] = default_val
            warnings.append(
                f"Column '{field}' not found in file — defaulting to {default_val}."
            )

    # Normalize transaction type values
    if "type" in df_mapped.columns:
        df_mapped["type"] = df_mapped["type"].astype(str).str.upper().str.strip()
        # Replace common alternative names
        type_replacements = {
            "CASHOUT": "CASH_OUT",
            "CASH OUT": "CASH_OUT",
            "CASHIN": "CASH_IN",
            "CASH IN": "CASH_IN",
            "WIRE": "TRANSFER",
            "WIRE TRANSFER": "TRANSFER",
        }
        df_mapped["type"] = df_mapped["type"].replace(type_replacements)

        invalid_types = set(df_mapped["type"].unique()) - VALID_TX_TYPES
        if invalid_types:
            warnings.append(
                f"Unknown transaction types found: {invalid_types}. "
                f"These rows will be skipped. Valid types: {VALID_TX_TYPES}."
            )
            df_mapped = df_mapped[df_mapped["type"].isin(VALID_TX_TYPES)]

    # Coerce numeric columns
    numeric_fields = [
        "amount", "oldbalanceOrg", "newbalanceOrig",
        "oldbalanceDest", "newbalanceDest", "step",
    ]
    for field in numeric_fields:
        if field in df_mapped.columns:
            df_mapped[field] = pd.to_numeric(df_mapped[field], errors="coerce")

    # Drop rows where required numeric fields are NaN
    before_count = len(df_mapped)
    df_mapped = df_mapped.dropna(subset=["amount"])
    dropped = before_count - len(df_mapped)
    if dropped > 0:
        warnings.append(f"Dropped {dropped} rows with missing/invalid amount values.")

    # Fill remaining NaN in numeric fields with 0
    for field in numeric_fields:
        if field in df_mapped.columns:
            df_mapped[field] = df_mapped[field].fillna(0)

    # Ensure step is an integer >= 1
    df_mapped["step"] = df_mapped["step"].astype(int).clip(lower=1)

    # Ensure string fields are strings
    for field in ["nameOrig", "nameDest"]:
        if field in df_mapped.columns:
            df_mapped[field] = df_mapped[field].astype(str).str.strip()

    # Build transaction dicts
    output_fields = ALL_FIELDS
    transactions = []
    for _, row in df_mapped.iterrows():
        tx = {}
        for field in output_fields:
            if field in row.index:
                val = row[field]
                # Convert numpy types to native Python types
                if hasattr(val, "item"):
                    val = val.item()
                tx[field] = val
        transactions.append(tx)

    logger.info(
        "Validated %d transactions (%d warnings)",
        len(transactions), len(warnings),
    )
    return transactions, warnings
