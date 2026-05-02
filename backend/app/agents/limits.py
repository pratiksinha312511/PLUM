"""Agent 6 — Limits.

Checks per-claim limit (TC008), category sub-limit, and annual OPD limit.
"""
from __future__ import annotations

from app.agents.base import Agent, PipelineContext
from app.models.schemas import ClaimCategory, RejectionReason


class LimitsAgent(Agent):
    name = "LimitsAgent"

    async def run(self, ctx: PipelineContext) -> None:
        sub = ctx.submission
        coverage = ctx.policy.coverage
        cat_cfg = ctx.policy.category(sub.claim_category.value)

        per_claim = coverage.get("per_claim_limit")
        annual_opd = coverage.get("annual_opd_limit")
        sub_limit = cat_cfg.get("sub_limit")

        # Per-claim limit applies to OPD consultation claims only.
        # Dental, vision, pharmacy and diagnostic have their own (higher) sub-limits
        # — capping them at the per-claim figure would invalidate those allowances.
        applies_per_claim = sub.claim_category == ClaimCategory.CONSULTATION

        # Per-claim limit (HARD reject — TC008)
        if applies_per_claim and per_claim and sub.claimed_amount > per_claim:
            ctx.rejection_reasons.append(RejectionReason.PER_CLAIM_EXCEEDED)
            ctx.notes = (
                f"This policy caps a single claim at ₹{per_claim:,.0f}. "
                f"You claimed ₹{sub.claimed_amount:,.0f}. "
                "Please split your bill or contact HR to request a high-value review."
            )
            ctx.trace.add(
                self.name, "failed",
                f"Claim ₹{sub.claimed_amount:,.0f} exceeds per-claim limit ₹{per_claim:,.0f}.",
                {"per_claim_limit": per_claim, "claimed": sub.claimed_amount},
            )
            return

        # Annual OPD
        if annual_opd and (sub.ytd_claims_amount + sub.claimed_amount) > annual_opd:
            ctx.rejection_reasons.append(RejectionReason.ANNUAL_LIMIT_EXCEEDED)
            ctx.notes = (
                f"Annual OPD limit of ₹{annual_opd:,.0f} would be exceeded. "
                f"Used so far: ₹{sub.ytd_claims_amount:,.0f}."
            )
            ctx.trace.add(
                self.name, "failed",
                "Annual OPD limit would be exceeded.",
                {"annual_opd_limit": annual_opd, "ytd": sub.ytd_claims_amount},
            )
            return

        ctx.trace.add(
            self.name,
            "passed",
            "All limit checks passed.",
            {
                "per_claim_limit": per_claim,
                "annual_opd_limit": annual_opd,
                "sub_limit": sub_limit,
                "ytd": sub.ytd_claims_amount,
            },
        )
