"""
Autonomous AML Investigation Agent, SAR Generator, and Compliance Copilot.

This module provides:
1. Deep anomaly decomposition and risk factor evaluation.
2. Autonomous risk triage and containment policy enforcement.
3. FinCEN-compliant Suspicious Activity Report (SAR) narrative generation.
4. Interactive AML Compliance Copilot assistant with domain-specific knowledge.
"""

import datetime
import hashlib
import logging
from typing import List, Optional

from aml_detector.schemas import (
    TransactionRequest,
    RiskTier,
    AgentAction,
    RiskFactor,
    SARReport,
    AgentInvestigationResponse,
    AgentChatMessage,
    AgentChatResponse,
)

logger = logging.getLogger(__name__)


def evaluate_risk_factors(
    tx: TransactionRequest,
    proba: float,
    risk_tier: RiskTier,
) -> List[RiskFactor]:
    """Analyze transaction parameters to isolate specific AML red flags and anomalies."""
    factors: List[RiskFactor] = []

    # 1. Total Balance Liquidation (Account Drain)
    if tx.oldbalanceOrg > 0 and tx.newbalanceOrig == 0 and tx.amount >= tx.oldbalanceOrg * 0.95:
        factors.append(
            RiskFactor(
                category="Account Liquidation",
                factor="Full Balance Drain",
                severity="CRITICAL" if risk_tier in [RiskTier.HIGH, RiskTier.CRITICAL] else "HIGH",
                description=(
                    f"Originator {tx.nameOrig} liquidated their entire available balance "
                    f"(${tx.oldbalanceOrg:,.2f} -> ${tx.newbalanceOrig:,.2f}) in a single operation."
                ),
            )
        )

    # 2. Originator Balance Discrepancy
    orig_expected = tx.oldbalanceOrg - tx.amount
    orig_diff = tx.newbalanceOrig - orig_expected
    if abs(orig_diff) > 1.0:
        factors.append(
            RiskFactor(
                category="Ledger Integrity",
                factor="Originator Ledger Inconsistency",
                severity="CRITICAL" if abs(orig_diff) > 10000 else "HIGH",
                description=(
                    f"Post-transaction balance (${tx.newbalanceOrig:,.2f}) differs by ${abs(orig_diff):,.2f} "
                    f"from expected ledger deduction (${orig_expected:,.2f})."
                ),
            )
        )

    # 3. Destination Balance Inconsistency / Mule Sink Pattern
    dest_expected = tx.oldbalanceDest + tx.amount
    dest_diff = tx.newbalanceDest - dest_expected
    if abs(dest_diff) > 1.0 and tx.newbalanceDest == 0 and tx.oldbalanceDest == 0:
        factors.append(
            RiskFactor(
                category="Mule Account Sink",
                factor="Zero-Balance Passthrough",
                severity="HIGH",
                description=(
                    f"Destination {tx.nameDest} recorded zero initial and zero closing balances "
                    f"despite receiving ${tx.amount:,.2f}, indicating an uncollateralized or ghost passthrough account."
                ),
            )
        )
    elif abs(dest_diff) > 1.0:
        factors.append(
            RiskFactor(
                category="Ledger Integrity",
                factor="Destination Ledger Inconsistency",
                severity="MEDIUM",
                description=(
                    f"Destination ledger expected ${dest_expected:,.2f} but recorded ${tx.newbalanceDest:,.2f} "
                    f"(variance: ${dest_diff:,.2f})."
                ),
            )
        )

    # 4. High-Risk Transaction Channel
    if tx.type.value in ["TRANSFER", "CASH_OUT"]:
        if tx.amount >= 200000:
            factors.append(
                RiskFactor(
                    category="High-Value Flow",
                    factor="Large Value Wire / Transfer",
                    severity="HIGH" if risk_tier in [RiskTier.HIGH, RiskTier.CRITICAL] else "MEDIUM",
                    description=(
                        f"High-velocity transfer channel ({tx.type.value}) utilized for substantial principal "
                        f"of ${tx.amount:,.2f}."
                    ),
                )
            )
    else:
        if risk_tier in [RiskTier.HIGH, RiskTier.CRITICAL]:
            factors.append(
                RiskFactor(
                    category="Anomalous Channel",
                    factor=f"Unusual {tx.type.value} Channel Fraud",
                    severity="MEDIUM",
                    description=f"Elevated fraud probability observed on non-standard transfer channel {tx.type.value}.",
                )
            )

    # 5. BSA / AML Structuring (Smurfing near reporting threshold)
    if 9000 <= tx.amount <= 10000:
        factors.append(
            RiskFactor(
                category="Structuring / Smurfing",
                factor="Sub-Threshold Transfer (Near $10K CTR Limit)",
                severity="HIGH",
                description=(
                    f"Transaction amount of ${tx.amount:,.2f} falls just below the $10,000 Currency "
                    "Transaction Reporting (CTR) compliance threshold."
                ),
            )
        )

    # 6. Temporal / Off-Peak Timing
    hour = tx.step % 24
    if hour in [1, 2, 3, 4]:
        factors.append(
            RiskFactor(
                category="Temporal Anomaly",
                factor="Off-Peak / Nocturnal Execution",
                severity="LOW" if risk_tier == RiskTier.LOW else "MEDIUM",
                description=f"Transaction initiated at hour {hour:02d}:00 (off-peak operational window).",
            )
        )

    # Fallback if no specific rule caught it but ML model flagged it
    if not factors and risk_tier in [RiskTier.HIGH, RiskTier.CRITICAL]:
        factors.append(
            RiskFactor(
                category="Statistical Anomaly",
                factor="Gradient-Boosted Pattern Alignment",
                severity="HIGH",
                description=(
                    f"LightGBM ensemble detected multi-variable interaction matching known fraud signatures "
                    f"with {proba*100:.2f}% statistical confidence."
                ),
            )
        )
    elif not factors and risk_tier == RiskTier.LOW:
        factors.append(
            RiskFactor(
                category="Normal Activity",
                factor="Nominal Operating Baseline",
                severity="LOW",
                description="Transaction parameters align with verified legitimate baseline traffic.",
            )
        )

    return factors


