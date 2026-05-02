"""Pipeline orchestrator — runs agents in order, respects halts, builds final ClaimDecision."""
from __future__ import annotations

import uuid

from app.agents.adjudication import AdjudicationAgent
from app.agents.base import PipelineContext, safe_run
from app.agents.cross_validation import CrossValidationAgent
from app.agents.document_verification import DocumentVerificationAgent
from app.agents.extraction import ExtractionAgent
from app.agents.fraud_detection import FraudDetectionAgent
from app.agents.intake import IntakeAgent
from app.agents.limits import LimitsAgent
from app.agents.policy_coverage import PolicyCoverageAgent
from app.core.policy import get_policy
from app.core.trace import TraceRecorder
from app.models.schemas import (
    ClaimDecision,
    ClaimSubmission,
    Decision,
)


PRE_DECISION_AGENTS = [
    IntakeAgent(),
    DocumentVerificationAgent(),
    ExtractionAgent(),
    CrossValidationAgent(),
]

ANALYSIS_AGENTS = [
    PolicyCoverageAgent(),
    LimitsAgent(),
    FraudDetectionAgent(),
]

ADJUDICATOR = AdjudicationAgent()


async def run_pipeline(submission: ClaimSubmission) -> ClaimDecision:
    ctx = PipelineContext(submission=submission, policy=get_policy(), trace=TraceRecorder())

    # ---- Phase 1: Intake & document gating (each can halt the pipeline) ----
    for agent in PRE_DECISION_AGENTS:
        await safe_run(agent, ctx, critical=True)
        if ctx.halt:
            break

    if ctx.halt:
        return _finalize(ctx, decision=Decision.NEEDS_USER_ACTION)

    # ---- Phase 2: Policy analysis (these never halt; they accumulate findings) ----
    for agent in ANALYSIS_AGENTS:
        await safe_run(agent, ctx, critical=False)

    # ---- Phase 3: Adjudication ----
    await safe_run(ADJUDICATOR, ctx, critical=True)
    return _finalize(ctx)


def _finalize(ctx: PipelineContext, decision: Decision | None = None) -> ClaimDecision:
    final_decision = decision or ctx.decision
    return ClaimDecision(
        claim_id=f"CLM-{uuid.uuid4().hex[:10].upper()}",
        decision=final_decision,
        approved_amount=ctx.approved_amount,
        rejection_reasons=ctx.rejection_reasons,
        line_items=ctx.line_items,
        calculation=ctx.calculation,
        confidence_score=round(ctx.confidence, 2),
        notes=ctx.notes,
        user_action=ctx.halt,
        fraud_signals=ctx.fraud_signals,
        degraded=bool(ctx.degraded_components),
        degraded_components=ctx.degraded_components,
        trace=ctx.trace.steps,
        submission=ctx.submission,
    )
