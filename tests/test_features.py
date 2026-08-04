"""
Tests for the feature engineering module.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aml_detector.features import (
    create_basic_features,
    create_discrepancy_features,
    create_velocity_features,
    create_graph_features,
    build_feature_matrix
)
from aml_detector.config import (
    COL_STEP, COL_TYPE, COL_AMOUNT, COL_NAME_ORIG, COL_NAME_DEST,
    COL_OLD_BAL_ORIG, COL_NEW_BAL_ORIG, COL_OLD_BAL_DEST, COL_NEW_BAL_DEST,
    COL_IS_FRAUD
)

@pytest.fixture
def feature_sample_df() -> pd.DataFrame:
    """Create a small DataFrame with known edge cases for testing features."""
    return pd.DataFrame({
        COL_STEP: [1, 2, 25, 26, 1], # 25 is next day
        COL_TYPE: ["TRANSFER", "CASH_OUT", "TRANSFER", "PAYMENT", "TRANSFER"],
        COL_AMOUNT: [100.0, 50.0, 1000.0, 10.0, 200.0],
        COL_NAME_ORIG: ["A", "A", "A", "B", "C"],
        COL_OLD_BAL_ORIG: [200.0, 100.0, 50.0, 10.0, 200.0],
        COL_NEW_BAL_ORIG: [100.0, 50.0, 0.0, 0.0, 0.0], # A's 3rd tx is unbalanced (0 instead of -950)
        COL_NAME_DEST: ["X", "Y", "X", "Z", "X"], # X receives from A and C (in-degree 2)
        COL_OLD_BAL_DEST: [0.0, 0.0, 100.0, 0.0, 1100.0],
        COL_NEW_BAL_DEST: [100.0, 50.0, 1100.0, 10.0, 1300.0],
        COL_IS_FRAUD: [0, 0, 1, 0, 0]
    })


def test_create_basic_features(feature_sample_df):
    feats = create_basic_features(feature_sample_df)
    
    # Check time features
    assert feats["hour_of_day"].iloc[0] == 1
    assert feats["day_of_month"].iloc[2] == 1 # step 25 is day 1, hour 1
    
    # Check log amount
    assert np.isclose(feats["amount_log"].iloc[0], np.log1p(100.0))
    
    # Check one-hot encoding (should have columns for the types present)
    assert "type_TRANSFER" in feats.columns
    assert "type_CASH_OUT" in feats.columns


def test_create_discrepancy_features(feature_sample_df):
    feats = create_discrepancy_features(feature_sample_df)
    
    # Row 0: old=200, amt=100 -> exp_new=100. actual_new=100. disc=0
    assert np.isclose(feats["orig_discrepancy"].iloc[0], 0.0)
    assert feats["orig_is_balanced"].iloc[0] == 1
    
    # Row 2 (A's 3rd tx): old=50, amt=1000 -> exp_new=-950. actual_new=0. disc=0 - (-950) = +950
    assert np.isclose(feats["orig_discrepancy"].iloc[2], 950.0)
    assert feats["orig_is_balanced"].iloc[2] == 0


def test_create_velocity_features(feature_sample_df):
    feats = create_velocity_features(feature_sample_df)
    
    # A has 3 transactions
    # 1st tx (idx 0): prev count=0, prev vol=0
    assert feats["orig_hist_count"].iloc[0] == 0
    assert feats["orig_hist_volume"].iloc[0] == 0.0
    
    # 2nd tx (idx 1): prev count=1, prev vol=100
    assert feats["orig_hist_count"].iloc[1] == 1
    assert feats["orig_hist_volume"].iloc[1] == 100.0
    
    # 3rd tx (idx 2): prev count=2, prev vol=150
    assert feats["orig_hist_count"].iloc[2] == 2
    assert feats["orig_hist_volume"].iloc[2] == 150.0
    
    # B's 1st tx (idx 3):
    assert feats["orig_hist_count"].iloc[3] == 0


def test_create_graph_features(feature_sample_df):
    feats = create_graph_features(feature_sample_df)
    
    # A sends to X and Y -> out_degree = 2
    assert feats["orig_out_degree"].iloc[0] == 2
    
    # X receives from A and C -> in_degree = 2
    assert feats["dest_in_degree"].iloc[0] == 2
    
    # A's degree ratio = 2 / (in_degree_of_A + 1) = 2 / (0 + 1) = 2.0
    assert feats["orig_degree_ratio"].iloc[0] == 2.0


def test_build_feature_matrix(feature_sample_df):
    X, y = build_feature_matrix(feature_sample_df)
    
    # Ensure dimensions
    assert len(X) == len(feature_sample_df)
    assert len(y) == len(feature_sample_df)
    
    # Check that y is isFraud
    assert (y.values == feature_sample_df[COL_IS_FRAUD].values).all()
    
    # Check presence of raw included columns
    assert "amount" in X.columns
    assert "oldbalanceOrg" in X.columns
