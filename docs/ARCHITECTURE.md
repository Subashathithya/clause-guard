# Architecture

This document explains how ClauseGuard is built, why each piece exists, and how
the pieces fit together.

## 1. High-level overview

```
┌─────────────────────────────┐
│  React SPA (TypeScript)     │  Vercel
│  tabs: Analyze · Compare ·  │
│        Chat                  │
└──────────────┬──────────────┘
               │  HTTPS / JSON
┌──────────────▼──────────────┐
│  FastAPI backend (Python)   │  Railway / Render / Docker
│  app/main.py (factory)      │
│  app/agents/{extractor,      │
│   comparator, ranker,        │
│   negotiator, orchestrator}  │
│  app/api/routes/             │
│  app/database.py · models/   │
│  services/ · core/security.py│
│  stores/ · db.py (facade)    │
│  llm.py · settings.py        │
└──────────────┬──────────────┘
   ┌───────────┼───────────┐
   ▼           ▼           ▼
 ChromaDB    SQLAlchemy   Optional infra
 (vectors/   (SQLite dev, (Redis / Neon Postgres)
  RAG)       Postgres prod)
 Groq API ──────────────────────────────► (LLM inference)
```

## 2. The 4-agent pipeline

Each agent lives in its own module and is wired together by
`app/agents/orchestrator.py`.

| # | Agent | Module | Responsibility | Implementation |
|---|-------|--------|----------------|----------------|
| 1 | **Extractor** | `app/agents/extract_agent.py` | Split contract into distinct clauses, label each with 1 of 7 categories | LLM (Groq, JSON mode); category membership validated against `schemas.CLAUSE_CATEGORIES` with a `_closest_category` fallback |
| 2 | **Comparator** | `app/agents/compare_agent.py` | Compare each clause to industry-standard fair references | **ChromaDB semantic search** (`db.compare_to_standard`) over the **197-clause** library → similarity + reference text |
| 3 | **Ranker** | `app/agents/ranker_agent.py` | Risk level (red/yellow/green), 0–100 risk score, plain-English explanation, ₹ financial impact | LLM per clause (parallel) with the comparator reference injected; **deterministic similarity fallback** if the LLM fails |
| 4 | **Negotiator** | `app/agents/negotiator_agent.py` | Balanced counter-clause, talking points, success probability + reasoning | LLM per risky clause (parallel), only for non-green clauses |

Pipeline orchestration (`app.agents.orchestrator.run_orchestrator`):
1. `ExtractAgent.extract(text)` → clauses (capped at 40).
2. `CompareAgent.compare(clause)` per clause **in parallel** (pure RAG, fast).
3. `RankAgent.rank(clause, comparison)` per clause **in parallel**.
4. `NegotiateAgent.negotiate(...)` for red/yellow clauses **in parallel**.
5. Synchronise into `AnalysisResult` + deterministic `RiskSummary`.
6. One final LLM call synthesises the executive recommendation & top priorities.

Partial failures never break the pipeline: a failed agent is recorded in
`agent_flags`, status becomes `PARTIAL_SUCCESS`, and the other agents still run.

All agent latencies are recorded in `agent_trace` (visible in the UI).

### Risk mapping (from specifications)
| Fair-clause similarity | Risk color | Risk score band |
|------------------------|------------|-----------------|
| **> 85%**              | 🟢 Green   | < 25%           |
| **70–85%**             | 🟡 Yellow  | 40–70%          |
| **< 70%**              | 🔴 Red     | > 75%           |

The ranker uses this mapping as a strong prior and lets the LLM refine the final
score + explanation; the deterministic mapping is used verbatim if the LLM fails.

## 3. The 7 canonical categories

```
Payment · Auto-Renewal · Liability · Data Privacy · Dispute · Warranty · Other
```

These exact strings are the single source of truth (`schemas.CLAUSE_CATEGORIES`)
used by extraction, comparison filters, the UI emoji map, and the fair-clause
library.

## 4. Prompt design

- Every agent prompt is a **system role** (persona + constraints) plus a **user
  role** with a strict JSON schema and the words "Return ONLY JSON".
- The Extractor receives the 7 canonical categories verbatim and must reuse the
  exact strings; a fallback mapper `_closest_category` recovers near-matches.
- The Ranker always receives the Comparator's nearest fair reference, which
  grounds risk scoring and prevents hallucinated "industry standards".
- The Negotiator emits a `reasoning` field explaining why the counter-clause is
  likely to be accepted.

## 5. Data layer

### ChromaDB (store layer: `app/stores/` + `app/db.py` facade)

The vector store lives behind a swap-in seam:

| Module | Role |
|--------|------|
| `app/stores/store_protocol.py` | The `Store` interface (`index_document`, `save_analysis`, `get_analysis`, `get_documents`, `delete_document`, `retrieve_context`, `seed_fair_clauses`, `fair_clause_count`, `compare_to_standard`) |
| `app/stores/chroma_store.py` | `ChromaStore` — the ChromaDB implementation of the protocol |
| `app/db.py` | Backwards-compatible module-level facade (singleton `ChromaStore`) so existing call sites and test patches keep working unchanged |

