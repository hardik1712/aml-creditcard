"""
Exploratory Data Analysis for the PaySim AML project.

Each function performs one focused analysis and returns:
    - A results dict (for programmatic use / logging)
    - A saved matplotlib figure in outputs/figures/

Design principle: these are *pure functions* that take a DataFrame and produce
output. No global state, no side effects beyond saving figures. This makes them
testable and composable — the notebook or CLI script just calls them in sequence.

Why these specific analyses?
    - Class imbalance: ML models fail silently on imbalanced data; we need to
      know the ratio before choosing a modeling strategy.
    - Transaction type distribution: fraud in PaySim is concentrated in
      TRANSFER and CASH_OUT — understanding the baseline distribution lets us
      spot over/under-representation.
    - Amount distributions: structuring (smurfing) leaves a telltale spike
      just below reporting thresholds. Log-scale histograms reveal this.
    - Temporal patterns: real laundering has time-of-day and day-of-week
      patterns (e.g., off-hours transactions to avoid scrutiny).
    - Fan-out/Fan-in: the core topological signature of smurfing — one
      account fanning money out to many accounts (or the reverse).
    - Balance inconsistency: PaySim has known data-quality quirks where
      balances don't add up. Some of these correlate with fraud labels.
"""

import logging
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for script use

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import numpy as np
import pandas as pd

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
    ALL_TX_TYPES,
    STRUCTURING_THRESHOLD_USD,
    STRUCTURING_BAND_LOW,
    STRUCTURING_BAND_HIGH,
    MIN_FANOUT_COUNTERPARTIES,
    MIN_FANIN_COUNTERPARTIES,
    BALANCE_TOLERANCE,
    EDA_SAMPLE_SIZE,
    FIGURE_DPI,
    FIGURE_SIZE,
    FIGURES_DIR,
    TOP_N_ACCOUNTS,
    TXTYPE_CASH_OUT,
    TXTYPE_TRANSFER,
)

logger = logging.getLogger(__name__)

# Consistent styling
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)


