<div align="center">

# 🩺 Plum Claims

### A multi-agent AI pipeline that adjudicates health insurance claims — explainably, deterministically, and gracefully.

*Built for the [PlumHQ](https://www.plumhq.com/) AI Engineer assignment.*

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Tailwind](https://img.shields.io/badge/Tailwind-3.4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Sarvam AI](https://img.shields.io/badge/LLM-Sarvam%20AI-7C3AED)](https://www.sarvam.ai/)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)](https://render.com/)
[![Tests](https://img.shields.io/badge/test%20cases-12%2F12%20passing-22c55e)](backend/tests/test_official_cases.py)

**[🚀 Quick Start](#-quick-start)** · **[🏛 Architecture](#-architecture-at-a-glance)** · **[🧠 The Agents](#-meet-the-agents)** · **[🧪 Run the Eval](#-run-the-eval)** · **[📚 Docs](#-deep-dives)**

</div>

---

## ✨ Why this exists

> *"When an employee submits a health insurance claim, someone on our team manually reviews their documents against the policy. It's slow, inconsistent, and doesn't scale. Your job is to automate it."*

Plum processes **75,000+ claims/year** today, on a path to **10 million lives by 2030**. That math doesn't work without intelligent systems. **Plum Claims** is one — a transparent, testable pipeline that turns a member's messy upload into an auditable decision in under a second.

```
   📨 submission   ──►   🤖 8-agent pipeline   ──►   ✅ APPROVED · ⚠️ PARTIAL · ❌ REJECTED · 👀 MANUAL_REVIEW
                                                       + full reasoning trace
```

---

## 🎯 The bright line

This is the single most important design choice in the system, and it shows up everywhere:

> ### **LLMs read documents. Code makes decisions.**

No LLM is ever asked *"should this claim be approved?"*. Every rupee paid is the output of pure functions over `policy_terms.json` and structured fields. The Sarvam vision model only does what models are good at — turning a phone photo of a hospital bill into clean JSON. Everything downstream is deterministic, reproducible, and unit-testable to the rupee.

| | LLM | Code |
|---|:---:|:---:|
| OCR a wrinkled prescription | ✅ | |
| Classify a document type | ✅ | |
| Decide if a waiting period applies | | ✅ |
| Calculate co-pay & network discount | | ✅ |
| Pick `APPROVED` vs `PARTIAL` vs `REJECTED` | | ✅ |

---

## 🏛 Architecture at a glance

```
                ┌──────────────────────────────┐
                │         POST /api/claims     │
                └──────────────┬───────────────┘
                               ▼
   ╔══════════════════════════════════════════════════════════════╗
   ║                       PHASE 1 — Gating                       ║
   ║  Intake → DocVerification → Extraction → CrossValidation     ║
   ║   (any can HALT with a specific, actionable user message)    ║
   ╚════════════════════════════╤═════════════════════════════════╝
                                ▼
   ╔══════════════════════════════════════════════════════════════╗
   ║                    PHASE 2 — Observation                     ║
   ║      PolicyCoverage    Limits    FraudDetection              ║
   ║         (always run · accumulate findings · never decide)    ║
   ╚════════════════════════════╤═════════════════════════════════╝
                                ▼
   ╔══════════════════════════════════════════════════════════════╗
   ║                     PHASE 3 — Decision                       ║
   ║     AdjudicationAgent (the only agent that writes a verdict) ║
   ║       network discount → co-pay → final amount → reasoning   ║
   ╚════════════════════════════╤═════════════════════════════════╝
                                ▼
                       📦 ClaimDecision (+ trace)
```

Three phases, one promise per phase. **Gating** protects the user from misleading errors. **Observation** guarantees the trace surfaces *every* check, even after a rejection reason is found. **Decision** is the single source of truth for the verdict.

---

## 🧠 Meet the agents

Eight focused agents. Each has one job, one promise, and one place it lives.

| # | Agent | Does one thing | Can halt? |
|---|---|---|:---:|
| 1 | 🪪 `IntakeAgent` | Member exists? Policy active? Amount valid? | ✅ |
| 2 | 📄 `DocumentVerificationAgent` | Right docs for the claim type? Readable? | ✅ |
| 3 | 🔍 `ExtractionAgent` | Pull patient/diagnosis/amount from raw OCR via Sarvam | — |
| 4 | 🔗 `CrossValidationAgent` | Same patient & date across all docs? | ✅ |
| 5 | 📜 `PolicyCoverageAgent` | Exclusions, waiting periods, pre-auth, dental split | — |
| 6 | 💰 `LimitsAgent` | Per-claim and annual OPD caps | — |
| 7 | 🚩 `FraudDetectionAgent` | Same-day clusters, high-value, provider concentration | — |
| 8 | ⚖️ `AdjudicationAgent` | The math — discount → co-pay → final verdict | — |

Every agent runs inside `safe_run(...)` — if anything throws, the failure becomes a `TraceStep`, confidence drops, and the pipeline keeps moving. **Test `TC011`** deliberately blows up `FraudDetectionAgent` and the system still produces a valid (degraded, lower-confidence) `APPROVED`.

---

## 🔬 Observability — the killer feature

Every claim returns a complete vertical timeline of *what was checked, in what order, with what data, and how long it took*:

```jsonc
{
  "claim_id": "CLM-A1B2C3D4E5",
  "decision": "PARTIAL",
  "approved_amount": 3600,
  "confidence_score": 0.92,
  "trace": [
    { "agent": "IntakeAgent",              "status": "passed", "duration_ms":  0.4, "summary": "Member EMP001 verified" },
    { "agent": "DocumentVerificationAgent","status": "passed", "duration_ms":  1.1, "summary": "All required documents present" },
    { "agent": "ExtractionAgent",          "status": "passed", "duration_ms": 12.7, "summary": "Extracted 3 documents" },
    { "agent": "PolicyCoverageAgent",      "status": "passed", "duration_ms":  0.6, "summary": "No exclusions matched" },
    { "agent": "LimitsAgent",              "status": "info",   "duration_ms":  0.3, "summary": "Per-claim cap ₹5,000 vs claimed ₹4,500 — ok" },
    { "agent": "AdjudicationAgent",        "status": "passed", "duration_ms":  0.9, "summary": "20% network discount → 10% co-pay → ₹3,600" }
  ]
}
```

The frontend renders this as a vertical timeline so an ops engineer can reconstruct *any* decision in seconds. This is the 20% Observability rubric — and where most of the design effort went.

---

## 🚀 Quick start

> **Prerequisites:** Python 3.11+, Node 18+, and (optionally) a Sarvam API key. The repo ships sensible defaults — extraction degrades gracefully without an API key.

### 1️⃣ Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # SARVAM_API_KEY pre-filled per assignment
uvicorn app.main:app --reload --port 8000
```

📍 API docs → http://localhost:8000/api/docs

### 2️⃣ Frontend

```powershell
cd frontend
npm install
npm run dev
```

📍 UI → http://localhost:3000

### 3️⃣ Submit your first claim

```powershell
curl -X POST http://localhost:8000/api/claims `
  -H "Content-Type: application/json" `
  -d '@../test_cases.json'
```

…or just open the UI and click **Submit a claim**.

---

## 🧪 Run the eval

The 12 official test scenarios from `test_cases.json` — covering the happy path, every halt condition, every limit, and a deliberately-broken-agent case:

```powershell
cd backend
pytest tests/test_official_cases.py -v
python -m app.scripts.run_eval > ../docs/EVAL_REPORT.md
```

**Result: 12 / 12 passing** — see [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md) for the per-case trace, expected-vs-actual diff, and timing.

---

## 🗂 Project layout

```
plum-claims/
├── 📂 backend/                  # FastAPI + multi-agent pipeline
│   └── app/
│       ├── agents/             # 🤖 The 8 pipeline agents
│       ├── core/               # ⚙️  policy loader · config · trace recorder
│       ├── models/             # 📐 Pydantic schemas (the wire contract)
│       ├── services/           # 🔌 Sarvam client · OCR.space · store
│       ├── pipeline.py         # 🎼 The 50-line orchestrator
│       └── main.py             # 🚪 FastAPI entrypoint + /api/upload
├── 📂 frontend/                 # Next.js 14 (App Router) · Tailwind · editorial UI
│   ├── app/                    # /submit · /claims · /policy · /architecture
│   └── components/             # ClaimForm · Decision · Chrome
├── 📂 docs/
│   ├── ARCHITECTURE.md         # Why it's built this way
│   ├── COMPONENT_CONTRACTS.md  # Per-agent input/output/errors
│   ├── EVAL_REPORT.md          # 12 cases · actual vs expected
│   └── DEPLOYMENT.md           # Render blueprint walkthrough
├── 📜 policy_terms.json         # The single source of truth (no hardcoded rules)
├── 🧾 test_cases.json           # 12 official scenarios
└── 🚀 render.yaml               # One-click Render deploy
```

---

## 🎨 The UI

A deliberately *editorial* design system — Playfair Display + Source Sans 3 + IBM Plex Mono — chosen to mirror Plum's brand register: **warm, considered, trustworthy**. Most claims dashboards feel like Splunk. This one feels like *The Atlantic*.

| Page | Purpose |
|---|---|
| `/submit` | Drag & drop documents → auto-classified by Sarvam vision → adjudicated |
| `/claims` | All processed claims with their decision badge & confidence |
| `/claims/detail` | Full vertical trace timeline + financial breakdown |
| `/policy` | Read-only view of `policy_terms.json` rendered as policy document |
| `/architecture` | Live system diagram of the 3-phase pipeline |

---

## 🛡 Graceful degradation

| Failure mode | What happens |
|---|---|
| Sarvam timeout | Fall back to provided structured fields · trace records the timeout · confidence ↓ |
| Phase 2 agent throws | `safe_run` catches · agent added to `degraded_components` · pipeline continues |
| Phase 1 agent throws | Converted into a user-facing `NEEDS_USER_ACTION` halt (never a 500) |
| Malformed LLM JSON | Schema-validated · drop bad fields · keep the rest · log it on the trace |
| Wrong document uploaded | Halt **immediately** with a *specific* message: "We needed a hospital bill but received a prescription. Please upload your itemised hospital bill." |

Every degraded state is reflected on the `ClaimDecision` envelope (`degraded`, `degraded_components`, `confidence_score`) so API consumers and the UI can react.

---

## 🌐 Deployment

The repo ships a [`render.yaml`](render.yaml) blueprint — one click in Render provisions:

- 🔧 FastAPI backend with a 1 GB persistent disk for the SQLite store
- 🎨 Next.js frontend served from the same origin
- 🔁 Health checks, CORS, and env-var wiring done

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the walkthrough.

---

## 📚 Deep dives

| Doc | What you'll find |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Why three phases · why deterministic adjudication · what was rejected · the 10× plan |
| [docs/COMPONENT_CONTRACTS.md](docs/COMPONENT_CONTRACTS.md) | Every agent's I/O contract — precise enough to reimplement from |
| [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md) | All 12 official test cases with actual decisions and traces |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Render one-click deploy walkthrough |
| [assignment.md](assignment.md) | The original brief |
| [sample_documents_guide.md](sample_documents_guide.md) | Indian medical document formats & extraction guidance |

---

## 🧰 Tech stack

**Backend** — Python 3.11 · FastAPI · Pydantic v2 · httpx · pytest-asyncio · SQLite (via `store.py`)
**LLM** — Sarvam AI (`sarvam-m` for text, `sarvam-vision` for image OCR) · OCR.space as an OCR fallback
**Frontend** — Next.js 14 (App Router) · React 18 · TypeScript · Tailwind CSS
**Infra** — Render (one-click via `render.yaml`) · GitHub Actions-ready

---

## 🧭 What I'd do at 10×

A short list — the long version is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#9-limitations--10×-plan):

- **State** → Postgres for decisions, JSONB for traces, versioned policy in a config service
- **OCR throughput** → async upload → S3 → worker queue; `POST /claims` references the OCR'd payload
- **Idempotency** → client `Idempotency-Key`; same key = same `claim_id`
- **Per-member ledgers** → annual sub-limit usage tracked atomically per member-per-category
- **Fraud** → behavioural model on top of the rules; surface the score to ops, never auto-decide
- **Observability** → publish the trace to OpenTelemetry; alert on `degraded > 1%` rolling

The agent boundaries were chosen so each of these is an additive change, not a rewrite.

---

<div align="center">

**Built with care for the Plum AI Pod.**

*If you got this far — thank you. The fastest way to grok the system is to run the eval and read [`backend/app/pipeline.py`](backend/app/pipeline.py). It's 50 lines.*

</div>
