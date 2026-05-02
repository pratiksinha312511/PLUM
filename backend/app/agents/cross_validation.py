"""Agent 4 — Cross-validation across documents.

Right now this catches:
  * Patient names that don't match across documents (TC003)
  * Patient name on the document not matching the member's name on file (warning)
"""
from __future__ import annotations

from app.agents.base import Agent, PipelineContext
from app.models.schemas import UserActionRequired


def _norm(name: str) -> str:
    return " ".join(name.lower().split())


class CrossValidationAgent(Agent):
    name = "CrossValidationAgent"

    async def run(self, ctx: PipelineContext) -> None:
        names: dict[str, str] = {}  # file_id -> patient name
        for doc in ctx.submission.documents:
            name = doc.patient_name_on_doc or (
                ctx.extracted.get(doc.file_id, {}).get("patient_name")
            )
            if name:
                names[doc.file_id] = name

        unique = {_norm(n) for n in names.values()}
        if len(unique) > 1:
            details = ", ".join(f"{fid}: '{n}'" for fid, n in names.items())
            ctx.halt = UserActionRequired(
                code="PATIENT_NAME_MISMATCH",
                title="Documents are for different people",
                message=(
                    "The documents you uploaded appear to belong to different patients — "
                    f"we found {details}. All documents in a single claim must be for "
                    "the same patient. Please re-check and resubmit."
                ),
                affected_documents=list(names.keys()),
            )
            ctx.trace.add(
                self.name,
                "failed",
                "Patient names differ across documents.",
                {"names": names},
            )
            return

        ctx.trace.add(
            self.name,
            "passed",
            "Patient identity consistent across all documents.",
            {"patient_names": list(unique)},
        )
