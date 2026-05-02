# Deploying to Render.com

This repo ships a `render.yaml` blueprint that provisions both services.

## One-click (Blueprint)

1. Push the repo to GitHub.
2. In Render: **New → Blueprint → connect repo → apply**.
3. After the first deploy completes, open the **plum-claims-api** service →
   **Environment** → set `SARVAM_API_KEY` to your key (kept out of source).
4. Hit *Manual Deploy → Deploy latest commit* on both services to pick up the
   new env var, then visit the **plum-claims-ui** URL.

## Architecture on Render

```
Internet ─→ plum-claims-ui (Next.js, port $PORT)
              │
              │  /api/* rewrite (NEXT_PUBLIC_API_URL)
              ▼
         plum-claims-api (FastAPI / uvicorn)
              │
              ▼
   /var/data/claims.db  (1 GB persistent disk)
              │
              ▼
       Sarvam AI (chat + vision)
```

* **Persistence**: SQLite file lives on a 1 GB disk mounted at `/var/data`,
  so claim history survives restarts and redeploys.
* **Vision uploads**: `POST /upload` accepts JPEG/PNG/WEBP/PDF (≤ 8 MB) and
  calls Sarvam's `sarvam-vision` model to extract structured fields, returning
  a payload the UI drops straight into the form's documents array.
* **Frontend → backend wiring**: Render auto-injects the backend's public host
  into the frontend service via `fromService` in `render.yaml`. No hard-coded
  URLs.

## Free-tier caveats

* Both free web services sleep after ~15 minutes of inactivity. The first
  request after a sleep takes ~30 s while the container cold-starts.
* The 1 GB disk is included on free tier.

## Manual (without blueprint)

If you prefer to wire services by hand:

### Backend
* New → Web Service → Python
* Root: `backend`
* Build: `pip install -r requirements.txt`
* Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* Disk: 1 GB at `/var/data`
* Env: `SARVAM_API_KEY`, `DATABASE_URL=sqlite:////var/data/claims.db`,
  `SARVAM_VISION_MODEL=sarvam-vision`, `LLM_ENABLED=true`

### Frontend
* New → Web Service → Node
* Root: `frontend`
* Build: `npm install && npm run build`
* Start: `npm start`
* Env: `NEXT_PUBLIC_API_URL=https://<backend-name>.onrender.com`

## Local development parity

```powershell
# Backend
cd backend
.\.venv\Scripts\Activate.ps1
$env:SARVAM_API_KEY = "sk_..."
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
```
