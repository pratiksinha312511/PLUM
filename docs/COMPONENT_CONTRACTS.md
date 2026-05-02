# Component Contracts

Every significant component in the pipeline is described below with its **input**, **output**, **errors raised**, and **invariants**. These contracts are the *only* coupling between agents — none of them imports another agent.

---

## Schemas (the shared language)

All agents operate on a single mutable `PipelineContext` defined in `app/agents/base.py`:

```python
@dataclass
class PipelineContext:
    submission: ClaimSubmission         # the raw input (immutable in practice)
    policy: Policy                      # loaded once, read-only
    trace: TraceRecorder                # append-only

    # Findings populated as the pipeline runs
    member: dict | None
    extracted: dict[str, dict]          # file_id -> structured content
    detected_diagnoses: list[str]
    fraud_signals: list[str]
    line_items: list[LineItemDecision]
    rejection_reasons: list[RejectionReason]
    excluded_line_descriptions: list[str]

    # Final outputs (set by the AdjudicationAgent — except `halt`)
    halt: UserActionRequired | None     # set by Phase 1 to stop the pipeline
    decision: Decision | None
    approved_amount: float
    calculation: CalculationBreakdown | None
    notes: str
    confidence: float

    # Resilience
    degraded_components: list[str]
```

Every type referenced above is a `pydantic.BaseModel` in `app/models/schemas.py`. The HTTP envelope is `ClaimDecision` which wraps the relevant slice of the context.

---

## `IntakeAgent`

**Responsibility:** Validate that the *member*, *policy* and *submission window* are coherent before anything else runs.

| | |
|---|---|
| **Input** | `ctx.submission`, `ctx.policy` |
| **Reads** | `policy.is_active()`, `policy.member(id)`, `policy.submission_rules` |
| **Writes** | `ctx.member`, optionally `ctx.halt`, optionally `ctx.rejection_reasons` |
| **Halts on** | Policy inactive · Member not found · Invalid date format · Claim below `minimum_claim_amount` |
| **Errors raised** | None (all conditions are converted to halts or trace failures) |
| **Invariant** | After this runs without setting `halt`, `ctx.member` is non-null. |

---

## `DocumentVerificationAgent`

**Responsibility:** Catch document-level problems *before* extraction or any policy evaluation.

| | |
|---|---|
| **Input** | `ctx.submission.documents`, `ctx.policy.doc_requirements(category)` |
| **Writes** | Optionally `ctx.halt` |
| **Halts on** | Required document is `UNREADABLE` quality · Required document type not uploaded |
| **Halt messages** | Always name (a) the uploaded document type, (b) the required document type, (c) the affected `file_id`s. Required by TC001/TC002. |
| **Errors raised** | None |
| **Invariant** | After this runs without setting `halt`, every required document type is present and at acceptable quality. |

---

## `ExtractionAgent`

**Responsibility:** Turn raw documents into structured fields.

| | |
|---|---|
| **Input** | `ctx.submission.documents` (each carries `content` and/or raw text in the real upload path) |
| **Writes** | `ctx.extracted[file_id]` (structured dict), `ctx.detected_diagnoses`, line-item synthesis on bills missing line items |
| **External** | `SarvamClient.chat_json` for unstructured text. Skipped when `content` is already a dict. |
| **Errors raised** | `SarvamError` (caught by `safe_run` → `degraded_components += ['ExtractionAgent']`) |
| **Invariant** | Every document has an entry in `ctx.extracted`, even if empty. |

`extract_text_via_llm(text)` is exposed as a module-level helper so the upload endpoint can normalize raw OCR text without standing up a `PipelineContext`.

---

## `CrossValidationAgent`

**Responsibility:** Detect contradictions between documents (TC003: documents belong to different patients).

| | |
|---|---|
| **Input** | `ctx.extracted`, `ctx.submission.documents` |
| **Writes** | Optionally `ctx.halt` |
| **Halts on** | Distinct normalized patient names across documents |
| **Halt message** | Lists every `file_id`-to-name pair so the user can see which document is the outlier. |
| **Errors raised** | None |

---

## `PolicyCoverageAgent`

**Responsibility:** Apply the policy's coverage rules — exclusions, waiting periods, pre-auth, dental line-item splits.

