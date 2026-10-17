# 🛡️ ClauseGuard — AI Contract Risk Analyser

A production-ready, AI-powered contract analyser. Paste a contract or upload a PDF
and a **4-agent LLM pipeline** extracts every clause, compares it against **197
fair industry-standard references via RAG**, scores risk, quantifies financial
exposure, and drafts negotiation counter-clauses with success probability.

Built to improve consumer protection and financial literacy — understand any
contract before you sign it.

---

## ✨ Features

| Area | What you get |
|------|--------------|
| **4-agent pipeline** | Extractor → Comparator (RAG vs fair clauses) → Ranker (risk + ₹ impact) → Negotiator (counter-clauses + success %) |
| **Clause analysis** | 🔴🟡🟢 risk levels, plain-English explanations, risk score 0–100, industry-standard similarity, confidence score |
| **Negotiation pack** | Rewritten fair clause, talking points, success probability + **why it likely succeeds** |
| **RAG chat** | Ask anything about your contracts — answers cite the exact clauses retrieved from the vector store |
| **Compare** | Side-by-side risk matrix across 2–5 contracts, per category, with the fairest pick |
| **Policy drift** | Feed old vs new versions — see which terms got better or worse |
| **Uploads** | PDF / TXT / Markdown / DOCX upload with text extraction |
| **Vector store** | ChromaDB (MiniLM embeddings + 197 fair-clause references) |
| **Data store** | SQLAlchemy relational store — SQLite in dev, Postgres in prod (user accounts, owner-scoped contract history, chat log, per-IP quota) |
| **Auth** | JWT + bcrypt (register/login), guest mode by default (`REQUIRE_AUTH=false`) |
| **Consumer app (React SPA)** | Landing page, auth flows, dashboard, analyse/progress view T&C checker, contract workspace (overview · sections · review list · connections · chat), compare & drift, insights, notifications, settings — plain-English developer-safe UI, no jargon, honest empty states |

### 7 clause categories
1. 💳 Payment · 2. 🔁 Auto-Renewal · 3. ⚠️ Liability · 4. 🔒 Data Privacy ·
5. ⚖️ Dispute · 6. 🛠️ Warranty · 7. 📄 Other

---

## 🧱 Architecture

```
React SPA (Vercel)
      │  REST + JSON
      ▼
FastAPI (Railway / Render / Docker)
  └─ app/
     ├─ main.py            → app factory + router registration
     ├─ api/routes/        → health · auth · analysis · chat · compare · contracts · knowledge · history
     ├─ agents/            → extractor · comparator · ranker · negotiator + orchestrator
     ├─ core/security.py   → bcrypt password hashing + JWT auth dependencies
     ├─ database.py        → SQLAlchemy engine/session (SQLite dev, Postgres prod)
     ├─ models/            → User · Contract · Clause · ChatMessage · UsageCounter
     ├─ services/          → persistence + quota + owner-scoping logic
     ├─ stores/            → Store protocol + ChromaStore (RAG backend seam)
     ├─ db.py              → store facade (backwards-compatible)
     ├─ llm.py             → Groq wrapper (openai/gpt-oss-120b)
     └─ settings.py        → central env-based config
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

---

## 🚀 Quickstart (local)

### 1. Backend
```bash
cd backend
# optional: python -m venv venv && ./venv/Scripts/activate   (Windows)
pip install -r requirements.txt
# create .env from the example:
#   GROQ_API_KEY=gsk_...
#   PRIMARY_MODEL=openai/gpt-oss-120b
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8011
```
First startup downloads the ~80 MB MiniLM ONNX embedding model once, then seeds
the 197 fair clauses automatically. The relational store (SQLAlchemy) creates
its tables at `data/clauseguard.sqlite3` on startup — set `DATABASE_URL` to a
PostgreSQL URL for cloud deployments.

### 2. Frontend
```bash
cd frontend
npm install
npm start          # http://localhost:3000
```
The SPA talks to the backend on `http://localhost:8011` by default (see
`frontend/src/api.ts` and `frontend/.env.local`); the local backend is started on
port 8011 in the examples below.

### 3. Run tests
```bash
cd backend
python -m pytest -q               # 35 unit + API tests (LLM calls stubbed)

cd ../frontend
CI=true npx react-scripts test --watchAll=false   # 5 routing/auth smoke tests
npx tsc --noEmit && npm run build # typecheck + production build
```

### 4. Evaluate accuracy
```bash
cd backend
python evaluate_system.py --limit 10           # quick run
python evaluate_system.py                      # full labelled set
python experiments/run_experiments.py          # 70-case WITH-RAG baseline
python experiments/run_experiments.py --ablate-rag   # ablation (no RAG reference)
```
Reports: `backend/data/eval_report.json`, `backend/experiments/report_latest.json`.

> Without a GROQ_API_KEY the backend still boots but pipeline calls fail —
> get a free key at console.groq.com.

---

## 📚 Docs
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system design, DB schema, agent prompts
- [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) — full REST reference
- [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) — test plan + results
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — Vercel + Railway/Render, Docker, CI/CD, monitoring
- [`docs/EVALUATION.md`](docs/EVALUATION.md) — accuracy methodology + research-paper outline
- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) — measured classification results (WITH-RAG baseline; ablation pending)
- [`docs/BUSINESS_MODEL.md`](docs/BUSINESS_MODEL.md) — freemium, ₹500/mo premium, roadmap

---

## 💰 Business model (freemium)
- **Free tier** — 5 analyses/month, basic clause analysis
- **Premium ₹500/month** — unlimited analyses, negotiation packs, compare, drift,
  multi-document RAG chat, file uploads, history
See [`docs/BUSINESS_MODEL.md`](docs/BUSINESS_MODEL.md).

---

## 📄 License
MIT (this project). The fair-clause library is provided for research and consumer
education; it is **not** legal advice.