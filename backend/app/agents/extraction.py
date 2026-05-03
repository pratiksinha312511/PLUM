"""Agent 3 — Extraction.

For the assignment, document `content` is provided as structured JSON in the
test cases. In a real system this is where Sarvam (or a vision model) would
parse uploaded images/PDFs into the same shape.

We expose an `extract_image_via_llm` path that the upload endpoint uses to
turn a raw image / PDF into a fully-classified document envelope:
  - which document type the file is (PRESCRIPTION, HOSPITAL_BILL, ...)
  - quality assessment (GOOD / POOR / UNREADABLE)
  - patient name
  - the structured fields the pipeline cares about
  - per-field + overall confidence
  - any warnings the model wants to surface

If the LLM fails or returns garbage we degrade gracefully and the caller
marks the doc as UNREADABLE so the pipeline halts cleanly.
"""
from __future__ import annotations

from typing import Any

from app.agents.base import Agent, PipelineContext
from app.models.schemas import DocumentType
from app.services.sarvam import SarvamClient, SarvamError


_VALID_DOC_TYPES = {t.value for t in DocumentType}
_VALID_QUALITY = {"GOOD", "POOR", "UNREADABLE"}

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


VISION_SYSTEM_PROMPT = (
    "You are an expert medical-document analyst for an Indian health insurer. "
    "You will be shown ONE image of a single medical document (prescription, "
    "hospital bill, lab report, pharmacy invoice, discharge summary, dental "
    "chart, or medical certificate). "
    "You MUST return ONE strict JSON object with this exact shape:\n"
    "{\n"
    '  "doc_type": one of ["PRESCRIPTION","HOSPITAL_BILL","PHARMACY_BILL",'
    '"LAB_REPORT","DISCHARGE_SUMMARY","DENTAL_CHART","MEDICAL_CERTIFICATE",'
    '"INSURANCE_CARD","UNKNOWN"],\n'
    '  "doc_type_confidence": float in [0,1],\n'
    '  "quality": one of ["GOOD","POOR","UNREADABLE"],\n'
    '  "patient_name": string or null,\n'
    '  "fields": {\n'
    '     "doctor_name": string or null,\n'
    '     "doctor_registration": string or null,\n'
    '     "date": "YYYY-MM-DD" or null,\n'
    '     "diagnosis": string or null,\n'
    '     "medicines": [string] or [],\n'
    '     "tests_ordered": [string] or [],\n'
    '     "hospital_name": string or null,\n'
    '     "line_items": [{"description": string, "amount": number}] or [],\n'
    '     "total": number or null\n'
    "  },\n"
    '  "warnings": [string]   // anything you noticed the user should verify\n'
    "}\n\n"
    "Rules:\n"
    "1. Use null / [] for fields you cannot read with confidence. "
    "DO NOT invent values. Hallucinations cost us money and customer trust.\n"
    "2. If the image is blank, blurry, rotated badly, or not a medical "
    "document, set quality=UNREADABLE and doc_type=UNKNOWN.\n"
    "3. doc_type_confidence reflects how sure you are about the document "
    "category. Below 0.7 means the user should confirm.\n"
    "4. Numbers are unitless rupees. Strip currency symbols and commas.\n"
    "5. Output ONLY the JSON object — no commentary, no markdown fences."
)

VISION_USER_PROMPT = (
    "Analyse this document image and return the JSON envelope as specified."
)

# When we hand OCR text (no image) to the text LLM we use the same envelope
# rules but reword the framing so the model knows it's reading raw OCR.
OCR_SYSTEM_PROMPT = VISION_SYSTEM_PROMPT.replace(
    "You will be shown ONE image of a single medical document",
    "You will be given the raw OCR text of a single medical document",
).replace(
    "If the image is blank, blurry, rotated badly, or not a medical "
    "document, set quality=UNREADABLE and doc_type=UNKNOWN.",
    "If the OCR text is empty, gibberish, or clearly not a medical "
    "document, set quality=UNREADABLE and doc_type=UNKNOWN. "
    "If the text is readable but sparse / partially garbled, mark "
    "quality=POOR and still extract whatever you can.",
)


def _ocr_user_prompt(text: str) -> str:
    snippet = text.strip()
    # Hard cap to keep prompt tokens bounded; medical docs rarely need more.
    if len(snippet) > 6000:
        snippet = snippet[:6000] + "\n...[truncated]"
    return (
        "Below is the raw OCR text extracted from a medical document. "
        "Classify it and extract the structured envelope.\n\n"
        "===== BEGIN OCR TEXT =====\n"
        f"{snippet}\n"
        "===== END OCR TEXT ====="
    )


