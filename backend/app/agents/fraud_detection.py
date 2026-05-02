"""Agent 7 — Fraud detection.

Rules-based for now. Each match is recorded as a *signal*; the adjudicator
decides whether to flag for manual review.
"""
from __future__ import annotations

from collections import Counter

from app.agents.base import Agent, PipelineContext


class FraudDetectionAgent(Agent):
    name = "FraudDetectionAgent"

    async def run(self, ctx: PipelineContext) -> None:
        sub = ctx.submission
        thresholds = ctx.policy.fraud_thresholds

        signals: list[str] = []

        # Same-day claims (TC009)
        same_day = [c for c in sub.claims_history if c.date == sub.treatment_date]
        same_day_limit = thresholds.get("same_day_claims_limit", 2)
        # The history excludes the current claim, so total = len(same_day) + 1
        total_same_day = len(same_day) + 1
        if total_same_day > same_day_limit:
            providers = sorted({c.provider for c in same_day if c.provider})
            signals.append(
                f"{total_same_day} claims on {sub.treatment_date} (limit {same_day_limit}); "
                f"providers seen: {', '.join(providers)}."
            )

        # High-value
        threshold = thresholds.get("auto_manual_review_above")
        if threshold and sub.claimed_amount >= threshold:
            signals.append(
                f"Claim of ₹{sub.claimed_amount:,.0f} meets the high-value review threshold ₹{threshold:,.0f}."
            )

        # Provider concentration
        provider_counts = Counter(c.provider for c in sub.claims_history if c.provider)
        if provider_counts and max(provider_counts.values()) >= 3:
            top, n = provider_counts.most_common(1)[0]
            signals.append(f"{n} prior claims at the same provider ({top}).")

        ctx.fraud_signals = signals
        ctx.trace.add(
            self.name,
            "passed" if not signals else "info",
            f"{len(signals)} fraud signal(s) detected." if signals else "No fraud signals.",
            {"signals": signals},
        )
