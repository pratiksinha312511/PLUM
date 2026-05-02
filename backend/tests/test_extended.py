"""Extended boundary, edge, and resilience tests.

These augment the 12 official cases in `test_official_cases.py`. They are
parameterised wherever possible to keep maintenance cheap.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from app.agents.base import PipelineContext
from app.agents.cross_validation import CrossValidationAgent
from app.agents.document_verification import DocumentVerificationAgent
from app.agents.fraud_detection import FraudDetectionAgent
from app.agents.intake import IntakeAgent
from app.agents.limits import LimitsAgent
from app.agents.policy_coverage import PolicyCoverageAgent
from app.core.policy import get_policy
from app.core.trace import TraceRecorder
from app.models.schemas import (
    ClaimCategory,
    ClaimHistoryItem,
    ClaimSubmission,
    Decision,
    DocumentInput,
    DocumentQuality,
    DocumentType,
    RejectionReason,
)
from app.pipeline import run_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _basic_consultation(**overrides) -> ClaimSubmission:
    base = dict(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-11-01",
        claimed_amount=1500,
        documents=[
            DocumentInput(
                file_id="P1",
                actual_type=DocumentType.PRESCRIPTION,
                content={
                    "doctor_name": "Dr. A",
                    "patient_name": "Rajesh Kumar",
                    "diagnosis": "Viral Fever",
                },
            ),
            DocumentInput(
                file_id="B1",
                actual_type=DocumentType.HOSPITAL_BILL,
                content={
                    "patient_name": "Rajesh Kumar",
                    "line_items": [{"description": "Consultation", "amount": 1500}],
                    "total": 1500,
                },
            ),
        ],
    )
    base.update(overrides)
    return ClaimSubmission.model_validate(base)


def _ctx(sub: ClaimSubmission) -> PipelineContext:
    return PipelineContext(submission=sub, policy=get_policy(), trace=TraceRecorder())


# ---------------------------------------------------------------------------
# Intake boundaries
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_intake_unknown_member_halts():
    sub = _basic_consultation(member_id="EMP_DOES_NOT_EXIST")
    ctx = _ctx(sub)
    await IntakeAgent().run(ctx)
    assert ctx.halt is not None
    assert ctx.halt.code == "MEMBER_NOT_FOUND"
    assert "EMP_DOES_NOT_EXIST" in ctx.halt.message


@pytest.mark.asyncio
async def test_intake_below_minimum_amount_halts():
    sub = _basic_consultation(claimed_amount=100)
    ctx = _ctx(sub)
    await IntakeAgent().run(ctx)
    assert ctx.halt is not None
    assert ctx.halt.code == "BELOW_MINIMUM"


@pytest.mark.asyncio
async def test_intake_invalid_date_halts():
    sub = _basic_consultation(treatment_date="not-a-date")
    ctx = _ctx(sub)
    await IntakeAgent().run(ctx)
    assert ctx.halt is not None
    assert ctx.halt.code == "BAD_DATE"


# ---------------------------------------------------------------------------
# Document verification — table-driven matrix
# ---------------------------------------------------------------------------
DOC_MATRIX = [
    # (description, docs, expect_halt, halt_code_substring)
    (
        "no documents at all",
        [],
        True,
        "WRONG_DOCUMENT_TYPE",
    ),
    (
        "only prescription, missing bill",
        [DocumentInput(file_id="X", actual_type=DocumentType.PRESCRIPTION)],
        True,
        "WRONG_DOCUMENT_TYPE",
    ),
    (
        "prescription unreadable",
        [
            DocumentInput(file_id="X", actual_type=DocumentType.PRESCRIPTION, quality=DocumentQuality.UNREADABLE),
            DocumentInput(file_id="Y", actual_type=DocumentType.HOSPITAL_BILL),
        ],
        True,
        "UNREADABLE_DOCUMENT",
    ),
    (
        "happy path",
        [
            DocumentInput(file_id="X", actual_type=DocumentType.PRESCRIPTION),
            DocumentInput(file_id="Y", actual_type=DocumentType.HOSPITAL_BILL),
        ],
        False,
        None,
    ),
    (
        "extra optional doc is fine",
        [
            DocumentInput(file_id="X", actual_type=DocumentType.PRESCRIPTION),
            DocumentInput(file_id="Y", actual_type=DocumentType.HOSPITAL_BILL),
            DocumentInput(file_id="Z", actual_type=DocumentType.LAB_REPORT),
        ],
        False,
        None,
    ),
]


@pytest.mark.parametrize("desc,docs,expect_halt,code", DOC_MATRIX, ids=[m[0] for m in DOC_MATRIX])
@pytest.mark.asyncio
async def test_document_verification_matrix(desc, docs, expect_halt, code):
    sub = _basic_consultation(documents=docs)
    ctx = _ctx(sub)
    await DocumentVerificationAgent().run(ctx)
    if expect_halt:
        assert ctx.halt is not None, desc
        assert code in ctx.halt.code, desc
    else:
        assert ctx.halt is None, desc


# ---------------------------------------------------------------------------
# Per-claim limit boundary
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "amount,expect_reason",
    [
        (4999, None),
        (5000, None),
        (5001, RejectionReason.PER_CLAIM_EXCEEDED),
        (10000, RejectionReason.PER_CLAIM_EXCEEDED),
    ],
)
@pytest.mark.asyncio
async def test_per_claim_limit_boundary(amount, expect_reason):
    sub = _basic_consultation(claimed_amount=amount)
    ctx = _ctx(sub)
    await LimitsAgent().run(ctx)
    if expect_reason:
        assert expect_reason in ctx.rejection_reasons
    else:
        assert RejectionReason.PER_CLAIM_EXCEEDED not in ctx.rejection_reasons


# ---------------------------------------------------------------------------
# Annual OPD limit
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_annual_opd_limit_exceeded():
    sub = _basic_consultation(ytd_claims_amount=49500, claimed_amount=2000)
    ctx = _ctx(sub)
    await LimitsAgent().run(ctx)
    assert RejectionReason.ANNUAL_LIMIT_EXCEEDED in ctx.rejection_reasons


@pytest.mark.asyncio
async def test_annual_opd_limit_just_within():
    sub = _basic_consultation(ytd_claims_amount=48500, claimed_amount=1500)
    ctx = _ctx(sub)
    await LimitsAgent().run(ctx)
    assert not ctx.rejection_reasons


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cross_validation_normalised_match_passes():
    """Same name, different whitespace and case — must NOT halt."""
    docs = [
        DocumentInput(
            file_id="A",
            actual_type=DocumentType.PRESCRIPTION,
            patient_name_on_doc="rajesh  kumar",
        ),
        DocumentInput(
            file_id="B",
            actual_type=DocumentType.HOSPITAL_BILL,
            patient_name_on_doc="Rajesh Kumar",
        ),
    ]
    sub = _basic_consultation(documents=docs)
    ctx = _ctx(sub)
    await CrossValidationAgent().run(ctx)
    assert ctx.halt is None


@pytest.mark.asyncio
async def test_cross_validation_distinct_names_halts():
    docs = [
        DocumentInput(file_id="A", actual_type=DocumentType.PRESCRIPTION, patient_name_on_doc="Alice"),
        DocumentInput(file_id="B", actual_type=DocumentType.HOSPITAL_BILL, patient_name_on_doc="Bob"),
    ]
    sub = _basic_consultation(documents=docs)
    ctx = _ctx(sub)
    await CrossValidationAgent().run(ctx)
    assert ctx.halt is not None
    assert ctx.halt.code == "PATIENT_NAME_MISMATCH"


# ---------------------------------------------------------------------------
# Waiting period boundary
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "treatment_date,expect_reject",
    [
        ("2024-11-29", True),   # day 89 — still in waiting period
        ("2024-11-30", False),  # day 90 — eligible
        ("2025-01-15", False),  # well after
    ],
)
@pytest.mark.asyncio
async def test_diabetes_waiting_period_boundary(treatment_date, expect_reject):
    sub = _basic_consultation(
        member_id="EMP005",  # joined 2024-09-01
        treatment_date=treatment_date,
        claimed_amount=2000,
        documents=[
            DocumentInput(
                file_id="P",
                actual_type=DocumentType.PRESCRIPTION,
                content={"diagnosis": "Type 2 Diabetes Mellitus", "medicines": ["Metformin"]},
            ),
            DocumentInput(
                file_id="B",
                actual_type=DocumentType.HOSPITAL_BILL,
                content={
                    "patient_name": "Vikram Joshi",
                    "line_items": [{"description": "Consultation", "amount": 2000}],
                    "total": 2000,
                },
            ),
        ],
    )
    dec = await run_pipeline(sub)
    if expect_reject:
        assert dec.decision == Decision.REJECTED
        assert RejectionReason.WAITING_PERIOD in dec.rejection_reasons
    else:
        assert dec.decision in (Decision.APPROVED, Decision.PARTIAL, Decision.MANUAL_REVIEW)


# ---------------------------------------------------------------------------
# Pre-auth reference (TC007 with the new field)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mri_with_pre_auth_reference_passes():
    sub = ClaimSubmission.model_validate({
        "member_id": "EMP007",
        "policy_id": "PLUM_GHI_2024",
        "claim_category": "DIAGNOSTIC",
        "treatment_date": "2024-11-02",
        "claimed_amount": 15000,
        "pre_auth_reference": "PA-2024-9988",
        "documents": [
            {"file_id": "F1", "actual_type": "PRESCRIPTION",
             "content": {"diagnosis": "Suspected Lumbar Disc Herniation",
                         "tests_ordered": ["MRI Lumbar Spine"]}},
            {"file_id": "F2", "actual_type": "LAB_REPORT",
             "content": {"test_name": "MRI Lumbar Spine"}},
            {"file_id": "F3", "actual_type": "HOSPITAL_BILL",
             "content": {"line_items": [{"description": "MRI Lumbar Spine", "amount": 15000}],
                         "total": 15000}},
        ],
    })
    dec = await run_pipeline(sub)
    assert RejectionReason.PRE_AUTH_MISSING not in dec.rejection_reasons


# ---------------------------------------------------------------------------
# Network discount + co-pay arithmetic
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_network_discount_applied_before_copay():
    """Apollo + 4500 base must yield 3240 (discount-then-copay), not 3060 (copay-then-discount)."""
    sub = _basic_consultation(
        member_id="EMP010",
        hospital_name="Apollo Hospitals",
        claimed_amount=4500,
    )
    dec = await run_pipeline(sub)
    assert dec.decision == Decision.APPROVED
    assert dec.approved_amount == 3240
    assert dec.calculation is not None
    # Network discount must be > 0 and applied first
    assert dec.calculation.network_discount_amount == 900
    assert dec.calculation.copay_amount == 360


@pytest.mark.asyncio
async def test_no_network_no_discount():
    """Same claim at a non-network hospital — only co-pay applies."""
    sub = _basic_consultation(
        hospital_name="Random Local Clinic",
        claimed_amount=4500,
    )
    dec = await run_pipeline(sub)
    assert dec.decision == Decision.APPROVED
    assert dec.calculation is not None
    assert dec.calculation.network_discount_amount == 0
    # 10% copay on 4500 → 4050 approved
    assert dec.approved_amount == 4050


# ---------------------------------------------------------------------------
# Fraud signal boundaries
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fraud_two_same_day_claims_within_limit():
    """Limit is 2 same-day claims. With 1 prior + this one = 2, must NOT trigger MANUAL_REVIEW for that signal."""
    sub = _basic_consultation(
        claims_history=[
            ClaimHistoryItem(claim_id="X1", date="2024-11-01", amount=500, provider="A"),
        ],
    )
    ctx = _ctx(sub)
    await FraudDetectionAgent().run(ctx)
    assert not any("same-day" in s.lower() or "2024-11-01" in s for s in ctx.fraud_signals)


@pytest.mark.asyncio
async def test_fraud_three_same_day_claims_triggers():
    sub = _basic_consultation(
        claims_history=[
            ClaimHistoryItem(claim_id="X1", date="2024-11-01", amount=500, provider="A"),
            ClaimHistoryItem(claim_id="X2", date="2024-11-01", amount=600, provider="B"),
        ],
    )
    ctx = _ctx(sub)
    await FraudDetectionAgent().run(ctx)
    assert ctx.fraud_signals  # at least one


@pytest.mark.asyncio
async def test_high_value_routes_to_manual_review():
    sub = _basic_consultation(claimed_amount=4900)  # below per-claim cap so it can adjudicate
    # bypass per-claim cap by using a category with higher sub-limit
    sub2 = ClaimSubmission.model_validate({
        **sub.model_dump(),
        "claim_category": "DIAGNOSTIC",
        "claimed_amount": 26000,
        "documents": [
            {"file_id": "P", "actual_type": "PRESCRIPTION",
             "content": {"diagnosis": "Routine screening", "tests_ordered": ["Full body checkup"]}},
            {"file_id": "L", "actual_type": "LAB_REPORT", "content": {"test_name": "Lipid panel"}},
            {"file_id": "B", "actual_type": "HOSPITAL_BILL",
             "content": {"line_items": [{"description": "Full body checkup", "amount": 26000}],
                         "total": 26000}},
        ],
    })
    dec = await run_pipeline(sub2)
    assert dec.decision == Decision.MANUAL_REVIEW
    assert any("high-value" in s.lower() for s in dec.fraud_signals)


# ---------------------------------------------------------------------------
# Coverage exclusion — word boundary safety
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lumbar_disc_herniation_does_not_match_hernia_waiting_period():
    """Regression: 'herniation' must not trigger the 'hernia' waiting-period rule."""
    sub = ClaimSubmission.model_validate({
        "member_id": "EMP001",
        "policy_id": "PLUM_GHI_2024",
        "claim_category": "DIAGNOSTIC",
        "treatment_date": "2024-11-01",
        "claimed_amount": 9000,
        "documents": [
            {"file_id": "P", "actual_type": "PRESCRIPTION",
             "content": {"diagnosis": "Lumbar disc herniation",
                         "tests_ordered": ["X-Ray spine"]}},
            {"file_id": "L", "actual_type": "LAB_REPORT", "content": {"test_name": "X-Ray spine"}},
            {"file_id": "B", "actual_type": "HOSPITAL_BILL",
             "content": {"line_items": [{"description": "X-Ray spine", "amount": 9000}],
                         "total": 9000}},
        ],
    })
    dec = await run_pipeline(sub)
    assert RejectionReason.WAITING_PERIOD not in dec.rejection_reasons


# ---------------------------------------------------------------------------
# Resilience — every Phase-2 agent failing in turn
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_does_not_crash_on_blank_documents():
    """Hostile input — empty content blobs."""
    sub = _basic_consultation(
        documents=[
            DocumentInput(file_id="P", actual_type=DocumentType.PRESCRIPTION, content={}),
            DocumentInput(file_id="B", actual_type=DocumentType.HOSPITAL_BILL, content={}),
        ],
    )
    dec = await run_pipeline(sub)
    assert dec.decision is not None  # never crashes


@pytest.mark.asyncio
async def test_concurrent_submissions_do_not_corrupt_store():
    """Submit 20 claims in parallel; all must round-trip through the store."""
    from app.services import store
    store.init()
    subs = [_basic_consultation() for _ in range(20)]
    decisions = await asyncio.gather(*(run_pipeline(s) for s in subs))
    for d in decisions:
        store.save(d)
    saved_ids = {d.claim_id for d in decisions}
    listed_ids = {d.claim_id for d in store.list_all()}
    assert saved_ids.issubset(listed_ids)
