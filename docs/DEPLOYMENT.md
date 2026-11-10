# Deployment Guide

This project deploys on a modern three-part stack with CI/CD baked in. Everything
below works as provided; swap in your own accounts/URLs.

## Targets

| Layer | Provider | Files |
|-------|----------|-------|
| Frontend | **Vercel** | `frontend/vercel.json` |
| Backend | **Railway** (or Render) | `backend/Dockerfile` + `render.yaml` |
| Postgres | **Neon** (serverless) | set `DATABASE_URL` |
| Cache | **Redis** (Railway plugin / Render add-on) | set `REDIS_URL` |
| CI/CD | **GitHub Actions** | `.github/workflows/ci.yml` |

## Backend

### Option A — Render (recommended, blueprint)
1. Push the repo (Render auto-detects `render.yaml`).
2. Set the secret `GROQ_API_KEY` in the Render dashboard (and optional
   `DATABASE_URL`, `REDIS_URL`).
3. A 1 GB persistent disk is mounted at `/app/data/persist`, so **both** the
   Chroma vectors (`/app/data/persist/chroma_db`) and the SQLite relational
   store (`/app/data/persist/clauseguard.sqlite3`) survive restarts and
   redeploys. The read-only knowledge base stays at `/app/data/fair_clauses.json`
   inside the image, outside the mount, so a fresh volume never hides it.
4. After the first deploy, open the Render Shell once and run
   `python scripts/seed_demo.py` to populate the guest and demo workspaces.
5. Done — health check at `/health`.

### Option B — Docker anywhere
```bash
docker build -t clauseguard-api backend
docker run -p 8000:8000 --env-file backend/.env \
  -v clauseguard_data:/app/data/persist \
  -e CHROMA_DIR=/app/data/persist/chroma_db \
  -e DATABASE_URL=sqlite:////app/data/persist/clauseguard.sqlite3 \
  clauseguard-api
```
Or with the whole stack (adds Redis):
```bash
docker compose up --build
```

### Railway
Railway autodiscovers the Dockerfile in `backend/`. Add `GROQ_API_KEY` as a
variable and a volume mounted at `/app/data/persist`.

### Environment variables
See `backend/.env.example`. Minimum viable production set:
```
GROQ_API_KEY=gsk_....
REDIS_URL=redis://...
DATABASE_URL=postgres://...@neon...
FIREBASE_CREDENTIALS=./firebase-service-account.json   # optional, for auth
```

## Frontend (Vercel)
1. Import the repo, root directory = `frontend`.
2. `vercel.json` is auto-detected (build = `npm run build`, output = `build`).
3. Set the env var `REACT_APP_API_URL` to your deployed backend URL.

Local dev: `.env.local` in `frontend/` overrides the default
`http://localhost:8000`.

## Backup

The relational store (SQLAlchemy) defaults to
`backend/data/clauseguard.sqlite3` locally; the Render blueprint sets
`DATABASE_URL` to `/app/data/persist/clauseguard.sqlite3` on the mounted disk.
Mount the container volume so it survives restarts, and back it up
(railway volume snapshots, nightly `scp`, or a cron job to S3/Drive). In
production you can instead set `DATABASE_URL` to Neon Postgres, which is
managed and replicated for you. ChromaDB vectors can always be re-seeded from
`data/fair_clauses.json` (`POST /fair-clauses/seed`).

Before switching to Postgres (or after restoring a backup), idempotently migrate
legacy pre-Phase-2 rows with `python -m scripts.migrate_store`.

> **Auth note** — generate a strong `JWT_SECRET` (e.g.
> `python -c "import secrets; print(secrets.token_hex(32))"`) and set
> `REQUIRE_AUTH=true` once a frontend login flow exists.

## CI/CD (GitHub Actions)
`.github/workflows/ci.yml` runs on every push/PR:
- **Backend** — pip install + `py_compile` on all modules + **`pytest -q`**
  (55 backend tests across unit/API/auth, LLM calls stubbed) + import smoke test.
- **Frontend** — `npm ci`, production build, `tsc --noEmit`, `npm test`.

Add a repository secret `GROQ_API_KEY` if you want the smoke test to exercise the
LLM (otherwise it still passes — the tests stub every live call).

## Monitoring & alerting
Recommended free tier:
- **Uptime** — UptimeRobot / Render native uptime checks against `/health`.
- **Errors** — Sentry (frontend + backend) or log drain to Papertrail.
- **Usage** — Posthog (usage funnels) / GA4 (marketing).
- **Alerting** — a failure webhook to Slack or email from the uptime provider.

## Autoscaling notes
The pipeline is CPU-light but LLM-bound; keep `--workers` modest (2) so you don't
burn the free-tier Groq rate limit. Move to `--workers 4` on a paid plan.
Chroma is single-node — for scale-out, implement `app/stores/store_protocol.py`
with a Qdrant/Pgvector backend (API-compatible for `add/query/delete`) and swap
the one-store wiring in `app/db.py`. No call sites need to change.