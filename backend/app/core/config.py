"""Application config loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    sarvam_api_key: str = os.getenv("SARVAM_API_KEY", "")
    sarvam_base_url: str = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
    sarvam_model: str = os.getenv("SARVAM_MODEL", "sarvam-m")
    sarvam_vision_model: str = os.getenv("SARVAM_VISION_MODEL", "sarvam-vision")
    llm_enabled: bool = os.getenv("LLM_ENABLED", "true").lower() == "true"
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./claims.db")

    # OCR.space (https://ocr.space/ocrapi) — used as the primary OCR engine
    # in front of Sarvam's text LLM, since the vision endpoint is unreliable
    # from some egress IPs. Free tier: K87019029488957 has 25k calls/month.
    ocr_space_api_key: str = os.getenv("OCR_SPACE_API_KEY", "K87019029488957")
    ocr_space_url: str = os.getenv(
        "OCR_SPACE_URL", "https://api.ocr.space/parse/image"
    )
    ocr_space_engine: int = int(os.getenv("OCR_SPACE_ENGINE", "2"))
    ocr_space_timeout_seconds: float = float(
        os.getenv("OCR_SPACE_TIMEOUT_SECONDS", "45")
    )

    # Resolve policy file relative to repo root if not absolute.
    @property
    def policy_file(self) -> Path:
        raw = os.getenv("POLICY_FILE", "../policy_terms.json")
        p = Path(raw)
        if not p.is_absolute():
            # backend/app/core/config.py -> backend dir is parents[2].
            # Default value "../policy_terms.json" then resolves to repo root.
            p = (Path(__file__).resolve().parents[2] / raw).resolve()
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
