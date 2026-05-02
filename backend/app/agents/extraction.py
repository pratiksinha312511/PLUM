"""Agent 3 — Extraction.

For the assignment, document `content` is provided as structured JSON in the
test cases. In a real system this is where Sarvam (or a vision model) would
parse uploaded images/PDFs into the same shape.

We expose an `extract_via_llm` path that the API uses when raw text is
provided through the upload endpoint. If the LLM fails we degrade gracefully
and leave the structured `content` as-is.
"""
from __future__ import annotations

from app.agents.base import Agent, PipelineContext
from app.models.schemas import DocumentType
from app.services.sarvam import SarvamClient, SarvamError


EXTRACTION_SYSTEM_PROMPT = (
    "You are a precise medical document parser for an Indian health insurer. "
    "Read the OCR text the user provides and return a JSON object with the "
    "fields you can find: doctor_name, doctor_registration, patient_name, "
    "date (YYYY-MM-DD), diagnosis, medicines (array), tests_ordered (array), "
    "hospital_name, line_items (array of {description, amount}), total. "
    "Use null for missing fields. Never invent data."
)


class ExtractionAgent(Agent):
    name = "ExtractionAgent"

    async def run(self, ctx: PipelineContext) -> None:
        diagnoses: list[str] = []
        for doc in ctx.submission.documents:
            content = dict(doc.content or {})
            ctx.extracted[doc.file_id] = content

            diag = content.get("diagnosis")
            if isinstance(diag, str) and diag:
                diagnoses.append(diag)

            # If line_items missing on a bill, synthesise from total.
            if doc.actual_type in (DocumentType.HOSPITAL_BILL, DocumentType.PHARMACY_BILL):
                if not content.get("line_items") and content.get("total") is not None:
                    content["line_items"] = [
                        {"description": "Total billed", "amount": content["total"]}
                    ]

        ctx.detected_diagnoses = diagnoses
        ctx.trace.add(
            self.name,
            "passed",
            f"Extracted structured content from {len(ctx.submission.documents)} document(s).",
            {
                "diagnoses": diagnoses,
                "doc_count": len(ctx.submission.documents),
            },
        )


async def extract_text_via_llm(text: str) -> dict:
    """Optional helper used by the /upload-text endpoint."""
    client = SarvamClient()
    try:
        return await client.chat_json(EXTRACTION_SYSTEM_PROMPT, text)
    except SarvamError:
        return {}