| | |
|---|---|
| **Input** | `ctx.extracted`, `ctx.detected_diagnoses`, `ctx.member`, `ctx.policy` |
| **Writes** | `ctx.rejection_reasons` (additive), `ctx.notes`, `ctx.line_items` (dental split) |
| **Order of checks** | Category covered → exclusions (regex word-boundary) → specific waiting period → initial waiting period → pre-auth (high-value diagnostics) → per-line dental split. Returns early on first hard rejection so cause is unambiguous. |
| **Errors raised** | None |
| **Invariant** | Never sets `ctx.decision` — only accumulates findings for the adjudicator. |

---

## `LimitsAgent`

**Responsibility:** Enforce financial caps from the policy.

| | |
|---|---|
| **Input** | `ctx.submission.claimed_amount`, `ctx.submission.ytd_claims_amount`, `ctx.policy.coverage` |
| **Writes** | `ctx.rejection_reasons` (additive), `ctx.notes` |
| **Rules** | Per-claim cap applies to `CONSULTATION` only (other categories have their own higher sub-limits) · Annual OPD cap applies to all categories. |
| **Errors raised** | None |

---

## `FraudDetectionAgent`

**Responsibility:** Flag suspicious patterns; never reject on its own.

| | |
|---|---|
| **Input** | `ctx.submission.claims_history`, `ctx.submission.claimed_amount`, `ctx.policy.fraud_thresholds` |
| **Writes** | `ctx.fraud_signals` (list of human-readable strings) |
| **Signals** | Multiple same-day claims · High-value above auto-review threshold · Provider concentration ≥ 3 prior claims at same provider |
| **Errors raised** | None — but the simulated failure (`simulate_component_failure=True`) raises `RuntimeError` so `TC011` exercises the degraded path. |

---

## `AdjudicationAgent`

**Responsibility:** Produce the single, final `Decision` and `approved_amount`.

| | |
|---|---|
| **Input** | The full `ctx` after Phases 1 and 2. |
| **Writes** | `ctx.decision`, `ctx.approved_amount`, `ctx.calculation`, `ctx.notes`, `ctx.confidence` |
| **Decision rules** | If any `rejection_reasons` → `REJECTED` · Else if same-day-claim threshold breached or high-value signal → `MANUAL_REVIEW` · Else if any line items rejected (dental split) → `PARTIAL` · Else → `APPROVED` |
| **Math** | `base = claimed (or sum of approved line items)` → `network_discount` → `copay` → final. Network discount applied **before** co-pay (TC010). Sub-limit treated as annual category cap (advisory, not enforced per-claim). |
| **Errors raised** | None |
| **Invariant** | Always sets exactly one `Decision`. |

---

## `safe_run(agent, ctx, *, critical: bool)`

The single point of failure containment.

| | |
|---|---|
| **Input** | An `Agent`, the `ctx`, and a `critical` flag |
| **Behaviour** | Calls `await agent.run(ctx)`. On any exception: appends `agent.name` to `ctx.degraded_components`, drops `ctx.confidence` by 0.2 (floor 0.4), records an `error` trace step. If `critical=True`, sets `ctx.halt` so Phase 2/3 never run. |
| **Special case** | If `ctx.submission.simulate_component_failure` is True and the agent is `FraudDetectionAgent`, deliberately raises `RuntimeError` (TC011 fixture). |

---

## HTTP Surface (`backend/app/main.py`)

| Method | Path | Body | Response |
|---|---|---|---|
| `GET` | `/health` | — | `{"status": "ok"}` |
| `GET` | `/policy` | — | The full policy document (used by the UI for forms / requirements) |
| `POST` | `/claims` | `ClaimSubmission` | `ClaimDecision` (with full trace) |
| `GET` | `/claims` | — | `list[ClaimDecision]` newest first |
| `GET` | `/claims/{claim_id}` | — | `ClaimDecision` or 404 |
| `GET` | `/members/{member_id}/claims` | — | `list[ClaimDecision]` for that member |

CORS is permissive (`allow_origins=["*"]`) for the local dev frontend. Lock down before shipping.

---

## Stability Guarantees

- Agents do not import other agents. They only mutate `ctx` and read `policy`.
- The order of Phase 2 agents is irrelevant to correctness. They are sequenced by `pipeline.PRE_DECISION_AGENTS`/`ANALYSIS_AGENTS` lists for readability of the trace.
- Adding a new agent is a one-line registration.
- Removing an agent must be paired with checking what fields on `ctx` it was the writer of. Today the only "shared writes" are `ctx.rejection_reasons` (PolicyCoverageAgent + LimitsAgent), `ctx.notes` (almost everyone — last writer wins), and `ctx.confidence` (anyone can lower it; only `safe_run` and `AdjudicationAgent` write it).
