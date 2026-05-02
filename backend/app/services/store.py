"""In-memory store for claim decisions (sufficient for the assignment).

In production this would be a Postgres table indexed by member_id and date,
with the trace stored as JSONB for ad-hoc analysis.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from app.models.schemas import ClaimDecision

_decisions: dict[str, ClaimDecision] = {}
_by_member: dict[str, list[str]] = defaultdict(list)


def save(decision: ClaimDecision) -> None:
    _decisions[decision.claim_id] = decision
    _by_member[decision.submission.member_id].append(decision.claim_id)


def get(claim_id: str) -> Optional[ClaimDecision]:
    return _decisions.get(claim_id)


def list_all() -> list[ClaimDecision]:
    return sorted(_decisions.values(), key=lambda d: d.created_at, reverse=True)


def list_for_member(member_id: str) -> list[ClaimDecision]:
    ids = _by_member.get(member_id, [])
    return [_decisions[i] for i in ids if i in _decisions]
