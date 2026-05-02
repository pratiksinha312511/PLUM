# Architecture — Plum Claims Pipeline

> Multi-agent claims adjudication for [PlumHQ](https://www.plumhq.com/). Built for the AI Engineer assignment.

---

## 1. Goals & Non-Negotiables

The assignment defines six non-negotiable behaviours that drove every architectural choice:

| # | Behaviour | Where it lives |
|---|---|---|
| 1 | Accept a claim submission | `POST /claims` (`backend/app/main.py`) |
| 2 | Catch document problems early — *specific*, actionable messages | `IntakeAgent` + `DocumentVerificationAgent` (halt the pipeline before any decision) |
| 3 | Extract structured info from messy docs | `ExtractionAgent` (Sarvam-backed; falls back to provided JSON) |
| 4 | Produce a decision: `APPROVED` / `PARTIAL` / `REJECTED` / `MANUAL_REVIEW` | `AdjudicationAgent` (only agent allowed to set the final decision) |
| 5 | Every decision is fully explainable | `TraceRecorder` — every agent appends a structured `TraceStep` |
| 6 | Graceful degradation | `safe_run` wrapper around every agent + `degraded_components` on the output envelope |

These were treated as acceptance tests, not aspirations. Each is verified by at least one test in `tests/test_official_cases.py`.

---

## 2. The Multi-Agent Pipeline

```
┌──────────────┐
│ ClaimSubmission ──┐
└──────────────┘    │
                    ▼
        ┌────────────────────────────┐
Phase 1 │ IntakeAgent                │  member valid? policy active? min amount?
        │ DocumentVerificationAgent  │  right docs? readable?              ──┐
        │ ExtractionAgent            │  OCR/structured fields              ─┤  HALT?  ──► NEEDS_USER_ACTION
        │ CrossValidationAgent       │  same patient across docs?          ──┘
        └────────────────────────────┘
                    │ (no halt)
                    ▼
        ┌────────────────────────────┐
Phase 2 │ PolicyCoverageAgent        │  exclusions, waiting periods, pre-auth, dental split
        │ LimitsAgent                │  per-claim, annual OPD
        │ FraudDetectionAgent        │  same-day clusters, high-value, provider concentration
        └────────────────────────────┘
                    │
                    ▼
        ┌────────────────────────────┐
Phase 3 │ AdjudicationAgent          │  network discount → co-pay → final decision
        └────────────────────────────┘
                    │
                    ▼
              ClaimDecision (with full trace)
```

### Why three phases?

- **Phase 1 is gating.** If something is wrong with the *input* (wrong docs, unreadable bill, mismatched patient), no policy logic should ever run. It would be misleading to tell a user "your claim was rejected because the diagnosis is excluded" when the real problem is they uploaded the wrong file. Halting early gives a single, specific, actionable error message.
- **Phase 2 is observation.** All three agents always run (regardless of each other's findings). They write findings into the context. None of them set the final decision. This guarantees the trace surfaces *every* check that was attempted, even when an earlier reason already rules out approval.
- **Phase 3 is decision.** Only the `AdjudicationAgent` is allowed to write `ctx.decision`. The decision rules are simple, deterministic, and entirely driven by `policy_terms.json` data and Phase 2 findings.

### Why separate agents at all?

Three reasons:

1. **Single responsibility makes contracts cheap.** Each agent has one job and one promise. See `docs/COMPONENT_CONTRACTS.md`.
2. **Safe isolation of failures.** `safe_run` catches anything an agent throws, records the failure as a trace step, drops confidence, and lets the pipeline keep going. Test `TC011` proves a failed `FraudDetectionAgent` does not crash the request — the system still produces an approval (with reduced confidence and a `degraded` flag).
3. **Easy to extend.** Adding a new check (e.g. "duplicate-bill detection") is one new agent class registered in `pipeline.py`. No existing code changes.

---

## 3. Determinism vs. LLMs

This is the single most important design choice in the system.

**Adjudication is 100% deterministic.** No LLM is ever asked "should this claim be approved?". Every rupee that gets paid is the result of a function applied to data from `policy_terms.json` and structured fields. This is non-negotiable for an insurer:

- It is auditable. The trace is reproducible.
- It is testable. Test cases assert exact rupee amounts.
- It is explainable. Every reason maps to a clause in the policy file.

**LLMs are used for one job: turning messy documents into structured data.** That is the `ExtractionAgent`'s role. When the test fixtures provide `content` directly we skip the LLM call. When raw OCR text is supplied (real upload path) we hand it to `SarvamClient.chat_json` with a strict JSON schema prompt. If Sarvam times out or returns malformed JSON, we degrade gracefully and the rest of the pipeline runs on whatever fields *are* available.

This is the bright line: **LLMs read documents. Code makes decisions.**

---

## 4. Explainability — the `TraceStep` contract

Every agent appends one or more `TraceStep`s:

```python
TraceStep(
    agent: str,          # which agent
    status: str,         # "passed" | "failed" | "skipped" | "error" | "info"
    summary: str,        # one-line human-readable
    details: dict,       # structured: thresholds, matched keywords, durations
    duration_ms: float,
    timestamp: datetime,
)
```

The trace is included in every `ClaimDecision` response. The frontend renders it as a vertical timeline so an operations engineer can see exactly:

- Which agent ran, in what order
- What it checked (e.g. "Initial waiting period", "Per-claim limit ₹5,000 vs claimed ₹7,500")
- What passed, what failed, what errored
- For rejections: the precise clause and the financial calculation breakdown
- For halts: the exact user-facing message that was generated

This is the "Observability" criterion (20% of the rubric) and where most of the design effort went.

---

## 5. Failure Handling

Every agent is wrapped in `safe_run(agent, ctx, critical=...)`:

```python
async def safe_run(agent, ctx, *, critical: bool = False) -> None:
    try:
        await agent.run(ctx)
    except Exception as exc:
        ctx.degraded_components.append(agent.name)
        ctx.confidence = max(0.4, ctx.confidence - 0.2)
        ctx.trace.add(agent.name, "error", f"{agent.name} failed and was skipped: {exc}", ...)
        if critical:
            ctx.halt = UserActionRequired(code="PIPELINE_ERROR", ...)
```

- **Non-critical agents** (Phase 2): logged, skipped, confidence reduced. Pipeline continues.
- **Critical agents** (Phase 1): the failure is converted into a user-facing halt rather than a 500.
- **Per-decision flags** (`degraded`, `degraded_components`, `confidence_score`) make this state visible to both API consumers and the UI.

`TC011` injects a deliberate failure into the `FraudDetectionAgent`. The pipeline produces an `APPROVED` decision with `degraded=True`, `confidence_score < 0.85`, and a note recommending manual review.

---

## 6. Data-Driven Policy

`policy_terms.json` is the single source of truth. It is loaded once at startup (`@lru_cache`'d in `app/core/policy.py`) and exposed through a typed `Policy` object. Every policy decision — sub-limits, waiting periods, exclusions, pre-auth thresholds, network hospitals, fraud thresholds, document requirements per category — is read from this file at runtime.

This means:

- A new claim category, a new exclusion, a different per-claim cap → JSON edit, no code change.
- Tests can be parameterised with policy variants by patching the loader.
- For multi-tenant production, this becomes a per-tenant lookup with no logic change.

There is exactly one place in the codebase where a policy detail is *interpreted* in code: in `LimitsAgent`, the per-claim cap is restricted to `ClaimCategory.CONSULTATION` because dental, vision, pharmacy and diagnostic have their own (higher) sub-limits that would otherwise be invalidated by a 5,000 cap. This interpretation is documented at the call site.

---

## 7. Component Contracts (summary)

The full contracts are in [`COMPONENT_CONTRACTS.md`](./COMPONENT_CONTRACTS.md). One-line summary per agent:

| Agent | Input | Output (writes to context) | Halts? |
|---|---|---|---|
| `IntakeAgent` | submission, policy | `ctx.member` | yes (member not found, policy inactive) |
| `DocumentVerificationAgent` | submission, policy | trace only | yes (wrong/unreadable docs) |
| `ExtractionAgent` | documents | `ctx.extracted` (per-doc), `ctx.detected_diagnoses` | no |
| `CrossValidationAgent` | extracted, documents | trace only | yes (patient mismatch) |
| `PolicyCoverageAgent` | extracted, member, policy | `ctx.rejection_reasons`, `ctx.line_items` (dental split), `ctx.notes` | no |
| `LimitsAgent` | submission, policy | `ctx.rejection_reasons`, `ctx.notes` | no |
| `FraudDetectionAgent` | submission, policy | `ctx.fraud_signals` | no |
| `AdjudicationAgent` | everything above | `ctx.decision`, `ctx.approved_amount`, `ctx.calculation`, `ctx.notes` | no (it *is* the terminal step) |

---

## 8. What I Considered and Rejected

- **A single LLM call doing the whole adjudication.** Rejected. Non-deterministic, unauditable, would make the ops team's job harder, not easier. Insurers cannot defend a payout that was made because a model "felt" the claim was valid.
- **A graph framework (LangGraph / LlamaIndex Workflows).** Rejected for this scope. The pipeline is linear with one halt condition; a 50-line orchestrator is cleaner than a dependency.
- **Storing extracted documents as a separate Postgres table.** Out of scope for the assignment. The in-memory `store.py` has the exact same interface a SQLAlchemy repository would expose, so the swap is mechanical.
- **A queue between agents (Celery / Redis Streams).** Rejected at this load. A single claim decision is sub-100ms (the LLM call dominates only for the OCR path). Below ~1k requests/sec, in-process orchestration is the correct choice.
- **Hard-coded retry on Sarvam timeouts.** Rejected — `safe_run` already covers this and the assignment explicitly asks for graceful degradation rather than retry storms. A retry policy would be the next addition (with circuit breaker) when we move off in-memory state.

---

## 9. Limitations & 10× Plan

What this system does well today:

- All 12 official test cases pass.
- Every decision carries a complete trace.
- Every component is independently testable.
- Failures don't crash the pipeline.

What I would address at 10× the current load (≥100k claims/day):

| Concern | Today | At 10× |
|---|---|---|
| **State** | In-memory dict | Postgres for `ClaimDecision`s; trace as JSONB; member/policy in a versioned config service |
| **OCR throughput** | Synchronous Sarvam call inside the request | Document upload triggers an async OCR job (S3 + worker queue); `POST /claims` references the resulting structured payload |
| **Idempotency** | None | Client-supplied `Idempotency-Key`; same key returns the same `claim_id` |
| **Policy hot-reload** | Process restart | Config service with versioned policies; every `ClaimDecision` records the policy version it was adjudicated against |
| **Per-member ledgers** | Annual category usage not tracked (sub-limits are advisory) | Per-member-per-category ledger updated atomically on every approval; LimitsAgent enforces remaining balance |
| **Fraud detection** | Rules-based, six signals | Add a per-member behavioural model trained on historical decisions; surface the score to ops, never to the auto-decision path |
| **Observability** | Structured trace returned in the response | Trace also published to OpenTelemetry; per-agent latency histograms; alerts on `degraded > 1%` rolling window |
| **Concurrency** | FastAPI/uvicorn workers | Same, plus Sarvam call concurrency limited per worker; backpressure on the OCR queue |
| **Multi-tenancy** | Single policy file | `Policy` keyed by tenant; `policy_terms.json` becomes the seed for one tenant |
| **Auditability** | Trace returned to caller | Trace also written append-only to an event log; every override recorded with operator id |

The architecture is intentionally shaped so each of these is an additive change — the agents themselves don't need to know about queues, ledgers, or tenancy.

---

## 10. Trade-offs I Made Deliberately

- **No file uploads in this build.** The test cases provide structured `content` directly. The `ExtractionAgent` keeps the LLM path live for the real upload integration but the UI submits structured documents. This was the right cut to make: it kept the eval objective (no model variability in the test results) and let me focus on the parts the rubric weighs heavily — system design, observability, and graceful degradation.
- **In-memory store.** Persistence is one file's worth of work and would have added test friction without adding evaluation signal.
- **No real OCR.** Same reason. The Sarvam client is wired for the moment a real image-upload endpoint is added (a future `extract_from_image` method on `SarvamClient`).
- **Frontend uses the editorial-serif design system end-to-end.** Aesthetic consistency was a deliberate choice — Plum's brand (warmth, trust, considered communication) maps far more naturally onto a serif/editorial language than onto a generic SaaS dashboard. Every page uses the same tokens defined in `frontend/app/globals.css`.

---
