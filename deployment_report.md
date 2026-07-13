# Deployment Report — Enterprise Conversational AI Platform

**Date:** 2026-07-14

## Canonical services
| Service | Entrypoint | Port | Notes |
|---|---|---|---|
| Backend | `uvicorn backend.main:app` | 8000 | FastAPI. This is the only backend now referenced by Docker, docker-compose, and the frontend's default `API_BASE_URL`. |
| Frontend | `next start` (after `next build`) | 3000 | Next.js 16 / React 19, calls backend via `NEXT_PUBLIC_API_URL` / `FASTAPI_URL` (defaults to `http://127.0.0.1:8000`). |

## What changed this session
- **`Dockerfile.backend`** — rewritten to build a venv from the single root `requirements.txt`, copy only `backend/`, `lib/`, and `rule_labelled.csv`, and run `uvicorn backend.main:app --host 0.0.0.0 --port 8000`. Health check now does `curl -f http://localhost:8000/`. Previously it built and ran a dead Flask app (`scripts/backend_server.py`) on port 5000 whose dependencies (`flask`, `flask-cors`) weren't even declared — that image would have failed to build in CI/CD.
- **`docker-compose.yml`** — backend service now exposes/health-checks port 8000, and the frontend's `NEXT_PUBLIC_API_URL` build arg points at `http://backend:8000` to match.
- **`requirements.txt`** — de-duplicated; `backend/requirements.txt` (a near-identical copy) was removed. One source of truth.

## Environment variables
| Var | Used by | Default | Purpose |
|---|---|---|---|
| `CORS_ORIGINS` | `backend/main.py` | `*` | Comma-separated allowed origins for the FastAPI CORS middleware. Set this explicitly in production. |
| `NEXT_PUBLIC_API_URL` / `FASTAPI_URL` | `app/api/chat/route.ts`, `lib/query-processor.ts` | `http://127.0.0.1:8000` | Where the frontend/API route reaches the FastAPI backend. |

## Health checks
- Backend: `GET /` → `{"status":"healthy"}`. Wired into both the Dockerfile `HEALTHCHECK` and `docker-compose.yml`.
- No dedicated frontend health endpoint exists; `docker-compose.yml`'s frontend service depends on the backend's health check via `depends_on: condition: service_healthy`, which is reasonable for a single-backend setup.

## Verified production startup (this session)
- `uvicorn backend.main:app --host 0.0.0.0 --port 8000` starts cleanly, engine loads the CSV and initializes with no errors, in a plain `venv` (not yet validated inside the actual Docker container in this sandbox, since Docker itself isn't available in this sandboxed environment — only the equivalent Python venv + uvicorn process was exercised directly). **Recommend running an actual `docker build -f Dockerfile.backend .` and `docker-compose up` once in an environment with Docker available, as a final pre-release check**, since the Dockerfile was corrected but not built end-to-end here.
- `next build` succeeds and produces a deployable `.next` output; `next start` was not separately smoke-tested in this session but relies on the same build artifact that already compiled successfully.

## Runbook / docs
- `RUNBOOK.md` and `DEPLOYMENT.md` exist; not modified this session. **Recommend a follow-up pass to confirm they reference port 8000 / the FastAPI backend** and not the now-removed Flask service, since those docs were written against the same stale assumption the Dockerfile had.

## Outstanding deployment risks
1. Dockerfile fix was validated by static review + running the equivalent commands outside Docker, not by an actual `docker build`/`docker run` in this session (no Docker daemon available in this sandbox). Treat as high-confidence but not fully proven until run once in a Docker-capable environment.
2. `CORS_ORIGINS` defaults to `*` — fine for local/dev, should be locked down for a real production deployment.
3. No secrets/environment file (`.env.example`) was found describing required production env vars beyond what's inferred from code — worth adding one for onboarding clarity.