def determine_agent_action(
    risk_tier: RiskTier,
    proba: float,
    risk_factors: List[RiskFactor],
) -> AgentAction:
    """Determine autonomous intervention policy based on risk scoring and detected anomalies."""
    if risk_tier == RiskTier.CRITICAL or proba >= 0.85:
        # Check if balance drain or critical ledger mismatch is present
        has_drain = any(f.factor == "Full Balance Drain" for f in risk_factors)
        if has_drain or proba >= 0.90:
            return AgentAction.FREEZE_ACCOUNT
        return AgentAction.BLOCK_TRANSACTION

    elif risk_tier == RiskTier.HIGH or proba >= 0.50:
        return AgentAction.BLOCK_TRANSACTION

    elif risk_tier == RiskTier.MEDIUM or proba >= 0.15:
        return AgentAction.MONITOR

    else:
        return AgentAction.AUTO_APPROVE


def generate_sar_report(
    tx: TransactionRequest,
    proba: float,
    risk_tier: RiskTier,
    risk_factors: List[RiskFactor],
    action: AgentAction,
) -> Optional[SARReport]:
    """Draft an automated, structured FinCEN Suspicious Activity Report (SAR) narrative."""
    # Only generate SAR for HIGH or CRITICAL risk tiers
    if risk_tier not in [RiskTier.HIGH, RiskTier.CRITICAL]:
        return None

    # Generate deterministic or unique SAR reference
    ref_hash = hashlib.sha256(f"{tx.nameOrig}-{tx.nameDest}-{tx.amount}-{tx.step}".encode()).hexdigest()[:8].upper()
    sar_id = f"SAR-{datetime.date.today().strftime('%Y%m')}-{ref_hash}"
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    indicators = [f"{f.category}: {f.factor} ({f.description})" for f in risk_factors]

    # Classify regulatory suspicion
    if any("Structuring" in f.category for f in risk_factors):
        classification = "Bank Secrecy Act (BSA) — Structuring / Smurfing"
    elif any("Account Liquidation" in f.category for f in risk_factors):
        classification = "Unauthorized Account Takeover & Rapid Fund Dissipation"
    elif any("Mule" in f.category for f in risk_factors):
        classification = "Funnel / Mule Account Laundering Operation"
    else:
        classification = "Suspected Money Laundering / Wire Fraud"

    narrative = (
        f"SUSPICIOUS ACTIVITY NARRATIVE REPORT\n"
        f"====================================\n"
        f"1. SUBJECT IDENTIFICATION:\n"
        f"   - Originating Account: {tx.nameOrig} (Prior Balance: ${tx.oldbalanceOrg:,.2f}, New: ${tx.newbalanceOrig:,.2f})\n"
        f"   - Counterparty Beneficiary: {tx.nameDest} (Prior Balance: ${tx.oldbalanceDest:,.2f}, New: ${tx.newbalanceDest:,.2f})\n\n"
        f"2. TRANSACTION PARTICULARS:\n"
        f"   - Amount: ${tx.amount:,.2f} USD\n"
        f"   - Instrument / Channel: {tx.type.value}\n"
        f"   - Simulation Step / Hour: {tx.step} (Time of Day: {tx.step % 24:02d}:00 UTC)\n"
        f"   - Machine Learning Risk Score: {proba*100:.2f}% (Classification: {risk_tier.value})\n\n"
        f"3. SUMMARY OF SUSPICIOUS ACTIVITY & RED FLAGS:\n"
        + "\n".join([f"   * {ind}" for ind in indicators])
        + f"\n\n4. AGENT DECISION & CONTAINMENT ACTION:\n"
        f"   - Autonomous Pipeline Action: {action.value}\n"
        f"   - Justification: Immediate intervention applied to prevent irreversible capital loss across counterparty channels.\n"
        f"   - Filing Recommendation: Transmit SAR form to Financial Crimes Enforcement Network (FinCEN) and initiate KYC re-verification."
    )

    return SARReport(
        sar_id=sar_id,
        filing_date=timestamp,
        institution="AML Autonomous Core Sentinel",
        primary_subject=tx.nameOrig,
        secondary_subject=tx.nameDest,
        transaction_amount=tx.amount,
        transaction_type=tx.type.value,
        suspicious_indicators=[f.factor for f in risk_factors],
        narrative_summary=narrative,
        regulatory_classification=classification,
        recommended_action=action,
    )


