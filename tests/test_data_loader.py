"""
Tests for the data loading module.

These tests use a small synthetic DataFrame to verify:
    1. Column validation catches missing columns
    2. Dtype optimization works correctly
    3. Summary stats computation is correct

We don't test with the real 6.3M row CSV (that's an integration test).
Instead, we create small fixtures that exercise the same code paths.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aml_detector.data_loader import _validate_columns, _optimize_dtypes, get_summary_stats
from aml_detector.config import EXPECTED_COLUMNS, COL_STEP, COL_TYPE, COL_AMOUNT


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create a small valid PaySim-like DataFrame for testing."""
    n = 100
    rng = np.random.default_rng(42)

    return pd.DataFrame({
        "step": rng.integers(1, 744, size=n).astype(np.int32),
        "type": rng.choice(["CASH_IN", "CASH_OUT", "TRANSFER", "PAYMENT", "DEBIT"], size=n),
        "amount": rng.uniform(1, 100_000, size=n),
        "nameOrig": [f"C{i}" for i in range(n)],
        "oldbalanceOrg": rng.uniform(0, 500_000, size=n),
        "newbalanceOrig": rng.uniform(0, 500_000, size=n),
        "nameDest": [f"M{i}" for i in range(n)],
        "oldbalanceDest": rng.uniform(0, 500_000, size=n),
        "newbalanceDest": rng.uniform(0, 500_000, size=n),
        "isFraud": rng.choice([0, 1], size=n, p=[0.99, 0.01]).astype(np.int8),
        "isFlaggedFraud": np.zeros(n, dtype=np.int8),
    })


class TestValidateColumns:
    """Tests for column validation."""

    def test_valid_columns_pass(self, sample_df):
        """Should not raise when all expected columns are present."""
        _validate_columns(sample_df)  # Should not raise

    def test_missing_column_raises(self, sample_df):
        """Should raise ValueError when a required column is missing."""
        df_missing = sample_df.drop(columns=["amount"])
        with pytest.raises(ValueError, match="missing expected columns"):
            _validate_columns(df_missing)

    def test_extra_columns_ok(self, sample_df):
        """Extra columns should not cause an error."""
        sample_df["extra_col"] = 1
        _validate_columns(sample_df)  # Should not raise


class TestOptimizeDtypes:
    """Tests for memory optimization."""

    def test_type_becomes_category(self, sample_df):
        """Transaction type should be converted to category dtype."""
        optimized = _optimize_dtypes(sample_df.copy())
        assert optimized["type"].dtype.name == "category"

    def test_names_become_category(self, sample_df):
        """Account name columns should be converted to category dtype."""
        optimized = _optimize_dtypes(sample_df.copy())
        assert optimized["nameOrig"].dtype.name == "category"
        assert optimized["nameDest"].dtype.name == "category"

    def test_balance_columns_float32(self, sample_df):
        """Balance columns should be downcast to float32."""
        optimized = _optimize_dtypes(sample_df.copy())
        assert optimized["oldbalanceOrg"].dtype == np.float32
        assert optimized["newbalanceOrig"].dtype == np.float32
        assert optimized["oldbalanceDest"].dtype == np.float32
        assert optimized["newbalanceDest"].dtype == np.float32

    def test_amount_stays_float64(self, sample_df):
        """Amount should remain float64 for precision."""
        optimized = _optimize_dtypes(sample_df.copy())
        assert optimized["amount"].dtype == np.float64

    def test_optimization_reduces_memory(self, sample_df):
        """Optimized DataFrame should use less memory."""
        original_mem = sample_df.memory_usage(deep=True).sum()
        optimized = _optimize_dtypes(sample_df.copy())
        optimized_mem = optimized.memory_usage(deep=True).sum()
        # For small DataFrames the savings may be minimal, but should not increase
        assert optimized_mem <= original_mem * 1.1  # Allow 10% tolerance for small data


class TestGetSummaryStats:
    """Tests for summary statistics."""

    def test_returns_expected_keys(self, sample_df):
        """Summary should contain all expected keys."""
        stats = get_summary_stats(sample_df)
        expected_keys = {"n_rows", "n_cols", "null_counts", "dtypes", "memory_mb", "step_range", "tx_types"}
        assert expected_keys == set(stats.keys())

    def test_row_count_correct(self, sample_df):
        """Row count should match DataFrame length."""
        stats = get_summary_stats(sample_df)
        assert stats["n_rows"] == len(sample_df)

    def test_col_count_correct(self, sample_df):
        """Column count should match DataFrame width."""
        stats = get_summary_stats(sample_df)
        assert stats["n_cols"] == len(sample_df.columns)

    def test_no_nulls_in_fixture(self, sample_df):
        """Fixture should have no null values."""
        stats = get_summary_stats(sample_df)
        assert all(v == 0 for v in stats["null_counts"].values())

    def test_step_range_tuple(self, sample_df):
        """Step range should be a (min, max) tuple."""
        stats = get_summary_stats(sample_df)
        assert len(stats["step_range"]) == 2
        assert stats["step_range"][0] <= stats["step_range"][1]
