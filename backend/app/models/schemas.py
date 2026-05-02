"""Pydantic schemas for the claims pipeline.

These types form the strict contract between agents. Every agent consumes
and emits a `ClaimContext` (mutated through copy_with helpers) so that the
final trace is reconstructible from the model alone.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    PHARMACY_BILL = "PHARMACY_BILL"
    LAB_REPORT = "LAB_REPORT"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    DENTAL_REPORT = "DENTAL_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    UNKNOWN = "UNKNOWN"


class DocumentQuality(str, Enum):
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"
    UNREADABLE = "UNREADABLE"


class Decision(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NEEDS_USER_ACTION = "NEEDS_USER_ACTION"  # blocked before adjudication


class RejectionReason(str, Enum):
    WAITING_PERIOD = "WAITING_PERIOD"
    PRE_AUTH_MISSING = "PRE_AUTH_MISSING"
    PER_CLAIM_EXCEEDED = "PER_CLAIM_EXCEEDED"
    SUB_LIMIT_EXCEEDED = "SUB_LIMIT_EXCEEDED"
    ANNUAL_LIMIT_EXCEEDED = "ANNUAL_LIMIT_EXCEEDED"
    EXCLUDED_CONDITION = "EXCLUDED_CONDITION"
    EXCLUDED_PROCEDURE = "EXCLUDED_PROCEDURE"
    BELOW_MINIMUM_CLAIM = "BELOW_MINIMUM_CLAIM"
    SUBMISSION_DEADLINE_PASSED = "SUBMISSION_DEADLINE_PASSED"
    MEMBER_NOT_COVERED = "MEMBER_NOT_COVERED"
    DOCUMENT_PATIENT_MISMATCH = "DOCUMENT_PATIENT_MISMATCH"
    POLICY_INACTIVE = "POLICY_INACTIVE"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
class DocumentInput(BaseModel):
    file_id: str
    file_name: Optional[str] = None
    actual_type: DocumentType = DocumentType.UNKNOWN
    quality: DocumentQuality = DocumentQuality.GOOD
    patient_name_on_doc: Optional[str] = None
    content: dict[str, Any] = Field(default_factory=dict)


class ClaimHistoryItem(BaseModel):
    claim_id: str
    date: str
    amount: float
    provider: Optional[str] = None


class ClaimSubmission(BaseModel):
    member_id: str
    policy_id: str
    claim_category: ClaimCategory
    treatment_date: str
    claimed_amount: float
    hospital_name: Optional[str] = None
    ytd_claims_amount: float = 0
    claims_history: list[ClaimHistoryItem] = Field(default_factory=list)
    documents: list[DocumentInput] = Field(default_factory=list)
    pre_auth_reference: Optional[str] = None
    simulate_component_failure: bool = False


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------
class TraceStep(BaseModel):
    agent: str
    status: str  # "passed" | "failed" | "skipped" | "error" | "info"
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Per-line approval breakdown
# ---------------------------------------------------------------------------
class LineItemDecision(BaseModel):
    description: str
    claimed_amount: float
    approved_amount: float
    status: str  # "APPROVED" | "REJECTED"
    reason: Optional[str] = None


class CalculationBreakdown(BaseModel):
    base_amount: float
    network_discount_percent: float = 0
    network_discount_amount: float = 0
    after_network_discount: float = 0
    copay_percent: float = 0
    copay_amount: float = 0
    sub_limit_applied: Optional[float] = None
    final_approved: float = 0
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# User-facing message (when the pipeline halts before adjudication)
# ---------------------------------------------------------------------------
class UserActionRequired(BaseModel):
    code: str
    title: str
    message: str
    affected_documents: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Final decision envelope
# ---------------------------------------------------------------------------
class ClaimDecision(BaseModel):
    claim_id: str
    decision: Optional[Decision]
    approved_amount: float = 0
    rejection_reasons: list[RejectionReason] = Field(default_factory=list)
    line_items: list[LineItemDecision] = Field(default_factory=list)
    calculation: Optional[CalculationBreakdown] = None
    confidence_score: float = 0.0
    notes: str = ""
    user_action: Optional[UserActionRequired] = None
    fraud_signals: list[str] = Field(default_factory=list)
    degraded: bool = False
    degraded_components: list[str] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    submission: ClaimSubmission
    created_at: datetime = Field(default_factory=datetime.utcnow)
