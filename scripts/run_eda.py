"""
CLI entry point for running the full EDA pipeline.

Usage:
    python scripts/run_eda.py
    python scripts/run_eda.py --nrows 100000   # Quick test with subset

This script:
    1. Loads the PaySim data (with memory optimization)
    2. Prints summary statistics
    3. Runs all 7 EDA analyses
    4. Saves figures to outputs/figures/
    5. Prints a summary report

All the heavy lifting is in src/aml_detector/eda.py — this script is just
the orchestrator. Keeping it thin means you can also call the individual
EDA functions from a notebook or test.
"""

import argparse
import logging
import sys
import json
from pathlib import Path
import numpy as np

# Add the src directory to the path so we can import aml_detector
# even if the package isn't installed via pip install -e .
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aml_detector.data_loader import load_paysim, get_summary_stats
from aml_detector.eda import run_all_eda
from aml_detector.config import FIGURES_DIR, OUTPUT_DIR

# Configure logging to both console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIR / "eda_log.txt", mode="w"),
    ],
)
logger = logging.getLogger("run_eda")


def main():
    parser = argparse.ArgumentParser(description="Run AML EDA pipeline on PaySim data")
    parser.add_argument(
        "--nrows", type=int, default=None,
        help="Load only the first N rows (for quick testing)",
    )
    args = parser.parse_args()

    # Ensure output directories exist
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # ---- Load Data ----
    logger.info("=" * 70)
    logger.info("PHASE 1: LOADING PAYSIM DATA")
    logger.info("=" * 70)

    df = load_paysim(nrows=args.nrows)

    # ---- Summary Stats ----
    stats = get_summary_stats(df)
    logger.info("Dataset summary:")
    logger.info("  Rows:      %s", f"{stats['n_rows']:,}")
    logger.info("  Columns:   %s", stats["n_cols"])
    logger.info("  Memory:    %.1f MB", stats["memory_mb"])
    logger.info("  Steps:     %d to %d", *stats["step_range"])
    logger.info("  Null counts: %s", stats["null_counts"])
    logger.info("  Transaction types:")
    for tx_type, count in stats["tx_types"].items():
        logger.info("    %-12s %s", tx_type, f"{count:,}")

    # ---- Run All EDA ----
    logger.info("")
    logger.info("=" * 70)
    logger.info("PHASE 1: RUNNING EDA ANALYSES")
    logger.info("=" * 70)

    results = run_all_eda(df)

    # ---- Print Summary Report ----
    logger.info("")
    logger.info("=" * 70)
    logger.info("EDA SUMMARY REPORT")
    logger.info("=" * 70)

    # Class imbalance
    ci = results.get("class_imbalance", {})
    if "error" not in ci:
        logger.info("")
        logger.info("1. CLASS IMBALANCE")
        logger.info("   Fraud rate:      %.4f%%", ci.get("fraud_rate", 0) * 100)
        logger.info("   Imbalance ratio: %.0f:1 (legit:fraud)", ci.get("imbalance_ratio", 0))
        logger.info("   Flagged by sim:  %s", f"{ci.get('n_flagged', 0):,}")
        logger.info("   -> The built-in flag catches almost nothing. We need better signals.")

    # Transaction types
    tt = results.get("transaction_types", {})
    if "error" not in tt:
        logger.info("")
        logger.info("2. TRANSACTION TYPES")
        fraud_types = tt.get("fraud_by_type", {})
        for tx_type, count in fraud_types.items():
            if count > 0:
                logger.info("   Fraud in %-12s: %s", tx_type, f"{count:,}")

    # Amount distributions
    ad = results.get("amount_distributions", {})
    if "error" not in ad:
        logger.info("")
        logger.info("3. AMOUNT DISTRIBUTIONS")
        for tx_type, s in ad.get("stats_by_type", {}).items():
            band_pct = s.get("pct_in_structuring_band", 0)
            if band_pct > 0:
                logger.info("   %-12s: %.2f%% of transactions in $8K-$10K structuring band",
                            tx_type, band_pct * 100)

    # Fan-out
    fo = results.get("fan_out", {})
    if "error" not in fo:
        logger.info("")
        logger.info("4. FAN-OUT (SMURFING SENDERS)")
        logger.info("   Suspicious accounts: %s", f"{fo.get('n_suspicious_senders', 0):,}")
        logger.info("   Of which known fraud: %s", fo.get("n_known_fraud_in_suspicious", 0))

    # Fan-in
    fi = results.get("fan_in", {})
    if "error" not in fi:
        logger.info("")
        logger.info("5. FAN-IN (COLLECTION POINTS)")
        logger.info("   Suspicious accounts: %s", f"{fi.get('n_suspicious_collectors', 0):,}")
        logger.info("   With cash-out:       %s", fi.get("n_with_cashout", 0))

    # Balance inconsistency
    bi = results.get("balance_inconsistency", {})
    if "error" not in bi:
        logger.info("")
        logger.info("6. BALANCE INCONSISTENCIES")
        logger.info("   Originator discrepancies: %.1f%%", bi.get("pct_orig_discrepancies", 0) * 100)
        logger.info("   Destination discrepancies: %.1f%%", bi.get("pct_dest_discrepancies", 0) * 100)
        logger.info("   Fraud orig disc rate:      %.1f%%", bi.get("fraud_orig_disc_rate", 0) * 100)
        logger.info("   Legit orig disc rate:       %.1f%%", bi.get("legit_orig_disc_rate", 0) * 100)
        logger.info("   -> Strong signal if fraud has much higher discrepancy rate.")

    # Save results as JSON for later use
    results_file = OUTPUT_DIR / "eda_results.json"

    # Make results JSON-serializable (convert numpy types)
    def make_serializable(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(i) for i in obj]
        return obj

    with open(results_file, "w") as f:
        json.dump(make_serializable(results), f, indent=2, default=str)
    logger.info("")
    logger.info("Results saved to: %s", results_file)

    logger.info("")
    logger.info("=" * 70)
    logger.info("Figures saved to: %s", FIGURES_DIR)
    logger.info("EDA complete! Review the figures and report above.")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
