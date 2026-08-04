"""
CLI entry point for running graph visualizations.

Extracts examples of money laundering subgraphs and plots them
interactively and statically.
"""

import logging
import sys
from pathlib import Path
import random

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aml_detector.data_loader import load_paysim
from aml_detector.graph import extract_fraud_subgraph, plot_interactive_network, plot_static_network
from aml_detector.config import FIGURES_DIR, COL_IS_FRAUD, COL_NAME_ORIG, COL_TYPE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("run_graph_viz")


def main():
    logger.info("=" * 70)
    logger.info("PHASE 4: LOADING DATA FOR GRAPH VISUALIZATION")
    logger.info("=" * 70)
    
    # We need the raw dataset because it contains the account names (which were dropped in ML phase)
    df = load_paysim()
    
    # Find known fraudulent transactions
    df_fraud = df[df[COL_IS_FRAUD] == 1]
    logger.info(f"Found {len(df_fraud)} fraudulent transactions to sample from.")
    
    if len(df_fraud) == 0:
        logger.error("No fraud found in dataset!")
        return
        
    # We want to pick a few interesting seed accounts.
    # We'll pick one that did a TRANSFER (often part of layering) and one that did CASH_OUT
    fraud_transfers = df_fraud[df_fraud[COL_TYPE] == "TRANSFER"]
    fraud_cashouts = df_fraud[df_fraud[COL_TYPE] == "CASH_OUT"]
    
    random.seed(42)
    seeds = []
    
    if not fraud_transfers.empty:
        # Pick a random transfer seed
        seed_account = fraud_transfers.iloc[random.randint(0, len(fraud_transfers)-1)][COL_NAME_ORIG]
        seeds.append(("Transfer_Layering_Example", seed_account))
        
    if not fraud_cashouts.empty:
        # Pick a random cashout seed
        seed_account = fraud_cashouts.iloc[random.randint(0, len(fraud_cashouts)-1)][COL_NAME_ORIG]
        seeds.append(("CashOut_Example", seed_account))
        
    # Manually adding a few more random seeds to increase chance of a good visual
    for i in range(2):
        seed_account = df_fraud.iloc[random.randint(0, len(df_fraud)-1)][COL_NAME_ORIG]
        seeds.append((f"Random_Fraud_{i}", seed_account))

    logger.info("=" * 70)
    logger.info("PHASE 4: EXTRACTING AND PLOTTING SUBGRAPHS")
    logger.info("=" * 70)
    
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    
    for name, seed in set(seeds):
        logger.info(f"Processing subgraph for {name} (Seed: {seed})...")
        
        # Extract graph (2 hops usually gives a good neighborhood)
        G = extract_fraud_subgraph(df, seed, max_hops=2, max_nodes=50)
        
        # Generate interactive plot
        html_path = FIGURES_DIR / f"09_graph_{name}.html"
        plot_interactive_network(G, html_path, title=f"Money Laundering Network: {name}")
        
        # Generate static plot
        png_path = FIGURES_DIR / f"10_graph_{name}.png"
        plot_static_network(G, png_path, title=f"Money Laundering Network: {name}")
        
    logger.info("Graph visualization complete.")


if __name__ == "__main__":
    main()
