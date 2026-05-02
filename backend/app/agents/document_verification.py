"""Agent 2 — Document Verification.

This agent runs BEFORE any extraction. It catches the most common user errors:
  * Wrong document type uploaded for the claim category
  * Unreadable / blurry documents
  * Required document missing entirely

Per the assignment, error messages here MUST be specific. We name the
uploaded type and the missing/required type explicitly.
"""
from __future__ import annotations

from collections import Counter

from app.agents.base import Agent, PipelineContext
from app.models.schemas import DocumentQuality, UserActionRequired


_FRIENDLY = {
    "PRESCRIPTION": "prescription",
    "HOSPITAL_BILL": "hospital bill",
    "PHARMACY_BILL": "pharmacy bill",
    "LAB_REPORT": "lab report",
    "DIAGNOSTIC_REPORT": "diagnostic report",
    "DENTAL_REPORT": "dental report",
    "DISCHARGE_SUMMARY": "discharge summary",
    "UNKNOWN": "unrecognised document",
}


def _friendly(t: str) -> str:
    return _FRIENDLY.get(t, t.lower().replace("_", " "))


class DocumentVerificationAgent(Agent):
    name = "DocumentVerificationAgent"

    async def run(self, ctx: PipelineContext) -> None:
        sub = ctx.submission
        reqs = ctx.policy.doc_requirements(sub.claim_category.value)
        required = list(reqs.get("required", []))

        # 1. Quality gate first — if any required doc is unreadable, ask for re-upload.
        for doc in sub.documents:
            if doc.quality == DocumentQuality.UNREADABLE and doc.actual_type.value in required:
                ctx.halt = UserActionRequired(
                    code="UNREADABLE_DOCUMENT",
                    title="We couldn't read one of your documents",
                    message=(
                        f"The {_friendly(doc.actual_type.value)} you uploaded "
                        f"({doc.file_name or doc.file_id}) is too blurry to process. "
                        "Please re-upload a clearer photo or scan of just that document — "
                        "the rest of your submission is fine."
                    ),
                    affected_documents=[doc.file_id],
                )
                ctx.trace.add(
                    self.name,
                    "failed",
                    f"Required {_friendly(doc.actual_type.value)} is unreadable.",
                    {"file_id": doc.file_id, "quality": doc.quality.value},
                )
                return

        # 2. Required-vs-uploaded check
        uploaded_counts = Counter(d.actual_type.value for d in sub.documents)
        missing = [r for r in required if uploaded_counts.get(r, 0) == 0]

        if missing:
            uploaded_summary = ", ".join(
                f"{n}× {_friendly(t)}" for t, n in uploaded_counts.items()
            ) or "nothing"
            missing_friendly = " and ".join(_friendly(m) for m in missing)
            required_friendly = " and ".join(_friendly(r) for r in required)
            ctx.halt = UserActionRequired(
                code="WRONG_DOCUMENT_TYPE",
                title="Wrong documents uploaded",
                message=(
                    f"For a {sub.claim_category.value.lower().replace('_', ' ')} claim we need "
                    f"{required_friendly}. You uploaded {uploaded_summary}, which means we are "
                    f"still missing the {missing_friendly}. Please upload the {missing_friendly} "
                    "and resubmit."
                ),
                affected_documents=[d.file_id for d in sub.documents],
            )
            ctx.trace.add(
                self.name,
                "failed",
                f"Missing required documents: {missing}",
                {"required": required, "uploaded": dict(uploaded_counts)},
            )
            return

        ctx.trace.add(
            self.name,
            "passed",
            f"All required documents present for {sub.claim_category.value} claim.",
            {"required": required, "uploaded": dict(uploaded_counts)},
        )
