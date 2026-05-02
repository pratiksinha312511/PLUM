"""Targeted unit tests for the most error-prone agents."""
from __future__ import annotations

import pytest

from app.agents.base import PipelineContext
from app.agents.document_verification import DocumentVerificationAgent
from app.core.policy import get_policy
from app.core.trace import TraceRecorder
from app.models.schemas import (
    ClaimCategory,
    ClaimSubmission,
    DocumentInput,
    DocumentQuality,
    DocumentType,
)


def _ctx(documents):
    sub = ClaimSubmission(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-11-01",
        claimed_amount=1500,
        documents=documents,
    )
    return PipelineContext(submission=sub, policy=get_policy(), trace=TraceRecorder())


@pytest.mark.asyncio
async def test_doc_verification_message_names_uploaded_and_required():
    ctx = _ctx([
        DocumentInput(file_id="X1", actual_type=DocumentType.PRESCRIPTION),
        DocumentInput(file_id="X2", actual_type=DocumentType.PRESCRIPTION),
    ])
    await DocumentVerificationAgent().run(ctx)
    assert ctx.halt is not None
    msg = ctx.halt.message.lower()
    assert "prescription" in msg
    assert "hospital bill" in msg


@pytest.mark.asyncio
async def test_doc_verification_passes_when_all_present():
    ctx = _ctx([
        DocumentInput(file_id="A", actual_type=DocumentType.PRESCRIPTION, quality=DocumentQuality.GOOD),
        DocumentInput(file_id="B", actual_type=DocumentType.HOSPITAL_BILL, quality=DocumentQuality.GOOD),
    ])
    await DocumentVerificationAgent().run(ctx)
    assert ctx.halt is None