def _ensure_output_dir(directory: Path = FIGURES_DIR) -> Path:
    """Create output directory if it doesn't exist."""
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _save_figure(fig: plt.Figure, filename: str, directory: Path = FIGURES_DIR) -> Path:
    """Save a matplotlib figure and close it to free memory."""
    outdir = _ensure_output_dir(directory)
    filepath = outdir / filename
    fig.savefig(filepath, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("Saved figure: %s", filepath)
    return filepath


# ============================================================================
# 1. CLASS IMBALANCE
# ============================================================================

def class_imbalance_report(df: pd.DataFrame) -> dict:
    """Analyze the class distribution of isFraud and isFlaggedFraud.

    Why this matters for AML:
        In PaySim, only ~0.13% of transactions are labeled as fraud. This
        extreme imbalance means:
        - A model that predicts "not fraud" 100% of the time gets 99.87% accuracy
        - We MUST use precision/recall/F1 and PR-AUC, not accuracy
        - We'll need resampling (SMOTE) or class weights in our models

    Returns
    -------
    dict with keys:
        'fraud_counts', 'fraud_rate', 'flagged_counts', 'flagged_rate',
        'imbalance_ratio' (non-fraud : fraud)
    """
    # isFraud distribution
    fraud_counts = df[COL_IS_FRAUD].value_counts().to_dict()
    n_fraud = fraud_counts.get(1, 0)
    n_legit = fraud_counts.get(0, 0)
    fraud_rate = n_fraud / len(df) if len(df) > 0 else 0
    imbalance_ratio = n_legit / n_fraud if n_fraud > 0 else float("inf")

    # isFlaggedFraud distribution
    flagged_counts = df[COL_IS_FLAGGED].value_counts().to_dict()
    n_flagged = flagged_counts.get(1, 0)
    flagged_rate = n_flagged / len(df) if len(df) > 0 else 0

    # --- Plot ---
    fig, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE)

    # Left: isFraud
    labels_fraud = ["Legitimate", "Fraud"]
    values_fraud = [n_legit, n_fraud]
    colors_fraud = ["#2ecc71", "#e74c3c"]
    bars1 = axes[0].bar(labels_fraud, values_fraud, color=colors_fraud, edgecolor="black", linewidth=0.5)
    axes[0].set_title("isFraud Distribution", fontsize=14, fontweight="bold")
    axes[0].set_ylabel("Transaction Count")
    axes[0].set_yscale("log")
    # Annotate bars with counts
    for bar, val in zip(bars1, values_fraud):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.1,
            f"{val:,}", ha="center", va="bottom", fontsize=11, fontweight="bold",
        )

    # Right: isFlaggedFraud
    n_not_flagged = len(df) - n_flagged
    labels_flagged = ["Not Flagged", "Flagged"]
    values_flagged = [n_not_flagged, n_flagged]
    colors_flagged = ["#3498db", "#e67e22"]
    bars2 = axes[1].bar(labels_flagged, values_flagged, color=colors_flagged, edgecolor="black", linewidth=0.5)
    axes[1].set_title("isFlaggedFraud Distribution", fontsize=14, fontweight="bold")
    axes[1].set_ylabel("Transaction Count")
    axes[1].set_yscale("log")
    for bar, val in zip(bars2, values_flagged):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.1,
            f"{val:,}", ha="center", va="bottom", fontsize=11, fontweight="bold",
        )

    fig.suptitle(
        f"Class Imbalance: {fraud_rate:.4%} fraud rate | "
        f"Ratio {imbalance_ratio:.0f}:1 (legit:fraud)",
        fontsize=13, y=1.02,
    )
    fig.tight_layout()
    _save_figure(fig, "01_class_imbalance.png")

    results = {
        "fraud_counts": fraud_counts,
        "fraud_rate": fraud_rate,
        "flagged_counts": flagged_counts,
        "flagged_rate": flagged_rate,
        "imbalance_ratio": imbalance_ratio,
        "n_fraud": n_fraud,
        "n_flagged": n_flagged,
    }

    logger.info(
        "Class imbalance: %.4f%% fraud rate, %.0f:1 ratio, %d flagged out of %d",
        fraud_rate * 100, imbalance_ratio, n_flagged, len(df),
    )

    return results


# ============================================================================
# 2. TRANSACTION TYPE DISTRIBUTION
# ============================================================================