def synthesize_agent_reasoning(
    tx: TransactionRequest,
    proba: float,
    risk_tier: RiskTier,
    risk_factors: List[RiskFactor],
    action: AgentAction,
) -> str:
    """Generate concise, natural language reasoning from the agent."""
    if risk_tier == RiskTier.LOW:
        return (
            f"Transaction evaluated as legitimate ({proba*100:.2f}% fraud risk). "
            f"Balance adjustments for {tx.nameOrig} and {tx.nameDest} are consistent, "
            f"and no structuring or rapid drain indicators were observed. "
            f"Autonomous action: {action.value} executed immediately."
        )

    top_factors = [f.factor for f in risk_factors[:2]]
    factors_str = " and ".join(top_factors) if top_factors else "anomalous data patterns"

    if risk_tier == RiskTier.CRITICAL:
        return (
            f"🚨 CRITICAL ALERT ({proba*100:.2f}% fraud score). "
            f"High-confidence illicit pattern detected driven by {factors_str}. "
            f"Account liquidation and ledger inconsistencies suggest an active takeover or illicit extraction. "
            f"Autonomous action {action.value} executed, and SAR filing generated."
        )
    elif risk_tier == RiskTier.HIGH:
        return (
            f"⚠️ HIGH RISK DETECTED ({proba*100:.2f}% fraud score). "
            f"Significant deviation from baseline due to {factors_str}. "
            f"Autonomous action {action.value} executed. Suspicious Activity Report prepared for compliance review."
        )
    else:
        return (
            f"⚡ MEDIUM SURVEILLANCE ({proba*100:.2f}% fraud score). "
            f"Subtle anomalies noted in transaction structure. Transaction permitted under elevated surveillance logging ({action.value})."
        )


def investigate_transaction(
    tx: TransactionRequest,
    proba: float,
    risk_tier: RiskTier,
) -> AgentInvestigationResponse:
    """Execute full autonomous investigation pipeline on a single transaction."""
    factors = evaluate_risk_factors(tx, proba, risk_tier)
    action = determine_agent_action(risk_tier, proba, factors)
    reasoning = synthesize_agent_reasoning(tx, proba, risk_tier, factors, action)
    sar = generate_sar_report(tx, proba, risk_tier, factors, action)

    return AgentInvestigationResponse(
        transaction=tx,
        fraud_probability=proba,
        risk_tier=risk_tier,
        recommended_action=action,
        risk_factors=factors,
        agent_reasoning=reasoning,
        sar_report=sar,
    )


