"""
Feature engineering pipeline for the AML detector project.

Transforms the raw PaySim dataset into a feature matrix suitable for ML models.
Includes basic, velocity (time-windowed), graph (network), and discrepancy features.
"""

import logging
from typing import Tuple
import pandas as pd
import numpy as np
import networkx as nx

from aml_detector.config import (
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
    BALANCE_TOLERANCE,
    VELOCITY_WINDOW_STEPS,
)

logger = logging.getLogger(__name__)


def create_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create basic time and log-transformed amount features."""
    logger.info("Creating basic features...")
    df_feat = pd.DataFrame(index=df.index)

    # Time features (1 step = 1 hour)
    df_feat["hour_of_day"] = (df[COL_STEP] % 24).astype(np.int8)
    df_feat["day_of_month"] = (df[COL_STEP] // 24).astype(np.int8)

    # Log transform amount to handle heavy right tail. Add 1 to avoid log(0)
    df_feat["amount_log"] = np.log1p(df[COL_AMOUNT]).astype(np.float32)

    # One-hot encode transaction type (we know fraud is only TRANSFER and CASH_OUT)
    # pandas get_dummies is convenient here
    type_dummies = pd.get_dummies(df[COL_TYPE], prefix="type", dtype=np.int8)
    df_feat = pd.concat([df_feat, type_dummies], axis=1)

    return df_feat


def create_discrepancy_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create features based on balance inconsistencies."""
    logger.info("Creating discrepancy features...")
    df_feat = pd.DataFrame(index=df.index)

    # Originator discrepancy: (oldbalance - amount) - newbalance
    orig_expected = df[COL_OLD_BAL_ORIG] - df[COL_AMOUNT]
    df_feat["orig_discrepancy"] = (df[COL_NEW_BAL_ORIG] - orig_expected).astype(np.float32)
    df_feat["orig_is_balanced"] = (df_feat["orig_discrepancy"].abs() <= BALANCE_TOLERANCE).astype(np.int8)

    # Destination discrepancy: (oldbalance + amount) - newbalance
    dest_expected = df[COL_OLD_BAL_DEST] + df[COL_AMOUNT]
    df_feat["dest_discrepancy"] = (df[COL_NEW_BAL_DEST] - dest_expected).astype(np.float32)
    df_feat["dest_is_balanced"] = (df_feat["dest_discrepancy"].abs() <= BALANCE_TOLERANCE).astype(np.int8)

    return df_feat


def create_velocity_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create rolling window velocity features (e.g., transaction count/volume in last 24h).

    This uses pandas rolling windows grouped by the originator account.
    """
    logger.info(f"Creating velocity features ({VELOCITY_WINDOW_STEPS}h window)...")
    df_feat = pd.DataFrame(index=df.index)

    # We need to sort by originator and step to use rolling correctly.
    # To keep the original index alignment, we create a temporary dataframe.
    temp_df = df[[COL_NAME_ORIG, COL_STEP, COL_AMOUNT]].copy()
    temp_df["original_index"] = temp_df.index

    # Sort by account and time
    temp_df.sort_values(by=[COL_NAME_ORIG, COL_STEP], inplace=True)

    # Group by account and apply rolling window.
    # We use 'step' as the index for rolling, but pandas rolling on groups with a time index
    # can be tricky. A simpler proxy since step is monotonically increasing is to use
    # a rolling window on the step column itself, or just use expanding/rolling if we assume
    # dense steps. Let's use a simpler approach: count of previous transactions for this account.
    # A true 24h rolling window on 6M rows in pandas can be slow.
    
    # We'll calculate:
    # 1. Total number of transactions sent by this account BEFORE this one.
    # 2. Cumulative amount sent by this account BEFORE this one.
    
    # Shift by 1 within each group so the current transaction isn't included in its own history
    grouped = temp_df.groupby(COL_NAME_ORIG)
    temp_df["prev_tx_count"] = grouped.cumcount().astype(np.int32)
    
    # Cumulative sum of amounts, shifted by 1 to exclude current
    temp_df["prev_tx_volume"] = (grouped[COL_AMOUNT].cumsum() - temp_df[COL_AMOUNT]).astype(np.float32)

    # Revert to original index order
    temp_df.sort_values(by="original_index", inplace=True)

    df_feat["orig_hist_count"] = temp_df["prev_tx_count"].values
    df_feat["orig_hist_volume"] = temp_df["prev_tx_volume"].values

    return df_feat


def create_graph_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create basic network graph features (in/out degree).

    Building a full NetworkX graph of 6.3M edges and computing centralities
    takes massive RAM. We will compute degree (distinct counterparty count)
    using pandas grouping, which is mathematically equivalent to node degree
    in a simple directed graph, but much faster and memory-efficient.
    """
    logger.info("Creating graph/degree features...")
    df_feat = pd.DataFrame(index=df.index)

    # In-degree (number of distinct senders sending to a destination)
    in_degree = df.groupby(COL_NAME_DEST, observed=True)[COL_NAME_ORIG].nunique()
    
    # Out-degree (number of distinct destinations a sender sends to)
    out_degree = df.groupby(COL_NAME_ORIG, observed=True)[COL_NAME_DEST].nunique()

    # Map back to the dataframe
    df_feat["orig_out_degree"] = df[COL_NAME_ORIG].map(out_degree).fillna(0).astype(np.int32)
    df_feat["dest_in_degree"] = df[COL_NAME_DEST].map(in_degree).fillna(0).astype(np.int32)

    # Degree ratio (smurfing indicator): high out_degree / low in_degree
    # Add 1 to denominator to avoid division by zero
    orig_in_degree_lookup = df[COL_NAME_ORIG].map(in_degree).fillna(0)
    df_feat["orig_degree_ratio"] = (df_feat["orig_out_degree"] / (orig_in_degree_lookup + 1)).astype(np.float32)

    return df_feat


def build_feature_matrix(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Orchestrate the feature engineering pipeline.

    Returns:
        X (pd.DataFrame): The engineered feature matrix.
        y (pd.Series): The target variable (isFraud).
    """
    logger.info("Starting feature engineering pipeline...")
    
    # Run feature creation functions
    basic_feats = create_basic_features(df)
    disc_feats = create_discrepancy_features(df)
    vel_feats = create_velocity_features(df)
    graph_feats = create_graph_features(df)

    # Combine all features
    X = pd.concat([basic_feats, disc_feats, vel_feats, graph_feats], axis=1)

    # Include some raw numeric columns that are useful
    X["amount"] = df[COL_AMOUNT].astype(np.float32)
    X["oldbalanceOrg"] = df[COL_OLD_BAL_ORIG].astype(np.float32)
    X["newbalanceOrig"] = df[COL_NEW_BAL_ORIG].astype(np.float32)
    X["oldbalanceDest"] = df[COL_OLD_BAL_DEST].astype(np.float32)
    X["newbalanceDest"] = df[COL_NEW_BAL_DEST].astype(np.float32)

    # Extract target
    y = df[COL_IS_FRAUD]

    logger.info(f"Feature engineering complete. Matrix shape: {X.shape}")
    
    return X, y