`PersistentClient` with four collections:

| Collection | Contents |
|------------|----------|
| `clause_chunks` | Overlapping ~600-word chunks of every analysed contract (for RAG chat) |
| `documents` | One record per contract (name, char count, created_at) for listing/drift |
| `analyses` | Full cached `AnalysisResult` JSON per contract (compare/drift/chat context) |
| `fair_clauses` | 197 curated fair references (seeded from `data/fair_clauses.json`) |

Embeddings: `all-MiniLM-L6-v2` via ONNX Runtime (local, ~80 MB, downloaded once).
Retrieval is plain semantic similarity with a `where` filter on `document_id`.

`data/fair_clauses.json` v2 format:
```json
{
  "version": "2.0",
  "clauses_by_category": {
    "Payment": [ "...", "...", "..." ],
    "Warranty": [ "...", ... ]
  },
  "total": 197
}
```
Regenerate with `python scripts/build_fair_clauses.py`.

### SQLAlchemy relational store (`app/database.py` + `app/models/`)

SQLAlchemy 2.0 with a declarative `Base`. Dev default is SQLite at
`data/clauseguard.sqlite3`; production points `DATABASE_URL` at PostgreSQL
(Neon). Tables are created automatically on startup (`init_db`).

| Table | Purpose |
|-------|---------|
| `users` | Accounts: email, bcrypt-hashed password, created_at |
| `contracts` | One row per analysed contract (owner-scoped `user_id`, risk aggregates, raw text, agent trace) |
| `clauses` | One row per extracted clause incl. full risk + comparator evidence |
| `chat_messages` | Log of RAG chat turns (question, answer, retrieved sources) |
| `usage_counters` | Per-IP monthly counters for guest quota enforcement |

Owner scoping: authenticated users only see their own `contracts`; guest runs
are stored with `user_id` NULL and are visible to other guests (and migrated
legacy rows). The `GET /contracts/{id}` payload is served from the full-fidelity
Chroma cache when present, otherwise reconstructed from these rows.

Backed API endpoints: `GET /stats`, `GET /history`, `DELETE /analyses/{id}`,
`GET/DELETE /contracts/{id}`, plus all `/auth/*` routes.

Legacy migration (pre-Phase-2 SQLite tables → relational): 
`python -m scripts.migrate_store` (idempotent; legacy tables are left as-is).

### Auth (`app/core/security.py`, `app/api/routes/auth.py`)

Passwords hashed with bcrypt (12 rounds); JWT (HS256) via PyJWT. Bearer tokens
are validated by `get_current_user` (required) / `get_optional_user` (guest
mode). `REQUIRE_AUTH=false` (default) keeps the API open with per-IP quota so
the current frontend works without a login screen.

## 6. API surface (`app/main.py` + `app/api/routes/`)

All endpoints return JSON. Full reference in
[`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md). Main ones:
- `POST /analyze` — text in (≥50 chars), full 4-agent analysis out
- `POST /upload` — multipart PDF/TXT/MD/DOCX → extraction → pipeline (≥50 chars)
- `POST /chat` — RAG chat (vector search + LLM)
- `POST /compare` — per-category risk matrix over 2–5 contracts
- `POST /drift` — old-vs-new term drift detection (exactly 2 docs)
- `GET /contracts`, `GET|DELETE /contracts/{id}`
- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `GET /fair-clauses`, `POST /fair-clauses/seed`
- `GET /history`, `GET /stats`, `DELETE /analyses/{id}`
- `GET /health`, `POST /test-api-key`

Input validation: pasted/uploaded text shorter than `MIN_TEXT_LENGTH` (default
50 chars) is rejected with `422`.

## 7. Frontend (`frontend/src/App.tsx`)

Single-page app with three tabs:

- **Analyze** — paste text (with a live character counter + min-50 hint) or drop
  a file; renders metric cards (overall risk, avg score, red/yellow/green counts,
  ₹ exposure), agent-trace chips, executive summary, and per-clause cards (emoji
  risk badge, category emoji, confidence score, risk bar, explanation, comparison
  reference, counter-clause, success-probability bar, talking points, and the
  negotiation `reasoning`). An **"Analyze Another"** button resets the form.
- **Compare & Drift** — pick 2–5 indexed contracts → risk matrix; pick exactly 2 →
  drift table showing per-category deltas.
- **Ask AI** — select contracts (or all) and chat; answers cite retrieved chunks.

State lives in `App.tsx`; API calls are isolated in `src/api.ts`; shared types in
`src/types.ts`.

## 8. Security & limits

- `.gitignore` excludes `.env`, `chroma_db/`, logs, node_modules.
- No secrets are committed. LLM responses are treated as untrusted; the pipeline
  re-validates categories and clamps scores to 0–100.
- File uploads capped at 10 MB; only PDF/TXT/MD/DOCX accepted (legacy `.doc` → 400 with a conversion hint).
- Min 50 chars enforced on analyzed text (both client and server).
- CORS is wide-open for development; harden `allow_origins` in production.