def transaction_type_distribution(df: pd.DataFrame) -> dict:
    """Analyze transaction counts and total volume by type.

    Why this matters for AML:
        Fraud in PaySim occurs ONLY in TRANSFER and CASH_OUT types. Knowing the
        volume breakdown helps us understand what fraction of the data is even
        eligible to be fraudulent, and where to focus feature engineering.
    """
    type_counts = df[COL_TYPE].value_counts().to_dict()
    type_volume = df.groupby(COL_TYPE, observed=True)[COL_AMOUNT].sum().to_dict()

    # Fraud breakdown by type
    fraud_by_type = (
        df[df[COL_IS_FRAUD] == 1][COL_TYPE]
        .value_counts()
        .reindex(ALL_TX_TYPES, fill_value=0)
        .to_dict()
    )

    # --- Plot ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Panel 1: Transaction counts by type
    types = list(type_counts.keys())
    counts = list(type_counts.values())
    palette = sns.color_palette("viridis", len(types))
    axes[0].barh(types, counts, color=palette, edgecolor="black", linewidth=0.5)
    axes[0].set_xlabel("Count")
    axes[0].set_title("Transaction Count by Type", fontweight="bold")
    axes[0].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    # Panel 2: Total volume by type
    volumes = [type_volume.get(t, 0) for t in types]
    axes[1].barh(types, volumes, color=palette, edgecolor="black", linewidth=0.5)
    axes[1].set_xlabel("Total Amount ($)")
    axes[1].set_title("Total Volume by Type", fontweight="bold")
    axes[1].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    # Panel 3: Fraud count by type
    fraud_types = list(fraud_by_type.keys())
    fraud_vals = list(fraud_by_type.values())
    fraud_colors = ["#e74c3c" if v > 0 else "#cccccc" for v in fraud_vals]
    axes[2].barh(fraud_types, fraud_vals, color=fraud_colors, edgecolor="black", linewidth=0.5)
    axes[2].set_xlabel("Fraud Count")
    axes[2].set_title("Fraudulent Transactions by Type", fontweight="bold")
    axes[2].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    fig.suptitle("Transaction Type Analysis", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    _save_figure(fig, "02_transaction_types.png")

    return {
        "type_counts": type_counts,
        "type_volume": type_volume,
        "fraud_by_type": fraud_by_type,
    }


# ============================================================================
# 3. AMOUNT DISTRIBUTIONS
# ============================================================================

def amount_distributions(df: pd.DataFrame, sample_size: int = EDA_SAMPLE_SIZE) -> dict:
    """Plot amount distributions per transaction type (log scale).

    Why log scale?
        Transaction amounts span from <$1 to >$10M. Linear histograms
        are dominated by the long tail and hide the structure in the
        low-amount region — exactly where structuring (smurfing) signals
        live (clustering just under $10K).

    Also highlights the "structuring band" ($8K–$10K) where smurfers
    tend to cluster their transactions.
    """
    # Sample for plotting performance, compute stats on full data
    stats_by_type = {}
    for tx_type in ALL_TX_TYPES:
        subset = df[df[COL_TYPE] == tx_type][COL_AMOUNT]
        stats_by_type[tx_type] = {
            "count": len(subset),
            "mean": float(subset.mean()) if len(subset) > 0 else 0,
            "median": float(subset.median()) if len(subset) > 0 else 0,
            "std": float(subset.std()) if len(subset) > 0 else 0,
            "min": float(subset.min()) if len(subset) > 0 else 0,
            "max": float(subset.max()) if len(subset) > 0 else 0,
            "pct_in_structuring_band": float(
                ((subset >= STRUCTURING_BAND_LOW) & (subset < STRUCTURING_BAND_HIGH)).mean()
            ) if len(subset) > 0 else 0,
        }

    # --- Plot ---
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for i, tx_type in enumerate(ALL_TX_TYPES):
        ax = axes[i]
        subset = df[df[COL_TYPE] == tx_type][COL_AMOUNT]

        # Sample if too large
        if len(subset) > sample_size:
            plot_data = subset.sample(sample_size, random_state=42)
        else:
            plot_data = subset

        # Only plot positive amounts (log scale requires > 0)
        plot_data = plot_data[plot_data > 0]

        if len(plot_data) > 0:
            ax.hist(
                np.log10(plot_data), bins=80, color=sns.color_palette("viridis", 5)[i],
                edgecolor="white", linewidth=0.3, alpha=0.85,
            )
            # Mark the structuring threshold
            if STRUCTURING_THRESHOLD_USD > 0:
                ax.axvline(
                    np.log10(STRUCTURING_THRESHOLD_USD), color="red", linestyle="--",
                    linewidth=2, label=f"${STRUCTURING_THRESHOLD_USD:,.0f} threshold",
                )
            ax.legend(fontsize=9)

        ax.set_title(f"{tx_type} (n={stats_by_type[tx_type]['count']:,})", fontweight="bold")
        ax.set_xlabel("log₁₀(Amount)")
        ax.set_ylabel("Frequency")

    # Hide unused subplot
    axes[5].set_visible(False)

    fig.suptitle(
        "Amount Distributions by Transaction Type (log scale)\n"
        "Red dashed line = $10K BSA reporting threshold",
        fontsize=14, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    _save_figure(fig, "03_amount_distributions.png")

    return {"stats_by_type": stats_by_type}


# ============================================================================
# 4. TEMPORAL PATTERNS
# ============================================================================

def temporal_patterns(df: pd.DataFrame) -> dict:
    """Analyze transaction volume and fraud rate over time (by step).

    PaySim's 'step' column represents 1-hour intervals over 30 simulated days
    (steps 1–744). We look for:
        - Overall volume patterns (daily cycles)
        - Whether fraud is concentrated at certain times
        - Velocity spikes (sudden bursts of activity)
    """
    # Volume per step
    step_volume = df.groupby(COL_STEP).agg(
        tx_count=(COL_AMOUNT, "count"),
        total_amount=(COL_AMOUNT, "sum"),
        fraud_count=(COL_IS_FRAUD, "sum"),
    ).reset_index()

    step_volume["fraud_rate"] = (
        step_volume["fraud_count"] / step_volume["tx_count"]
    ).fillna(0)

    # Derive "hour of day" and "day" from step (step 1 = hour 1)
    step_volume["hour_of_day"] = step_volume[COL_STEP] % 24
    step_volume["day"] = step_volume[COL_STEP] // 24

    # Aggregate by hour-of-day
    hourly_avg = step_volume.groupby("hour_of_day").agg(
        avg_tx_count=("tx_count", "mean"),
        avg_fraud_rate=("fraud_rate", "mean"),
    ).reset_index()

    # --- Plot ---
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    # Panel 1: Transaction count over time
    axes[0, 0].plot(step_volume[COL_STEP], step_volume["tx_count"],
                     color="#3498db", alpha=0.7, linewidth=0.5)
    axes[0, 0].set_title("Transaction Volume Over Time", fontweight="bold")
    axes[0, 0].set_xlabel("Step (hour)")
    axes[0, 0].set_ylabel("Transaction Count")

    # Panel 2: Fraud count over time
    axes[0, 1].plot(step_volume[COL_STEP], step_volume["fraud_count"],
                     color="#e74c3c", alpha=0.8, linewidth=0.8)
    axes[0, 1].set_title("Fraud Transactions Over Time", fontweight="bold")
    axes[0, 1].set_xlabel("Step (hour)")
    axes[0, 1].set_ylabel("Fraud Count")

    # Panel 3: Average volume by hour of day
    axes[1, 0].bar(hourly_avg["hour_of_day"], hourly_avg["avg_tx_count"],
                    color="#2ecc71", edgecolor="black", linewidth=0.5)
    axes[1, 0].set_title("Avg Transaction Count by Hour of Day", fontweight="bold")
    axes[1, 0].set_xlabel("Hour of Day")
    axes[1, 0].set_ylabel("Avg Count")

    # Panel 4: Fraud rate by hour of day
    axes[1, 1].bar(hourly_avg["hour_of_day"], hourly_avg["avg_fraud_rate"] * 100,
                    color="#e67e22", edgecolor="black", linewidth=0.5)
    axes[1, 1].set_title("Avg Fraud Rate by Hour of Day", fontweight="bold")
    axes[1, 1].set_xlabel("Hour of Day")
    axes[1, 1].set_ylabel("Fraud Rate (%)")

    fig.suptitle("Temporal Patterns in PaySim Data", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    _save_figure(fig, "04_temporal_patterns.png")

    return {
        "total_steps": int(step_volume[COL_STEP].max()),
        "peak_step": int(step_volume.loc[step_volume["tx_count"].idxmax(), COL_STEP]),
        "peak_count": int(step_volume["tx_count"].max()),
        "avg_fraud_rate_per_step": float(step_volume["fraud_rate"].mean()),
    }


# ============================================================================
# 5. FAN-OUT ANALYSIS (Smurfing: sender side)
# ============================================================================

def fan_out_analysis(
    df: pd.DataFrame,
    top_n: int = TOP_N_ACCOUNTS,
    min_counterparties: int = MIN_FANOUT_COUNTERPARTIES,
) -> dict:
    """Identify accounts with high fan-out: many small transfers to distinct recipients.

    What is fan-out (smurfing)?
        A money launderer wants to move $100K but the reporting threshold is $10K.
        Instead of one $100K transfer (which triggers a CTR), they split it into
        12 transfers of ~$8,300 each to 12 different recipients. This is
        "structuring" or "smurfing."

    Detection logic:
        1. Filter to TRANSFER type with amount < structuring threshold
        2. For each sender: count distinct recipients and total amount
        3. Accounts with many distinct recipients for small transfers are suspicious

    Parameters
    ----------
    top_n : int
        Number of top fan-out accounts to return/plot.
    min_counterparties : int
        Minimum distinct recipients to flag.
    """
    # Filter to small transfers (potential structuring)
    small_transfers = df[
        (df[COL_TYPE] == TXTYPE_TRANSFER) &
        (df[COL_AMOUNT] < STRUCTURING_THRESHOLD_USD) &
        (df[COL_AMOUNT] > 0)
    ]

    # Aggregate by sender
    fan_out = (
        small_transfers.groupby(COL_NAME_ORIG)
        .agg(
            n_recipients=(COL_NAME_DEST, "nunique"),
            n_transactions=(COL_AMOUNT, "count"),
            total_amount=(COL_AMOUNT, "sum"),
            avg_amount=(COL_AMOUNT, "mean"),
            min_amount=(COL_AMOUNT, "min"),
            max_amount=(COL_AMOUNT, "max"),
        )
        .reset_index()
        .sort_values("n_recipients", ascending=False)
    )

    # Flag suspicious accounts
    suspicious = fan_out[fan_out["n_recipients"] >= min_counterparties].copy()

    # Check how many of these accounts are already labeled as fraud
    fraud_senders = set(df[df[COL_IS_FRAUD] == 1][COL_NAME_ORIG].unique())
    suspicious["is_known_fraud"] = suspicious[COL_NAME_ORIG].isin(fraud_senders)

    # --- Plot ---
    top = suspicious.head(top_n)

    if len(top) > 0:
        fig, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE)

        # Left: distinct recipients
        colors = ["#e74c3c" if f else "#3498db" for f in top["is_known_fraud"]]
        axes[0].barh(
            range(len(top)), top["n_recipients"],
            color=colors, edgecolor="black", linewidth=0.5,
        )
        axes[0].set_yticks(range(len(top)))
        axes[0].set_yticklabels(top[COL_NAME_ORIG], fontsize=8)
        axes[0].set_xlabel("Distinct Recipients")
        axes[0].set_title("Top Fan-Out: Distinct Recipients\n(Red = known fraud sender)", fontweight="bold")
        axes[0].invert_yaxis()

        # Right: total amount sent
        axes[1].barh(
            range(len(top)), top["total_amount"],
            color=colors, edgecolor="black", linewidth=0.5,
        )
        axes[1].set_yticks(range(len(top)))
        axes[1].set_yticklabels(top[COL_NAME_ORIG], fontsize=8)
        axes[1].set_xlabel("Total Amount ($)")
        axes[1].set_title("Top Fan-Out: Total Sent (sub-threshold)\n(Red = known fraud sender)", fontweight="bold")
        axes[1].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        axes[1].invert_yaxis()

        fig.suptitle(
            f"Fan-Out Analysis — Potential Smurfing Senders\n"
            f"({len(suspicious):,} accounts with ≥{min_counterparties} distinct recipients for <${STRUCTURING_THRESHOLD_USD:,} transfers)",
            fontsize=13, fontweight="bold", y=1.04,
        )
        fig.tight_layout()
        _save_figure(fig, "05_fan_out_analysis.png")
    else:
        logger.warning("No accounts met the fan-out threshold of %d recipients.", min_counterparties)

    return {
        "n_suspicious_senders": len(suspicious),
        "n_known_fraud_in_suspicious": int(suspicious["is_known_fraud"].sum()) if len(suspicious) > 0 else 0,
        "top_accounts": top.to_dict("records") if len(top) > 0 else [],
        "total_small_transfers": len(small_transfers),
    }


# ============================================================================
# 6. FAN-IN ANALYSIS (Smurfing: receiver / collection side)
# ============================================================================

def fan_in_analysis(
    df: pd.DataFrame,
    top_n: int = TOP_N_ACCOUNTS,
    min_counterparties: int = MIN_FANIN_COUNTERPARTIES,
) -> dict:
    """Identify accounts with high fan-in: many small transfers received, then cashed out.

    What is fan-in (collection)?
        After smurfing (fan-out), the small amounts need to be re-aggregated.
        A "collection" account receives many small transfers from distinct senders,
        then does a large CASH_OUT to extract the reassembled funds.

    Detection logic:
        1. Find accounts that receive many small transfers from distinct senders
        2. Cross-reference with CASH_OUT activity from the same accounts
        3. Accounts that both receive many small inflows AND have large outflows
           are strong candidates for money collection points
    """
    # Small incoming transfers
    small_incoming = df[
        (df[COL_TYPE] == TXTYPE_TRANSFER) &
        (df[COL_AMOUNT] < STRUCTURING_THRESHOLD_USD) &
        (df[COL_AMOUNT] > 0)
    ]

    # Fan-in aggregation
    fan_in = (
        small_incoming.groupby(COL_NAME_DEST)
        .agg(
            n_senders=(COL_NAME_ORIG, "nunique"),
            n_transactions=(COL_AMOUNT, "count"),
            total_received=(COL_AMOUNT, "sum"),
            avg_amount=(COL_AMOUNT, "mean"),
        )
        .reset_index()
        .sort_values("n_senders", ascending=False)
    )

    # Suspicious = many distinct senders
    suspicious = fan_in[fan_in["n_senders"] >= min_counterparties].copy()

    # Cross-reference: do these accounts also cash out?
    # Look for CASH_OUT transactions where these accounts are the originator
    cashout_accounts = set(
        df[df[COL_TYPE] == TXTYPE_CASH_OUT][COL_NAME_ORIG].unique()
    )
    suspicious["has_cashout"] = suspicious[COL_NAME_DEST].isin(cashout_accounts)

    # Get total cash-out amount for suspicious accounts
    cashout_totals = (
        df[(df[COL_TYPE] == TXTYPE_CASH_OUT) & (df[COL_NAME_ORIG].isin(suspicious[COL_NAME_DEST]))]
        .groupby(COL_NAME_ORIG)[COL_AMOUNT]
        .sum()
        .to_dict()
    )
    suspicious["cashout_total"] = suspicious[COL_NAME_DEST].map(cashout_totals).fillna(0)

    # --- Plot ---
    top = suspicious.head(top_n)

    if len(top) > 0:
        fig, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE)

        # Left: distinct senders
        colors = ["#e74c3c" if co else "#3498db" for co in top["has_cashout"]]
        axes[0].barh(
            range(len(top)), top["n_senders"],
            color=colors, edgecolor="black", linewidth=0.5,
        )
        axes[0].set_yticks(range(len(top)))
        axes[0].set_yticklabels(top[COL_NAME_DEST], fontsize=8)
        axes[0].set_xlabel("Distinct Senders")
        axes[0].set_title("Top Fan-In: Distinct Senders\n(Red = also does CASH_OUT)", fontweight="bold")
        axes[0].invert_yaxis()

        # Right: cash-out total
        axes[1].barh(
            range(len(top)), top["cashout_total"],
            color=colors, edgecolor="black", linewidth=0.5,
        )
        axes[1].set_yticks(range(len(top)))
        axes[1].set_yticklabels(top[COL_NAME_DEST], fontsize=8)
        axes[1].set_xlabel("Total Cash-Out Amount ($)")
        axes[1].set_title("Top Fan-In: Subsequent Cash-Out\n(Red = account has CASH_OUT)", fontweight="bold")
        axes[1].xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        axes[1].invert_yaxis()

        fig.suptitle(
            f"Fan-In Analysis — Potential Collection Points\n"
            f"({len(suspicious):,} accounts with ≥{min_counterparties} distinct senders | "
            f"{suspicious['has_cashout'].sum()} also have CASH_OUT)",
            fontsize=13, fontweight="bold", y=1.04,
        )
        fig.tight_layout()
        _save_figure(fig, "06_fan_in_analysis.png")
    else:
        logger.warning("No accounts met the fan-in threshold of %d senders.", min_counterparties)

    return {
        "n_suspicious_collectors": len(suspicious),
        "n_with_cashout": int(suspicious["has_cashout"].sum()) if len(suspicious) > 0 else 0,
        "top_accounts": top.to_dict("records") if len(top) > 0 else [],
    }


# ============================================================================
# 7. BALANCE INCONSISTENCY CHECK
# ============================================================================

def balance_inconsistency_check(df: pd.DataFrame) -> dict:
    """Flag transactions where balances don't add up.

    PaySim has a known data-quality feature: for many transactions,
        oldbalanceOrg - amount ≠ newbalanceOrg

    This happens because:
        - The simulation doesn't always model all balance effects
        - Some transactions may represent "phantom" credits/debits
        - The inconsistency itself can be a fraud signal (a real AML system
          would flag unexplained balance changes)

    We compute the discrepancy for both originator and destination, then
    analyze the correlation with the fraud label.
    """
    # Compute expected new balance (what it *should* be if only this tx affected it)
    # For the originator: new_balance_expected = old_balance - amount (for outgoing)
    # This is a simplification — the real relationship depends on transaction type
    df_check = df[[COL_TYPE, COL_AMOUNT, COL_OLD_BAL_ORIG, COL_NEW_BAL_ORIG,
                    COL_OLD_BAL_DEST, COL_NEW_BAL_DEST, COL_IS_FRAUD]].copy()

    # Originator discrepancy
    df_check["orig_expected"] = df_check[COL_OLD_BAL_ORIG] - df_check[COL_AMOUNT]
    df_check["orig_discrepancy"] = abs(df_check[COL_NEW_BAL_ORIG] - df_check["orig_expected"])
    df_check["orig_has_discrepancy"] = df_check["orig_discrepancy"] > BALANCE_TOLERANCE

    # Destination discrepancy
    df_check["dest_expected"] = df_check[COL_OLD_BAL_DEST] + df_check[COL_AMOUNT]
    df_check["dest_discrepancy"] = abs(df_check[COL_NEW_BAL_DEST] - df_check["dest_expected"])
    df_check["dest_has_discrepancy"] = df_check["dest_discrepancy"] > BALANCE_TOLERANCE

    # Summary stats
    n_orig_disc = int(df_check["orig_has_discrepancy"].sum())
    n_dest_disc = int(df_check["dest_has_discrepancy"].sum())
    pct_orig = n_orig_disc / len(df_check) if len(df_check) > 0 else 0
    pct_dest = n_dest_disc / len(df_check) if len(df_check) > 0 else 0

    # Correlation with fraud
    # What fraction of fraudulent transactions have balance discrepancies?
    fraud_rows = df_check[df_check[COL_IS_FRAUD] == 1]
    legit_rows = df_check[df_check[COL_IS_FRAUD] == 0]

    fraud_orig_disc_rate = float(fraud_rows["orig_has_discrepancy"].mean()) if len(fraud_rows) > 0 else 0
    legit_orig_disc_rate = float(legit_rows["orig_has_discrepancy"].mean()) if len(legit_rows) > 0 else 0
    fraud_dest_disc_rate = float(fraud_rows["dest_has_discrepancy"].mean()) if len(fraud_rows) > 0 else 0
    legit_dest_disc_rate = float(legit_rows["dest_has_discrepancy"].mean()) if len(legit_rows) > 0 else 0

    # Discrepancy by transaction type
    disc_by_type = (
        df_check.groupby(df[COL_TYPE], observed=True)
        .agg(
            orig_disc_rate=("orig_has_discrepancy", "mean"),
            dest_disc_rate=("dest_has_discrepancy", "mean"),
        )
        .to_dict("index")
    )

    # --- Plot ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Panel 1: Discrepancy rates (fraud vs legit)
    categories = ["Orig (Fraud)", "Orig (Legit)", "Dest (Fraud)", "Dest (Legit)"]
    rates = [fraud_orig_disc_rate, legit_orig_disc_rate, fraud_dest_disc_rate, legit_dest_disc_rate]
    colors = ["#e74c3c", "#2ecc71", "#e74c3c", "#2ecc71"]
    axes[0].bar(categories, [r * 100 for r in rates], color=colors, edgecolor="black", linewidth=0.5)
    axes[0].set_ylabel("Discrepancy Rate (%)")
    axes[0].set_title("Balance Discrepancy Rate:\nFraud vs Legitimate", fontweight="bold")
    axes[0].tick_params(axis="x", rotation=30)

    # Panel 2: Discrepancy amount distribution (log scale, sampled)
    orig_disc_amounts = df_check.loc[df_check["orig_has_discrepancy"], "orig_discrepancy"]
    if len(orig_disc_amounts) > EDA_SAMPLE_SIZE:
        orig_disc_amounts = orig_disc_amounts.sample(EDA_SAMPLE_SIZE, random_state=42)
    orig_disc_positive = orig_disc_amounts[orig_disc_amounts > 0]
    if len(orig_disc_positive) > 0:
        axes[1].hist(
            np.log10(orig_disc_positive), bins=80, color="#9b59b6",
            edgecolor="white", linewidth=0.3, alpha=0.85,
        )
    axes[1].set_xlabel("log₁₀(Discrepancy Amount)")
    axes[1].set_ylabel("Frequency")
    axes[1].set_title("Originator Balance\nDiscrepancy Distribution", fontweight="bold")

    # Panel 3: Discrepancy rate by transaction type
    types_ordered = sorted(disc_by_type.keys())
    orig_rates = [disc_by_type[t]["orig_disc_rate"] * 100 for t in types_ordered]
    dest_rates = [disc_by_type[t]["dest_disc_rate"] * 100 for t in types_ordered]
    x = np.arange(len(types_ordered))
    width = 0.35
    axes[2].bar(x - width / 2, orig_rates, width, label="Originator", color="#3498db", edgecolor="black", linewidth=0.5)
    axes[2].bar(x + width / 2, dest_rates, width, label="Destination", color="#e67e22", edgecolor="black", linewidth=0.5)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(types_ordered, rotation=30)
    axes[2].set_ylabel("Discrepancy Rate (%)")
    axes[2].set_title("Discrepancy Rate by\nTransaction Type", fontweight="bold")
    axes[2].legend()

    fig.suptitle(
        f"Balance Inconsistency Analysis\n"
        f"Originator discrepancies: {pct_orig:.1%} | Destination: {pct_dest:.1%}",
        fontsize=14, fontweight="bold", y=1.04,
    )
    fig.tight_layout()
    _save_figure(fig, "07_balance_inconsistency.png")

    return {
        "n_orig_discrepancies": n_orig_disc,
        "pct_orig_discrepancies": pct_orig,
        "n_dest_discrepancies": n_dest_disc,
        "pct_dest_discrepancies": pct_dest,
        "fraud_orig_disc_rate": fraud_orig_disc_rate,
        "legit_orig_disc_rate": legit_orig_disc_rate,
        "fraud_dest_disc_rate": fraud_dest_disc_rate,
        "legit_dest_disc_rate": legit_dest_disc_rate,
        "disc_by_type": disc_by_type,
    }


# ============================================================================
# MASTER EDA RUNNER
# ============================================================================

def run_all_eda(df: pd.DataFrame) -> dict:
    """Run all EDA analyses and return combined results.

    This is the main entry point called by scripts/run_eda.py.
    Each sub-analysis is independent, so a failure in one won't block the others.
    """
    results = {}

    analyses = [
        ("class_imbalance", class_imbalance_report),
        ("transaction_types", transaction_type_distribution),
        ("amount_distributions", amount_distributions),
        ("temporal_patterns", temporal_patterns),
        ("fan_out", fan_out_analysis),
        ("fan_in", fan_in_analysis),
        ("balance_inconsistency", balance_inconsistency_check),
    ]

    for name, func in analyses:
        logger.info("=" * 60)
        logger.info("Running EDA: %s", name)
        logger.info("=" * 60)
        try:
            results[name] = func(df)
            logger.info("[OK] %s complete", name)
        except Exception as e:
            logger.error("[FAIL] %s failed: %s", name, e, exc_info=True)
            results[name] = {"error": str(e)}

    return results
