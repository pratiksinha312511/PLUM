"""Base contract for every pipeline agent.

Each agent is a single-responsibility unit. It takes the mutable
`PipelineContext` and either:
  * mutates the context with new findings, OR
  * sets `context.halt` with a `UserActionRequired` message, OR
  * sets a `Decision` directly on `context` (only the Adjudication agent does this).

Every agent is wrapped in `safe_run` which catches exceptions, records a
`degraded` step in the trace, and lets the pipeline continue.
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.policy import Policy
from app.core.trace import TraceRecorder
from app.models.schemas import (
    CalculationBreakdown,
    ClaimSubmission,
    Decision,
    LineItemDecision,
    RejectionReason,
    UserActionRequired,
)


@dataclass
class PipelineContext:
    submission: ClaimSubmission
    policy: Policy
    trace: TraceRecorder = field(default_factory=TraceRecorder)

    # Findings filled in by agents
    member: Optional[dict[str, Any]] = None
    extracted: dict[str, dict[str, Any]] = field(default_factory=dict)  # file_id -> content
    detected_diagnoses: list[str] = field(default_factory=list)
    fraud_signals: list[str] = field(default_factory=list)
    line_items: list[LineItemDecision] = field(default_factory=list)
    rejection_reasons: list[RejectionReason] = field(default_factory=list)
    excluded_line_descriptions: list[str] = field(default_factory=list)

    # Final outputs
    halt: Optional[UserActionRequired] = None
    decision: Optional[Decision] = None
    approved_amount: float = 0
    calculation: Optional[CalculationBreakdown] = None
    notes: str = ""
    confidence: float = 1.0

    # Resilience
    degraded_components: list[str] = field(default_factory=list)


class Agent:
    name: str = "BaseAgent"

    async def run(self, ctx: PipelineContext) -> None:  # pragma: no cover - interface
        raise NotImplementedError


async def safe_run(agent: Agent, ctx: PipelineContext, *, critical: bool = False) -> None:
    """Run an agent and never let it bring down the pipeline."""
    start = time.perf_counter()
    try:
        # Component-failure simulation hook (per TC011)
        if ctx.submission.simulate_component_failure and agent.name == "FraudDetectionAgent":
            raise RuntimeError("Simulated component failure")
        await agent.run(ctx)
    except Exception as exc:  # noqa: BLE001 — by design
        duration = (time.perf_counter() - start) * 1000
        ctx.degraded_components.append(agent.name)
        ctx.confidence = max(0.4, ctx.confidence - 0.2)
        ctx.trace.add(
            agent=agent.name,
            status="error",
            summary=f"{agent.name} failed and was skipped: {exc}",
            details={"error": str(exc), "trace": traceback.format_exc().splitlines()[-3:]},
            duration_ms=duration,
        )
        if critical:
            # Critical agents (intake/doc-check) bubble up a halt instead.
            ctx.halt = UserActionRequired(
                code="PIPELINE_ERROR",
                title="We hit an unexpected error",
                message=f"Our {agent.name} component could not complete. Please retry.",
            )
