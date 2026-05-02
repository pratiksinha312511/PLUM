"""Loads and exposes the policy document. All policy logic must read from this."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from app.core.config import get_settings


class Policy:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self._members_by_id = {m["member_id"]: m for m in raw.get("members", [])}

    # ----- accessors ------------------------------------------------------
    @property
    def policy_id(self) -> str:
        return self.raw["policy_id"]

    @property
    def coverage(self) -> dict[str, Any]:
        return self.raw.get("coverage", {})

    def category(self, name: str) -> dict[str, Any]:
        return self.raw.get("opd_categories", {}).get(name.lower(), {})

    def doc_requirements(self, category: str) -> dict[str, list[str]]:
        return self.raw.get("document_requirements", {}).get(category.upper(), {"required": [], "optional": []})

    @property
    def waiting_periods(self) -> dict[str, Any]:
        return self.raw.get("waiting_periods", {})

    @property
    def exclusions(self) -> dict[str, Any]:
        return self.raw.get("exclusions", {})

    @property
    def network_hospitals(self) -> list[str]:
        return self.raw.get("network_hospitals", [])

    @property
    def submission_rules(self) -> dict[str, Any]:
        return self.raw.get("submission_rules", {})

    @property
    def fraud_thresholds(self) -> dict[str, Any]:
        return self.raw.get("fraud_thresholds", {})

    @property
    def pre_authorization(self) -> dict[str, Any]:
        return self.raw.get("pre_authorization", {})

    def member(self, member_id: str) -> Optional[dict[str, Any]]:
        return self._members_by_id.get(member_id)

    def is_active(self) -> bool:
        return self.raw.get("policy_holder", {}).get("renewal_status") == "ACTIVE"


@lru_cache
def get_policy() -> Policy:
    settings = get_settings()
    with open(settings.policy_file, "r", encoding="utf-8") as fh:
        return Policy(json.load(fh))
