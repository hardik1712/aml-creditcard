"""
Automated Transaction Ingestion Stream Simulator.

Simulates a live core-banking transaction feed by generating realistic normal
and adversarial/fraudulent transactions. The agentic pipeline intercepts these
events in real-time, extracts features, performs LightGBM inference, executes
autonomous triage, and triggers SAR generation for high-risk anomalies.
"""

import asyncio
import datetime
import logging
import random
import uuid
from typing import Callable, Dict, List, Optional

from aml_detector.schemas import (
    TransactionRequest,
    TransactionType,
    RiskTier,
    AgentAction,
    PipelineTransactionEvent,
    PipelineStreamStatus,
)

logger = logging.getLogger(__name__)


class StreamSimulator:
    """Manages the background automated transaction ingestion stream."""

    def __init__(self):
        self.is_running: bool = False
        self.speed_tps: float = 1.0  # transactions per second
        self.total_ingested: int = 0
        self.total_approved: int = 0
        self.total_flagged: int = 0
        self.total_sars_generated: int = 0
        self.events: List[PipelineTransactionEvent] = []
        self._max_events: int = 100
        self._task: Optional[asyncio.Task] = None
        self._process_callback: Optional[Callable] = None
        self._step_counter: int = random.randint(10, 50)

    def set_processor(self, callback: Callable):
        """Set the callback function that scores and triages transactions."""
        self._process_callback = callback

    def generate_random_transaction(self) -> TransactionRequest:
        """Generate a realistic transaction (90% normal, 10% anomalous/fraudulent)."""
        self._step_counter += 1
        is_fraud_scenario = random.random() < 0.18  # 18% chance of interesting anomaly for demo

        orig_id = f"C{random.randint(1000000000, 9999999999)}"
        dest_id = f"M{random.randint(1000000000, 9999999999)}" if random.random() < 0.5 else f"C{random.randint(1000000000, 9999999999)}"

        if is_fraud_scenario:
            scenario = random.choice(["drain", "structuring", "large_transfer", "mule_passthrough"])

            if scenario == "drain":
                # Account takeover / total liquidation
                old_orig = round(random.uniform(50000, 750000), 2)
                amount = old_orig
                new_orig = 0.0
                old_dest = 0.0
                new_dest = 0.0  # Mule sink
                tx_type = TransactionType.TRANSFER
            elif scenario == "structuring":
                # Sub-threshold transfer
                old_orig = round(random.uniform(15000, 80000), 2)
                amount = round(random.uniform(9200, 9950), 2)
                new_orig = max(0.0, round(old_orig - amount, 2))
                old_dest = round(random.uniform(0, 5000), 2)
                new_dest = round(old_dest + amount, 2)
                tx_type = random.choice([TransactionType.TRANSFER, TransactionType.CASH_OUT])
            elif scenario == "large_transfer":
                # Massive transfer with ghost destination
                old_orig = round(random.uniform(300000, 2000000), 2)
                amount = round(random.uniform(250000, old_orig * 0.9), 2)
                new_orig = round(old_orig - amount, 2)
                old_dest = 0.0
                new_dest = 0.0
                tx_type = TransactionType.TRANSFER
            else: # mule_passthrough
                old_orig = round(random.uniform(100000, 500000), 2)
                amount = round(random.uniform(80000, old_orig), 2)
                new_orig = 0.0
                old_dest = 0.0
                new_dest = 0.0
                tx_type = TransactionType.CASH_OUT
        else:
            # Normal transaction
            tx_type = random.choice([
                TransactionType.PAYMENT,
                TransactionType.PAYMENT,
                TransactionType.CASH_OUT,
                TransactionType.TRANSFER,
                TransactionType.CASH_IN,
                TransactionType.DEBIT,
            ])
            amount = round(random.expovariate(1 / 450) + 10, 2)
            if amount > 50000:
                amount = round(random.uniform(50, 2500), 2)

            old_orig = round(random.uniform(amount, amount * 10 + 500), 2)
            new_orig = round(old_orig - amount if tx_type != TransactionType.CASH_IN else old_orig + amount, 2)

            old_dest = round(random.uniform(0, 10000), 2)
            new_dest = round(old_dest + amount if tx_type != TransactionType.CASH_IN else max(0.0, old_dest - amount), 2)

        return TransactionRequest(
            step=self._step_counter,
            type=tx_type,
            amount=amount,
            nameOrig=orig_id,
            oldbalanceOrg=old_orig,
            newbalanceOrig=new_orig,
            nameDest=dest_id,
            oldbalanceDest=old_dest,
            newbalanceDest=new_dest,
        )

    async def _stream_loop(self):
        """Main loop that continuously pushes transactions into the pipeline."""
        logger.info("Transaction stream simulator started at %.1f TPS", self.speed_tps)
        while self.is_running:
            try:
                tx = self.generate_random_transaction()
                if self._process_callback:
                    event = await self._process_callback(tx)
                    self.total_ingested += 1
                    if event.agent_action == AgentAction.AUTO_APPROVE:
                        self.total_approved += 1
                    else:
                        self.total_flagged += 1

                    if event.sar_generated:
                        self.total_sars_generated += 1

                    self.events.insert(0, event)
                    if len(self.events) > self._max_events:
                        self.events.pop()

                delay = max(0.2, 1.0 / self.speed_tps)
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in transaction stream loop: %s", e)
                await asyncio.sleep(1.0)

    def start(self, speed_tps: float = 1.0):
        """Start the automated background stream."""
        if self.is_running:
            self.speed_tps = max(0.2, min(speed_tps, 10.0))
            return

        self.is_running = True
        self.speed_tps = max(0.2, min(speed_tps, 10.0))
        self._task = asyncio.create_task(self._stream_loop())

    def stop(self):
        """Stop the background stream."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        logger.info("Transaction stream simulator stopped.")

    def reset_stats(self):
        """Reset stream counters and history."""
        self.total_ingested = 0
        self.total_approved = 0
        self.total_flagged = 0
        self.total_sars_generated = 0
        self.events.clear()

    def get_status(self) -> PipelineStreamStatus:
        """Get snapshot of current pipeline status."""
        return PipelineStreamStatus(
            is_running=self.is_running,
            speed_tps=self.speed_tps,
            total_ingested=self.total_ingested,
            total_approved=self.total_approved,
            total_flagged=self.total_flagged,
            total_sars_generated=self.total_sars_generated,
            recent_events=self.events[:50],
        )


# Global singleton instance
stream_simulator = StreamSimulator()
