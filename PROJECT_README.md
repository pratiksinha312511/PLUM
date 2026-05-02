# Plum Claims — Health Insurance Claims Processing System

> Multi-agent AI pipeline that automates health insurance claim adjudication for [PlumHQ](https://www.plumhq.com/).

This is the implementation of the AI Engineer assignment. It accepts a claim with member details and uploaded documents, runs them through a deterministic multi-agent pipeline (with LLM-assisted document understanding via Sarvam AI), and produces an explainable decision: `APPROVED`, `PARTIAL`, `REJECTED`, or `MANUAL_REVIEW`.

## Repository Layout

```
plum-claims/
├── backend/                # FastAPI service + multi-agent pipeline
│   ├── app/
│   │   ├── agents/         # The 8 pipeline agents
│   │   ├── core/           # Policy loader, config, trace
│   │   ├── models/         # Pydantic schemas
│   │   ├── services/       # Sarvam LLM client, in-memory store
│   │   └── main.py         # FastAPI entrypoint
│   ├── tests/              # Pytest suite (12 official test cases + units)
│   └── requirements.txt
├── frontend/               # Next.js 14 (App Router) + Tailwind + Editorial Serif UI
│   ├── app/
│   ├── components/
│   └── package.json
├── docs/
│   ├── ARCHITECTURE.md
│   ├── COMPONENT_CONTRACTS.md
│   └── EVAL_REPORT.md
├── policy_terms.json       # Canonical policy (read at runtime)
├── test_cases.json         # 12 official test scenarios
├── assignment.md           # Original brief
└── sample_documents_guide.md
```

## Quick Start (Local)

### Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # SARVAM_API_KEY already pre-filled per assignment
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend
```powershell
cd frontend
npm install
npm run dev
```

UI: http://localhost:3000

### Run the eval (all 12 test cases)
```powershell
cd backend
pytest tests/test_official_cases.py -v
python -m app.scripts.run_eval > ../docs/EVAL_REPORT.md
```

## Highlights

- **Multi-agent architecture** — 8 agents, each with a single responsibility and a strict input/output contract.
- **Deterministic adjudication** — All policy logic is data-driven from `policy_terms.json`. The LLM is only used for document content understanding.
- **Full trace per claim** — Every check, input, output, and timing is recorded; surfaced in the UI as an audit trail.
- **Graceful degradation** — Each agent is wrapped in a circuit-breaker. A failed agent is recorded, the pipeline continues, and confidence is reduced.
- **Editorial UI** — Serif-driven design system (Playfair Display + Source Sans 3 + IBM Plex Mono) inspired by Plum's brand register: warm, considered, and trustworthy.

See `docs/ARCHITECTURE.md` for the full design rationale.
