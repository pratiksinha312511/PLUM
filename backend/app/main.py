"""FastAPI entrypoint.

Serves both the JSON API (under ``/api/*``) and the statically-exported
Next.js frontend (mounted at ``/``) so the whole app runs from one Render
service / one URL.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.extraction import extract_image_via_llm
from app.core.policy import get_policy
from app.models.schemas import ClaimDecision, ClaimSubmission, DocumentType
from app.pipeline import run_pipeline
from app.services import store

app = FastAPI(
    title="Plum Claims API",
    description="Multi-agent health insurance claims processing pipeline.",
    version="1.2.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    store.init()


# ---------------------------------------------------------------------------
# JSON API – mounted under /api so the static frontend can own /
# ---------------------------------------------------------------------------
api = APIRouter(prefix="/api")


@api.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@api.get("/policy")
async def policy() -> dict:
    """Return the active policy (used by the UI to render forms / requirements)."""
    return get_policy().raw


@api.post("/claims", response_model=ClaimDecision)
async def submit_claim(submission: ClaimSubmission) -> ClaimDecision:
    decision = await run_pipeline(submission)
    store.save(decision)
    return decision


@api.get("/claims", response_model=list[ClaimDecision])
async def list_claims() -> list[ClaimDecision]:
    return store.list_all()


@api.get("/claims/{claim_id}", response_model=ClaimDecision)
async def get_claim(claim_id: str) -> ClaimDecision:
    found = store.get(claim_id)
    if not found:
        raise HTTPException(status_code=404, detail="Claim not found")
    return found


@api.get("/members/{member_id}/claims", response_model=list[ClaimDecision])
async def member_claims(member_id: str) -> list[ClaimDecision]:
    return store.list_for_member(member_id)


# ---------------------------------------------------------------------------
# Document upload + Sarvam-vision extraction
# ---------------------------------------------------------------------------
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@api.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    actual_type: str | None = Form(None),
) -> dict:
    """Accept an image / PDF of a medical document, classify + extract via
    Sarvam vision, and return a fully-populated payload that drops straight
    into ``ClaimSubmission.documents[]``.

    The user does not need to tell us the document type; the model decides.
    If the user *does* override (form field ``actual_type``) we honour it.
    """
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type {file.content_type!r}. "
            f"Allowed: {sorted(_ALLOWED_MIME)}.",
        )
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 8 MB).")

    mime = file.content_type or "image/jpeg"
    envelope = await extract_image_via_llm(raw, mime_type=mime)

    # User override wins over model classification.
    if actual_type:
        try:
            chosen_type = DocumentType(actual_type.upper()).value
            user_overrode = chosen_type != envelope["doc_type"]
        except ValueError:
            chosen_type = envelope["doc_type"]
            user_overrode = False
    else:
        chosen_type = envelope["doc_type"]
        user_overrode = False

    needs_review = (
        envelope["extraction_status"] != "OK"
        or envelope["quality"] != "GOOD"
        or envelope["doc_type_confidence"] < 0.7
        or chosen_type == "UNKNOWN"
    )

    return {
        "file_id": f"F{uuid.uuid4().hex[:6].upper()}",
        "file_name": file.filename,
        "actual_type": chosen_type,
        "actual_type_confidence": envelope["doc_type_confidence"],
        "actual_type_overridden": user_overrode,
        "quality": envelope["quality"],
        "patient_name_on_doc": envelope["patient_name"],
        "content": envelope["fields"],
        "warnings": envelope["warnings"],
        "extraction_status": envelope["extraction_status"],
        "needs_review": needs_review,
    }


app.include_router(api)


# ---------------------------------------------------------------------------
# Static frontend (Next.js export) – mounted last so /api/* takes precedence.
# ---------------------------------------------------------------------------
# Resolution order:
#   1. $FRONTEND_DIST  (set on Render)
#   2. ../frontend/out (local dev once `next build` has been run)
_FRONTEND_DIR = Path(
    os.getenv("FRONTEND_DIST")
    or (Path(__file__).resolve().parents[2] / "frontend" / "out")
)

if _FRONTEND_DIR.exists():
    # html=True makes StaticFiles serve index.html for directory requests
    # (e.g. /submit/ -> /submit/index.html), which is what `next export`
    # produces for app-router routes.
    app.mount("/_next", StaticFiles(directory=_FRONTEND_DIR / "_next"), name="_next")
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
else:
    @app.get("/")
    async def _root_no_frontend() -> dict:
        return {
            "status": "ok",
            "message": (
                "Plum Claims API is running. The static frontend was not found at "
                f"{_FRONTEND_DIR}. Set FRONTEND_DIST or build the frontend with "
                "`npm run build` before starting the server."
            ),
            "docs": "/api/docs",
        }