async def extract_image_via_llm(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Two-stage extraction: OCR.space for text, Sarvam text LLM for structure.

    We previously called Sarvam's vision endpoint directly, but it rejects
    requests from several cloud egress IPs (403 Forbidden). OCR.space is
    a reliable free OCR layer; the text LLM then handles classification +
    field extraction with the same envelope guarantees.

    Returns a validated envelope:
        {
          "doc_type": str,            # always set; UNKNOWN on failure
          "doc_type_confidence": float,
          "quality": str,             # GOOD / POOR / UNREADABLE
          "patient_name": str | None,
          "fields": dict,             # the same shape pipelines consume
          "warnings": [str],
          "extraction_status": "OK" | "LLM_ERROR" | "INVALID_RESPONSE" | "OCR_ERROR",
        }
    """
    # Lazy import to avoid a circular dep at module load.
    from app.services.ocr_space import OcrSpaceClient, OcrSpaceError

    ocr = OcrSpaceClient()
    try:
        text = await ocr.parse_image(image_bytes, mime_type)
    except OcrSpaceError as exc:
        return _failed_envelope("OCR_ERROR", _friendly_ocr_error(str(exc)))

    sarvam = SarvamClient()
    try:
        raw = await sarvam.chat_json(OCR_SYSTEM_PROMPT, _ocr_user_prompt(text))
    except SarvamError as exc:
        # OCR worked but the LLM didn't — degrade gracefully and at least
        # surface the raw text so the user can copy/paste into the editor.
        envelope = _failed_envelope("LLM_ERROR", _friendly_llm_error(str(exc)))
        envelope["fields"] = {"raw_ocr_text": text[:2000]}
        envelope["quality"] = "POOR"
        return envelope

    envelope = _coerce_envelope(raw)
    # Always preserve the raw OCR text in case the user wants to verify.
    envelope.setdefault("fields", {})
    if "raw_ocr_text" not in envelope["fields"]:
        envelope["fields"]["raw_ocr_text"] = text[:2000]
    return envelope


def _friendly_ocr_error(raw: str) -> str:
    text = raw.strip()
    low = text.lower()
    if "no text" in low:
        return (
            "OCR could not read any text from this file. The image may be "
            "blank, too blurry, or upside down. Please re-upload a clearer "
            "scan, or fill the details manually below."
        )
    if "401" in low or "403" in low or "unauthorized" in low or "forbidden" in low:
        return (
            "The OCR service rejected our credentials. "
            "Please ask an administrator to refresh OCR_SPACE_API_KEY."
        )
    if "timeout" in low or "timed out" in low:
        return "The OCR service timed out. Please retry, or fill the details manually."
    if "disabled" in low:
        return "OCR is not configured on this server. Please fill the details manually."
    return text.split(" For more information")[0][:240]


def _friendly_llm_error(raw: str) -> str:
    """Turn raw httpx error text into something safe to show end-users."""
    text = raw.strip()
    low = text.lower()
    if "401" in low or "unauthorized" in low:
        return (
            "The vision service rejected our credentials. "
            "Please ask an administrator to refresh the SARVAM_API_KEY."
        )
    if "403" in low or "forbidden" in low:
        return (
            "The vision service refused this request (403). "
            "The API key is missing, expired, or not allowed from this server. "
            "You can still fill the document details manually below."
        )
    if "429" in low or "rate" in low:
        return "The vision service is rate-limiting us. Please retry in a minute."
    if "timeout" in low or "timed out" in low:
        return "The vision service timed out. Please retry, or fill the details manually."
    if "connection" in low or "network" in low:
        return "Could not reach the vision service. Check connectivity and retry."
    # Strip the noisy MDN URL httpx appends.
    return text.split(" For more information")[0][:240]


def _failed_envelope(status: str, reason: str) -> dict[str, Any]:
    return {
        "doc_type": "UNKNOWN",
        "doc_type_confidence": 0.0,
        "quality": "UNREADABLE",
        "patient_name": None,
        "fields": {},
        "warnings": [reason],
        "extraction_status": status,
    }


def _coerce_envelope(raw: Any) -> dict[str, Any]:
    """Validate and normalise the LLM response.

    The model is *supposed* to return our envelope shape, but we cannot trust
    it. We accept legacy responses (a flat field dict) too so older prompts
    don't break.
    """
    if not isinstance(raw, dict) or not raw:
        return _failed_envelope("INVALID_RESPONSE", "Model returned no JSON object.")

    # Legacy / fallback: model returned just the fields dict.
    if "fields" not in raw and "doc_type" not in raw:
        return {
            "doc_type": "UNKNOWN",
            "doc_type_confidence": 0.0,
            "quality": "GOOD" if raw else "UNREADABLE",
            "patient_name": raw.get("patient_name"),
            "fields": raw,
            "warnings": [
                "Document type was not detected; please confirm before submitting."
            ],
            "extraction_status": "OK",
        }

    doc_type = str(raw.get("doc_type", "UNKNOWN")).upper()
    if doc_type not in _VALID_DOC_TYPES:
        doc_type = "UNKNOWN"

    quality = str(raw.get("quality", "GOOD")).upper()
    if quality not in _VALID_QUALITY:
        quality = "GOOD"

    try:
        confidence = float(raw.get("doc_type_confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    fields = raw.get("fields")
    if not isinstance(fields, dict):
        fields = {}

    warnings_raw = raw.get("warnings") or []
    warnings = [str(w) for w in warnings_raw if w] if isinstance(warnings_raw, list) else []

    # If the model says it can't read the image, force quality to UNREADABLE
    # so the document-verification agent reacts correctly.
    if doc_type == "UNKNOWN" and not fields:
        quality = "UNREADABLE"

    patient_name = raw.get("patient_name")
    if patient_name is not None:
        patient_name = str(patient_name).strip() or None

    return {
        "doc_type": doc_type,
        "doc_type_confidence": confidence,
        "quality": quality,
        "patient_name": patient_name,
        "fields": fields,
        "warnings": warnings,
        "extraction_status": "OK",
    }
