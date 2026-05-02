"""Thin async client for the Sarvam AI chat completions endpoint.

The Sarvam API is OpenAI-compatible. We use it for document content
normalization & extraction (text + vision) — never for adjudication.
All policy logic is deterministic.

Two surface methods:
  * ``chat_json``    — text-only extraction from raw OCR strings.
  * ``vision_json``  — vision extraction from an uploaded image (bytes
                       or base64). Uses the configured ``SARVAM_VISION_MODEL``.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.core.config import get_settings


class SarvamError(RuntimeError):
    pass


class SarvamClient:
    def __init__(self) -> None:
        s = get_settings()
        self.api_key = s.sarvam_api_key
        self.base_url = s.sarvam_base_url.rstrip("/")
        self.model = s.sarvam_model
        self.vision_model = s.sarvam_vision_model
        self.timeout = s.llm_timeout_seconds
        self.enabled = bool(s.llm_enabled and self.api_key)

    # ------------------------------------------------------------------
    # Text-only chat → JSON object
    # ------------------------------------------------------------------
    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.enabled:
            raise SarvamError("LLM disabled")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        return await self._post_chat(payload)

    # ------------------------------------------------------------------
    # Vision → JSON object
    # ------------------------------------------------------------------
    async def vision_json(
        self,
        system: str,
        user_text: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """Send an image to the Sarvam vision model and parse the JSON reply.

        Uses the OpenAI-compatible multi-modal message shape that Sarvam
        documents for its vision endpoint:

            messages = [
              {"role": "system", "content": <prompt>},
              {"role": "user", "content": [
                  {"type": "text", "text": <instructions>},
                  {"type": "image_url",
                   "image_url": {"url": "data:image/jpeg;base64,..."}},
              ]},
            ]
        """
        if not self.enabled:
            raise SarvamError("LLM disabled")

        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64}"

        payload = {
            "model": self.vision_model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0.1,
            # Sarvam vision sometimes ignores response_format; we still ask.
            "response_format": {"type": "json_object"},
        }
        return await self._post_chat(payload, allow_text_fallback=True)

    # ------------------------------------------------------------------
    # Internal: POST to /v1/chat/completions with JSON-extraction fallback
    # ------------------------------------------------------------------
    async def _post_chat(
        self, payload: dict[str, Any], *, allow_text_fallback: bool = False
    ) -> dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError) as exc:
            raise SarvamError(str(exc)) from exc

        # Direct JSON parse first
        try:
            return json.loads(content)
        except (TypeError, json.JSONDecodeError):
            if not allow_text_fallback:
                raise SarvamError("Reply was not valid JSON")
        # Vision fallback: yank the first {...} block out of the prose.
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise SarvamError(f"Vision JSON extraction failed: {exc}") from exc
        raise SarvamError("Vision reply contained no JSON object")
