"""Thin async client for the OCR.space `parse/image` endpoint.

Why this exists: Sarvam's vision endpoint returns 403 from several cloud
egress IPs (Render included), which blocked our auto-extraction flow.
OCR.space is a free, IP-agnostic OCR service that gives us raw text; we
then hand that text to Sarvam's text LLM for classification + structured
field extraction.

Docs: https://ocr.space/ocrapi
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings


class OcrSpaceError(RuntimeError):
    pass


class OcrSpaceClient:
    def __init__(self) -> None:
        s = get_settings()
        self.api_key = s.ocr_space_api_key
        self.url = s.ocr_space_url
        self.engine = s.ocr_space_engine
        self.timeout = s.ocr_space_timeout_seconds
        self.enabled = bool(self.api_key)

    async def parse_image(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> str:
        """Upload a single image/PDF and return concatenated parsed text.

        Raises OcrSpaceError on transport errors, non-200 responses, or
        when the API itself reports a failure (`IsErroredOnProcessing`).
        """
        if not self.enabled:
            raise OcrSpaceError("OCR.space disabled (no API key)")

        # OCR.space infers a filename extension from the upload name; pick
        # something sensible from the MIME type so it doesn't reject us.
        ext = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "application/pdf": "pdf",
        }.get(mime_type.lower(), "jpg")
        files = {"file": (f"upload.{ext}", image_bytes, mime_type)}
        data = {
            "apikey": self.api_key,
            "OCREngine": str(self.engine),
            "isOverlayRequired": "false",
            "scale": "true",
            "detectOrientation": "true",
            "language": "eng",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.url, data=data, files=files)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as exc:
            raise OcrSpaceError(str(exc)) from exc
        except ValueError as exc:  # JSON decode
            raise OcrSpaceError(f"Invalid OCR.space response: {exc}") from exc

        if payload.get("IsErroredOnProcessing"):
            err = payload.get("ErrorMessage") or payload.get("ErrorDetails") or "unknown"
            if isinstance(err, list):
                err = "; ".join(str(e) for e in err)
            raise OcrSpaceError(f"OCR.space failed: {err}")

        results = payload.get("ParsedResults") or []
        chunks = [r.get("ParsedText", "") for r in results if isinstance(r, dict)]
        text = "\n".join(c for c in chunks if c).strip()
        if not text:
            raise OcrSpaceError("OCR.space returned no text")
        return text
