"""Trace recorder — accumulates structured steps as the pipeline runs."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

from app.models.schemas import TraceStep


class TraceRecorder:
    def __init__(self) -> None:
        self.steps: list[TraceStep] = []

    def add(
        self,
        agent: str,
        status: str,
        summary: str,
        details: dict[str, Any] | None = None,
        duration_ms: float = 0,
    ) -> None:
        self.steps.append(
            TraceStep(
                agent=agent,
                status=status,
                summary=summary,
                details=details or {},
                duration_ms=duration_ms,
            )
        )

    @contextmanager
    def time(self, agent: str):
        start = time.perf_counter()
        try:
            yield self
        finally:
            self._last_duration = (time.perf_counter() - start) * 1000

    @property
    def last_duration_ms(self) -> float:
        return getattr(self, "_last_duration", 0.0)