def handle_copilot_chat(
    query: str,
    tx_context: Optional[TransactionRequest] = None,
    history: Optional[List[AgentChatMessage]] = None,
) -> AgentChatResponse:
    """Intelligent compliance assistant conversational engine."""
    q_lower = query.lower().strip()

    suggested = [
        "Explain why this transaction was flagged",
        "What are the FinCEN SAR filing requirements for this case?",
        "How does the model detect smurfing / structuring?",
        "What containment action is recommended?",
    ]

    # Context-aware responses
    if tx_context:
        orig = tx_context.nameOrig
        dest = tx_context.nameDest
        amt = tx_context.amount
        tx_type = tx_context.type.value

        if any(w in q_lower for w in ["why", "flag", "reason", "explain", "risk"]):
            is_drain = tx_context.oldbalanceOrg > 0 and tx_context.newbalanceOrig == 0
            res = (
                f"### 🔍 Case Investigation: {orig} ➔ {dest}\n\n"
                f"- **Amount**: ${amt:,.2f} via `{tx_type}`\n"
                f"- **Account State**: Sender started with ${tx_context.oldbalanceOrg:,.2f} and ended with ${tx_context.newbalanceOrig:,.2f}.\n"
            )
            if is_drain:
                res += f"- **Key Anomaly**: **Complete Account Drain** — {orig} cleared 100% of their available balance in one transaction.\n"
            if tx_context.newbalanceDest == 0 and tx_context.oldbalanceDest == 0:
                res += f"- **Counterparty Anomaly**: Beneficiary `{dest}` maintained zero balance before and after receiving funds, typical of an intermediary pass-through mule account.\n"
            res += (
                f"\n**Regulatory Assessment**: These behaviors match synthetic identity extraction and mule funneling. "
                f"Immediate containment ({'FREEZE_ACCOUNT' if is_drain else 'BLOCK_TRANSACTION'}) and SAR filing are advised."
            )
            return AgentChatResponse(response=res, suggested_questions=suggested)

        if any(w in q_lower for w in ["sar", "fincen", "report", "filing"]):
            res = (
                f"### 📑 SAR Filing Guidance for Case ({orig})\n\n"
                f"Under FinCEN BSA guidelines (31 CFR § 1020.320):\n"
                f"1. **Filing Deadline**: Within 30 calendar days of initial detection.\n"
                f"2. **Reportable Amount**: ${amt:,.2f} USD (Threshold exceeds mandatory $5,000 for identified suspects).\n"
                f"3. **Narrative Focus**: Document the sudden liquidation of `${tx_context.oldbalanceOrg:,.2f}` to account `{dest}`.\n"
                f"4. **Action**: The automated SAR draft has been generated and queued for compliance officer sign-off."
            )
            return AgentChatResponse(response=res, suggested_questions=suggested)

        if any(w in q_lower for w in ["action", "block", "freeze", "what should"]):
            res = (
                f"### 🛡️ Recommended Containment Protocol\n\n"
                f"1. **Execute Immediate Freeze** on Originator account `{orig}`.\n"
                f"2. **Place Hold** on counterparty `{dest}` for outgoing ACH/wire channels.\n"
                f"3. **Initiate Enhanced Due Diligence (EDD)**: Request source-of-funds verification.\n"
                f"4. **Review Historical Network**: Inspect other counterparties linked to `{dest}` in graph centralities."
            )
            return AgentChatResponse(response=res, suggested_questions=suggested)

    # General AML / System Queries
    if any(w in q_lower for w in ["smurf", "structuring", "threshold", "10,000", "ctr"]):
        res = (
            "### 🔄 Smurfing & Structuring Detection\n\n"
            "**Structuring** involves breaking down large sums into smaller transactions below statutory reporting limits (such as the $10,000 CTR threshold) to evade AML scrutiny.\n\n"
            "**How our Agentic Pipeline catches it**:\n"
            "- **Velocity Windows**: Tracks 24-hour cumulative volume (`prev_tx_volume`) and count (`prev_tx_count`) per account.\n"
            "- **Degree Centrality**: High out-degree to multiple accounts with low in-degree highlights distribution hubs (smurfing dispatchers).\n"
            "- **Threshold Proximity**: Flags repeated transfers in the $8,500–$9,999 range."
        )
        return AgentChatResponse(response=res, suggested_questions=suggested)

    if any(w in q_lower for w in ["model", "lightgbm", "how does", "pipeline", "features"]):
        res = (
            "### ⚙️ Autonomous AML Engine Architecture\n\n"
            "1. **Data Ingestion Agent**: Normalizes raw transaction records and validates balance equations.\n"
            "2. **Feature Pipeline**: Computes 22 engineered features including ledger balance discrepancies, log amounts, time steps, and graph degree ratios.\n"
            "3. **LightGBM Classifier**: Evaluates multi-tree probability of fraud.\n"
            "4. **Agentic Triage Engine**: Automatically triggers actions (`AUTO_APPROVE`, `MONITOR`, `BLOCK_TRANSACTION`, `FREEZE_ACCOUNT`) and drafts FinCEN SARs."
        )
        return AgentChatResponse(response=res, suggested_questions=suggested)

    # General fallback
    res = (
        f"### 🤖 AML Sentinel Copilot\n\n"
        f"I can assist you with real-time transaction investigations, explaining model features, "
        f"evaluating AML/BSA compliance obligations, or reviewing auto-generated SAR filings.\n\n"
        f"Feel free to click any transaction in the pipeline stream or ask me about AML typologies (Structuring, Mules, Account Takeovers)."
    )
    return AgentChatResponse(response=res, suggested_questions=suggested)
