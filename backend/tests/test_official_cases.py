"""Run all 12 official test cases and assert expected behaviour.

Each case asserts the headline outcome (decision + key reason / amount).
The `notes` field of test cases describing required user-facing behaviour
is verified by checking that the relevant trace entries / messages exist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.schemas import ClaimSubmission, Decision, RejectionReason
from app.pipeline import run_pipeline

CASES_FILE = Path(__file__).resolve().parents[2] / "test_cases.json"
CASES = json.loads(CASES_FILE.read_text(encoding="utf-8"))["test_cases"]
CASES_BY_ID = {c["case_id"]: c for c in CASES}


async def _run(case_id: str):
    case = CASES_BY_ID[case_id]
    sub = ClaimSubmission.model_validate(case["input"])
    return case, await run_pipeline(sub)


@pytest.mark.asyncio
async def test_TC001_wrong_document_type():
    case, dec = await _run("TC001")
    assert dec.decision == Decision.NEEDS_USER_ACTION
    assert dec.user_action is not None
    msg = dec.user_action.message.lower()
    # Must name what was uploaded AND what is needed
    assert "prescription" in msg
    assert "hospital bill" in msg


@pytest.mark.asyncio
async def test_TC002_unreadable_document():
    _, dec = await _run("TC002")
    assert dec.decision == Decision.NEEDS_USER_ACTION
    assert dec.user_action.code == "UNREADABLE_DOCUMENT"
    assert "F004" in dec.user_action.affected_documents
    # Pipeline did NOT proceed to a rejection
    assert not dec.rejection_reasons


@pytest.mark.asyncio
async def test_TC003_patient_mismatch():
    _, dec = await _run("TC003")
    assert dec.decision == Decision.NEEDS_USER_ACTION
    assert dec.user_action.code == "PATIENT_NAME_MISMATCH"
    assert "Rajesh Kumar" in dec.user_action.message
    assert "Arjun Mehta" in dec.user_action.message


@pytest.mark.asyncio
async def test_TC004_clean_consultation_full_approval():
    _, dec = await _run("TC004")
    assert dec.decision == Decision.APPROVED
    assert dec.approved_amount == 1350  # 1500 - 10% copay
    assert dec.confidence_score >= 0.85


@pytest.mark.asyncio
async def test_TC005_waiting_period_diabetes():
    _, dec = await _run("TC005")
    assert dec.decision == Decision.REJECTED
    assert RejectionReason.WAITING_PERIOD in dec.rejection_reasons
    assert "eligible from" in dec.notes.lower()


@pytest.mark.asyncio
async def test_TC006_dental_partial():
    _, dec = await _run("TC006")
    assert dec.decision == Decision.PARTIAL
    assert dec.approved_amount == 8000
    statuses = {li.description: li.status for li in dec.line_items}
    assert statuses["Root Canal Treatment"] == "APPROVED"
    assert statuses["Teeth Whitening"] == "REJECTED"


@pytest.mark.asyncio
async def test_TC007_mri_no_pre_auth():
    _, dec = await _run("TC007")
    assert dec.decision == Decision.REJECTED
    assert RejectionReason.PRE_AUTH_MISSING in dec.rejection_reasons
    assert "pre-auth" in dec.notes.lower()


@pytest.mark.asyncio
async def test_TC008_per_claim_exceeded():
    _, dec = await _run("TC008")
    assert dec.decision == Decision.REJECTED
    assert RejectionReason.PER_CLAIM_EXCEEDED in dec.rejection_reasons
    assert "5,000" in dec.notes
    assert "7,500" in dec.notes


@pytest.mark.asyncio
async def test_TC009_fraud_same_day():
    _, dec = await _run("TC009")
    assert dec.decision == Decision.MANUAL_REVIEW
    assert dec.fraud_signals  # at least one signal present
    assert any("same-day" in s.lower() or "2024-10-30" in s for s in dec.fraud_signals)


@pytest.mark.asyncio
async def test_TC010_network_discount_then_copay():
    _, dec = await _run("TC010")
    assert dec.decision == Decision.APPROVED
    assert dec.approved_amount == 3240
    assert dec.calculation is not None
    assert dec.calculation.network_discount_amount == 900
    assert dec.calculation.copay_amount == 360


@pytest.mark.asyncio
async def test_TC011_component_failure_graceful():
    _, dec = await _run("TC011")
    # Must not crash — must return a decision
    assert dec.decision is not None
    assert dec.degraded is True
    assert "FraudDetectionAgent" in dec.degraded_components
    assert dec.confidence_score < 0.85


@pytest.mark.asyncio
async def test_TC012_excluded_treatment():
    _, dec = await _run("TC012")
    assert dec.decision == Decision.REJECTED
    assert RejectionReason.EXCLUDED_CONDITION in dec.rejection_reasons
    assert dec.confidence_score >= 0.90
