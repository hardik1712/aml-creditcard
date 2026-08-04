"""
Data loading and validation for the PaySim dataset.

Design decisions:
    - We downcast columns to memory-efficient dtypes. The raw CSV loads at
      ~2.5 GB; after optimization it's ~800 MB. This matters because we need
      room for feature engineering on the same machine.
    - We validate column names on load so downstream code can trust the schema.
    - The loader is a pure function (no global state) — easy to test and reuse.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from aml_detector.config import (
    PAYSIM_CSV,
    EXPECTED_COLUMNS,
    COL_STEP,
    COL_TYPE,
    COL_AMOUNT,
    COL_NAME_ORIG,
    COL_NAME_DEST,
    COL_OLD_BAL_ORIG,
    COL_NEW_BAL_ORIG,
    COL_OLD_BAL_DEST,
    COL_NEW_BAL_DEST,
    COL_IS_FRAUD,
    COL_IS_FLAGGED,
)

logger = logging.getLogger(__name__)


def load_paysim(
    filepath: Optional[Path] = None,
    nrows: Optional[int] = None,
    optimize_memory: bool = True,
) -> pd.DataFrame:
    """Load the PaySim CSV into a pandas DataFrame with optimized dtypes.

    Parameters
    ----------
    filepath : Path, optional
        Path to the CSV. Defaults to the path in config.py.
    nrows : int, optional
        Load only the first N rows (useful for quick iteration).
    optimize_memory : bool
        If True, downcast numeric columns and convert strings to categoricals.

    Returns
    -------
    pd.DataFrame
        Validated, memory-optimized PaySim data.

    Raises
    ------
    FileNotFoundError
        If the CSV does not exist at the specified path.
    ValueError
        If expected columns are missing from the CSV.
    """
    filepath = filepath or PAYSIM_CSV

    if not filepath.exists():
        raise FileNotFoundError(
            f"PaySim CSV not found at {filepath}.\n"
            f"Download it from https://www.kaggle.com/datasets/ealaxi/paysim1 "
            f"and place it in {filepath.parent}/"
        )

    logger.info("Loading PaySim data from %s ...", filepath)

    # Read with explicit dtypes to avoid pandas guessing wrong
    df = pd.read_csv(
        filepath,
        nrows=nrows,
        dtype={
            COL_STEP: np.int32,
            COL_TYPE: str,
            COL_AMOUNT: np.float64,
            COL_NAME_ORIG: str,
            COL_OLD_BAL_ORIG: np.float64,
            COL_NEW_BAL_ORIG: np.float64,
            COL_NAME_DEST: str,
            COL_OLD_BAL_DEST: np.float64,
            COL_NEW_BAL_DEST: np.float64,
            COL_IS_FRAUD: np.int8,
            COL_IS_FLAGGED: np.int8,
        },
    )

    # Validate schema
    _validate_columns(df)

    if optimize_memory:
        df = _optimize_dtypes(df)

    mem_mb = df.memory_usage(deep=True).sum() / 1e6
    logger.info(
        "Loaded %s rows x %s columns (%.1f MB in memory)",
        f"{len(df):,}",
        len(df.columns),
        mem_mb,
    )

    return df


def _validate_columns(df: pd.DataFrame) -> None:
    """Check that all expected columns are present."""
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"PaySim CSV is missing expected columns: {missing}. "
            f"Found columns: {list(df.columns)}"
        )


def _optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Downcast numeric columns and convert strings to categoricals.

    Why this matters:
        - 'type' has only 5 unique values → category saves ~90% vs object dtype
        - nameOrig/nameDest have many unique values but category still helps
          because pandas stores the underlying codes as integers
        - int8 for boolean-like columns (isFraud, isFlaggedFraud) is already set
          at load time
    """
    # Transaction type → category (5 levels)
    df[COL_TYPE] = df[COL_TYPE].astype("category")

    # Account names → category
    # Note: with ~6M rows, nameOrig has ~6M unique values (most are unique).
    # Category encoding still saves memory vs Python str objects, but the
    # savings are smaller than for low-cardinality columns.
    df[COL_NAME_ORIG] = df[COL_NAME_ORIG].astype("category")
    df[COL_NAME_DEST] = df[COL_NAME_DEST].astype("category")

    # Downcast float64 → float32 for balance columns
    # We keep 'amount' as float64 to preserve precision for large transactions
    for col in [COL_OLD_BAL_ORIG, COL_NEW_BAL_ORIG, COL_OLD_BAL_DEST, COL_NEW_BAL_DEST]:
        df[col] = df[col].astype(np.float32)

    return df


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Compute high-level summary statistics for the loaded dataset.

    Returns
    -------
    dict
        Keys: 'n_rows', 'n_cols', 'null_counts', 'dtypes', 'memory_mb',
              'step_range', 'tx_types'.
    """
    return {
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "null_counts": df.isnull().sum().to_dict(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 1),
        "step_range": (int(df[COL_STEP].min()), int(df[COL_STEP].max())),
        "tx_types": df[COL_TYPE].value_counts().to_dict(),
    }
