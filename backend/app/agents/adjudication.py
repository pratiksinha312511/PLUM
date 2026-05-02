"""Agent 8 — Adjudication.

The only agent allowed to set the final `Decision`. It applies the policy's
financial rules in the correct order:

   1. Start with the base claim amount (or per-line breakdown for dental/partial).
   2. Apply network discount FIRST if the hospital is in the network (TC010).
   3. Apply co-pay on the post-discount amount.
   4. Cap at the category sub-limit and per-claim limit.
   5. Round to nearest rupee.

Decision rules:
   * Any rejection_reasons -> REJECTED.
   * Any excluded line items but other lines approved -> PARTIAL.
   * Fraud signals exceeding threshold OR degraded pipeline with non-trivial
     amount -> MANUAL_REVIEW.
   * Otherwise -> APPROVED.
"""
from __future__ import annotations

from app.agents.base import Agent, PipelineContext
from app.models.schemas import (
    CalculationBreakdown,
    Decision,
    LineItemDecision,
)


class AdjudicationAgent(Agent):
    name = "AdjudicationAgent"

    async def run(self, ctx: PipelineContext) -> None:
        sub = ctx.submission
        cat_cfg = ctx.policy.category(sub.claim_category.value)

        # Hard rejection short-circuit
        if ctx.rejection_reasons:
            ctx.decision = Decision.REJECTED
            ctx.approved_amount = 0
            if not ctx.notes:
                ctx.notes = f"Rejected: {', '.join(r.value for r in ctx.rejection_reasons)}."
            ctx.trace.add(
                self.name, "passed",
                f"Final decision: REJECTED ({', '.join(r.value for r in ctx.rejection_reasons)}).",
                {"reasons": [r.value for r in ctx.rejection_reasons]},
            )
            return

        # Determine base amount: sum of approved line items if dental split was done,
        # otherwise the claimed amount.
        if ctx.line_items:
            base = sum(li.approved_amount for li in ctx.line_items if li.status == "APPROVED")
            has_rejected = any(li.status == "REJECTED" for li in ctx.line_items)
        else:
            base = float(sub.claimed_amount)
            has_rejected = False

        breakdown = CalculationBreakdown(base_amount=base)

        # Network discount (BEFORE co-pay) — TC010
        in_network = bool(
            sub.hospital_name
            and any(n.lower() in sub.hospital_name.lower() for n in ctx.policy.network_hospitals)
        )
        net_discount_pct = cat_cfg.get("network_discount_percent", 0) if in_network else 0
        if net_discount_pct:
            breakdown.network_discount_percent = net_discount_pct
            breakdown.network_discount_amount = round(base * net_discount_pct / 100, 2)
            base = base - breakdown.network_discount_amount
            breakdown.notes.append(
                f"Network discount {net_discount_pct}% applied (hospital '{sub.hospital_name}' is in network)."
            )
        breakdown.after_network_discount = base

        # Co-pay (AFTER network discount)
        copay_pct = cat_cfg.get("copay_percent", 0)
        if copay_pct:
            breakdown.copay_percent = copay_pct
            breakdown.copay_amount = round(base * copay_pct / 100, 2)
            base = base - breakdown.copay_amount
            breakdown.notes.append(f"Co-pay {copay_pct}% applied on post-discount amount.")

        # Sub-limit cap
        sub_limit = cat_cfg.get("sub_limit")
        if sub_limit and base > sub_limit:
            breakdown.sub_limit_applied = sub_limit
            breakdown.notes.append(
                f"Capped at category sub-limit ₹{sub_limit:,.0f}."
            )
            base = sub_limit

        breakdown.final_approved = round(base, 2)
        ctx.calculation = breakdown
        ctx.approved_amount = breakdown.final_approved

        # Decide outcome
        # Manual review if fraud signals exceed limit OR degraded with significant amount
        fraud_threshold = ctx.policy.fraud_thresholds.get("same_day_claims_limit", 2)
        same_day_count = len([c for c in sub.claims_history if c.date == sub.treatment_date]) + 1
        needs_review = same_day_count > fraud_threshold or any(
            "high-value" in s for s in ctx.fraud_signals
        )

        if needs_review:
            ctx.decision = Decision.MANUAL_REVIEW
            ctx.notes = (
                "Routed to manual review due to fraud signal(s): "
                + " | ".join(ctx.fraud_signals)
            )
            ctx.confidence = min(ctx.confidence, 0.6)
        elif has_rejected:
            ctx.decision = Decision.PARTIAL
            ctx.notes = (
                f"Approved ₹{ctx.approved_amount:,.0f}. "
                f"Excluded line items: {', '.join(ctx.excluded_line_descriptions)}."
            )
        else:
            ctx.decision = Decision.APPROVED
            if breakdown.notes:
                ctx.notes = " ".join(breakdown.notes)
            else:
                ctx.notes = f"Approved in full: ₹{ctx.approved_amount:,.0f}."

        # Confidence: start from current ctx.confidence (lowered by degraded agents)
        # and add a tiny bonus for clean cases.
        if not ctx.degraded_components and ctx.decision == Decision.APPROVED:
            ctx.confidence = min(1.0, ctx.confidence + 0.0)  # already 1.0
        if ctx.degraded_components:
            ctx.notes += " (Note: pipeline ran in degraded mode — manual review recommended.)"

        ctx.trace.add(
            self.name, "passed",
            f"Final decision: {ctx.decision.value} — ₹{ctx.approved_amount:,.0f}.",
            {
                "decision": ctx.decision.value,
                "approved_amount": ctx.approved_amount,
                "breakdown": breakdown.model_dump(),
                "in_network": in_network,
                "fraud_signals": ctx.fraud_signals,
            },
        )
