"""Thin async client for the Sarvam AI chat completions endpoint.

The Sarvam API is OpenAI-compatible. We use it for document content
normalization & extraction (when raw text is provided) — never for
adjudication. All policy logic is deterministic.
"""
from __future__ import annotations

import json
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
        self.timeout = s.llm_timeout_seconds
        self.enabled = bool(s.llm_enabled and self.api_key)

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        """Call the chat endpoint and parse a JSON object from the reply."""
        if not self.enabled:
            raise SarvamError("LLM disabled")

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            raise SarvamError(str(exc)) from exc
