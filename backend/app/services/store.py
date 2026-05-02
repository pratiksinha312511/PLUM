"""Claim decision store.

Default backend is SQLite (file at ``$DATABASE_URL`` or ``./claims.db``)
so decisions survive process restarts on Render. The interface is the
same one a Postgres adapter would expose; swap via ``DATABASE_URL``.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.models.schemas import ClaimDecision


_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _db_path() -> Path:
    url = get_settings().database_url
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "", 1)
    else:
        # Fallback for any non-SQLite DSN — write next to the working dir.
        path = "./claims.db"
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def init() -> None:
    """Create the schema. Idempotent. Called on FastAPI startup."""
    global _conn
    with _lock:
        if _conn is not None:
            return
        _conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                claim_id     TEXT PRIMARY KEY,
                member_id    TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                payload      TEXT NOT NULL
            )
            """
        )
        _conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_decisions_member ON decisions(member_id)"
        )
        _conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at DESC)"
        )
        _conn.commit()


def _ensure() -> sqlite3.Connection:
    if _conn is None:
        init()
    assert _conn is not None
    return _conn


def save(decision: ClaimDecision) -> None:
    conn = _ensure()
    payload = decision.model_dump_json()
    with _lock:
        conn.execute(
            "INSERT OR REPLACE INTO decisions (claim_id, member_id, created_at, payload) "
            "VALUES (?, ?, ?, ?)",
            (
                decision.claim_id,
                decision.submission.member_id,
                decision.created_at.isoformat(),
                payload,
            ),
        )
        conn.commit()


def _row_to_decision(row: tuple) -> ClaimDecision:
    return ClaimDecision.model_validate(json.loads(row[0]))


def get(claim_id: str) -> Optional[ClaimDecision]:
    conn = _ensure()
    with _lock:
        cur = conn.execute(
            "SELECT payload FROM decisions WHERE claim_id = ?", (claim_id,)
        )
        row = cur.fetchone()
    return _row_to_decision(row) if row else None


def list_all(limit: int = 200) -> list[ClaimDecision]:
    conn = _ensure()
    with _lock:
        cur = conn.execute(
            "SELECT payload FROM decisions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
    return [_row_to_decision(r) for r in rows]


def list_for_member(member_id: str, limit: int = 200) -> list[ClaimDecision]:
    conn = _ensure()
    with _lock:
        cur = conn.execute(
            "SELECT payload FROM decisions WHERE member_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (member_id, limit),
        )
        rows = cur.fetchall()
    return [_row_to_decision(r) for r in rows]


def reset() -> None:
    """Test helper — wipe all rows. Not exposed via HTTP."""
    conn = _ensure()
    with _lock:
        conn.execute("DELETE FROM decisions")
        conn.commit()
