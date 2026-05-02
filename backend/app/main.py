"""FastAPI entrypoint."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.policy import get_policy
from app.models.schemas import ClaimDecision, ClaimSubmission
from app.pipeline import run_pipeline
from app.services import store

app = FastAPI(
    title="Plum Claims API",
    description="Multi-agent health insurance claims processing pipeline.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/policy")
async def policy() -> dict:
    """Return the active policy (used by the UI to render forms / requirements)."""
    return get_policy().raw


@app.post("/claims", response_model=ClaimDecision)
async def submit_claim(submission: ClaimSubmission) -> ClaimDecision:
    decision = await run_pipeline(submission)
    store.save(decision)
    return decision


@app.get("/claims", response_model=list[ClaimDecision])
async def list_claims() -> list[ClaimDecision]:
    return store.list_all()


@app.get("/claims/{claim_id}", response_model=ClaimDecision)
async def get_claim(claim_id: str) -> ClaimDecision:
    found = store.get(claim_id)
    if not found:
        raise HTTPException(status_code=404, detail="Claim not found")
    return found


@app.get("/members/{member_id}/claims", response_model=list[ClaimDecision])
async def member_claims(member_id: str) -> list[ClaimDecision]:
    return store.list_for_member(member_id)
