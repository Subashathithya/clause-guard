# ClauseGuard REST API — Full Documentation

Base URL (local): `http://localhost:8000` — production: your Railway/Render URL.
Unless noted, requests and responses are `application/json`.

> Live interactive docs: `GET /docs` (Swagger UI) once the server is running.

---

## Quick reference

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Service + RAG status |
| POST | `/analyze` | Run the 4-agent pipeline on pasted text (≥50 chars) |
| POST | `/upload` | Run the pipeline on an uploaded PDF/TXT/MD (≥50 chars) |
| POST | `/chat` | RAG Q&A over indexed contracts |
| POST | `/compare` | Per-category risk matrix across 2–5 contracts |
| POST | `/drift` | Term drift detection between 2 contract versions |
| GET | `/contracts` | List your indexed contracts (owner-scoped; guests see anonymous runs) |
| GET | `/contracts/{id}` | Fetch a stored analysis |
| DELETE | `/contracts/{id}` | Delete a contract + its vectors + relational rows |
| POST | `/auth/register` | Create an account (email + password) |
| POST | `/auth/login` | Login → JWT Bearer token |
| GET | `/auth/me` | Current user profile + monthly quota (Bearer token) |
| GET | `/fair-clauses` | Fair-clause library stats + samples |
| POST | `/fair-clauses/seed` | (Re)seed the fair-clause library |
| GET | `/history` | Recent analysis history (relational store) |
| GET | `/stats` | Usage/analysis stats (relational store) |
| DELETE | `/analyses/{id}` | Delete a history row + its vectors |
| POST | `/test-api-key` | Verify the Groq API key |

---

## Health

```
GET /health
```
```json
{
  "status": "API is running",
  "version": "2.0.0",
  "model": "openai/gpt-oss-120b",
  "pipeline": ["Extractor", "Comparator", "Ranker", "Negotiator"],
  "rag": { "documents_indexed": 0, "fair_clauses": 197, "vector_store": "chromadb" }
}
```

## Authentication

```
POST /auth/register   Body: { "email", "password" (≥8), "full_name"? }  → 201 { "access_token", "token_type", "user" }
POST /auth/login      Body: { "email", "password" }                     → 200 { "access_token", "token_type", "user" }
GET  /auth/me         Header: Authorization: Bearer <token>             → 200 user profile + quota
```

- Passwords are bcrypt-hashed; email login is case-insensitive.
- `user` includes `quota: { monthly_limit, used, remaining }`.
- Guest mode: no token ⇒ requests are treated as anonymous (per-IP quota,
  `user_id` NULL rows). Set `REQUIRE_AUTH=true` to reject anonymous calls with
  **401** instead of completing them.

## Analyze a contract

```
POST /analyze
```
Body:
```json
{
  "text": "<full contract text, ≥ 50 characters>",
  "document_name": "Gym Membership Agreement"
}
```
Validation: empty or < `MIN_TEXT_LENGTH` (default 50) returns **422**.

Response: a full `AnalysisResult` (schema below). The contract is automatically
indexed for chat, compare and drift; `document_id` is returned and the run is
persisted in the relational store (contract + clauses, owner-scoped).

> **Quota** — guests (no token) are limited to `FREE_TIER_ANALYSES_PER_MONTH`
> analyses per IP/month; authenticated users are limited per account. Responses
> include `quota_remaining`. Set `REQUIRE_AUTH=true` to force login.

## Upload a contract file

```
POST /upload   (multipart/form-data)
  file: <pdf|txt|md|docx, max 10 MB>
  document_name: <optional>
```
Text extracted from the file (PDF via pypdf; DOCX via python-docx, paragraphs +
tables) then runs the same pipeline (also ≥50 chars). Legacy `.doc` is rejected
with a 400 telling users to save as `.docx`/PDF.

## Chat (RAG Q&A)

```
POST /chat
```
```json
{
  "question": "What is the biggest risk?",
  "document_ids": ["<uuid>", "..."],
  "history": [{"role": "user", "content": "..."}]
}
```
- `document_ids` empty ⇒ search all indexed contracts.
- Response: `{ "answer", "status", "used_documents", "sources": [{text, document_id, document_name, similarity}] }`

## Compare contracts

```
POST /compare
```
```json
{ "document_ids": ["<id1>", "<id2>", "..."] }   // 2–5
```
Response: per-category average-risk matrix, fairest winner per category, and an
AI narrative.

## Policy drift detection

```
POST /drift
```
```json
{ "document_ids": ["<old_id>", "<new_id>"] }   // exactly 2, oldest first
```
Response: `overall_delta`, `overall_direction`, and per-category
`{before, after, delta, direction}`.

## Contract storage

```
GET  /contracts               → { "contracts": [{document_id, document_name, char_count, created_at, ...}] }
GET  /contracts/{id}          → stored AnalysisResult
DELETE /contracts/{id}        → { "status", "deleted" }
```

## Fair-clause library

```
GET  /fair-clauses?limit=5
```
```json
{
  "version": "2.0",
  "count": 197,
  "indexed": 197,
  "by_category": { "Payment": 22, "Warranty": 31, "Other": 55, "..." }
  ,
  "samples_by_category": { "Payment": ["...", "..."], "..." }
}
```
```
POST /fair-clauses/seed?force=true   → { "status", "indexed" }
```

## History & stats (relational)

```
GET  /history?limit=50    → { "count", "analyses": [{document_id, document_name, status, overall_risk, source, total_clauses, red_count, yellow_count, green_count, created_at, ...}] }
GET  /stats               → { "total_contracts", "contracts_this_month", "total_clauses", "red_clauses", "yellow_clauses", "green_clauses", "analysis_credits_this_month", "scope" }
DELETE /analyses/{id}     → { "status", "deleted" }
```

Both `/history` and `/stats` are owner-scoped (your records only).

## Diagnostics

```
POST /test-api-key   → { "status", "message", "api_key_valid" }
```

---

## AnalysisResult schema

```jsonc
{
  "document_id": "uuid",
  "document_name": "string",
  "total_clauses": 3,
  "status": "SUCCESS | PARTIAL_SUCCESS | NO_CLAUSES | EXTRACTOR_ERROR",
  "source": "paste | upload",
  "agent_trace": [ {"agent": "Extractor", "clauses": 3, "ms": 2405} ],
  "risk_summary": {
    "red_count": 1, "yellow_count": 1, "green_count": 1,
    "overall_risk": "SAFE|MODERATE|HIGH",
    "average_risk_score": 61.3,
    "total_financial_exposure_inr": 12000
  },
  "summary": {
    "total_analyzed": 3, "red_flags": 1, "warnings": 1, "safe": 1,
    "recommendation": "…", "top_priorities": ["…"]
  },
  "clauses": [{
    "clause_id": "clause_1",
    "category": "Payment | Auto-Renewal | Liability | Data Privacy | Dispute | Warranty | Other",
    "text": "…original wording…",
    "risk_level": "red|yellow|green",
    "risk_score": 85,
    "risk_percentage": 85,
    "explanation": "plain-English why",
    "confidence": 0.95,
    "comparison": {
      "standard_match": "match|worse|better|unknown",
      "similarity": 0.77,
      "reference_clause": "…fair reference…",
      "reference_category": "…",
      "notes": "…"
    },
    "financial_impact": "Up to ₹12,000 in renewal overcharges",
    "financial_impact_inr": 12000,
    "negotiation_needed": true,
    "suggested_counter_clause": "…rewritten fair clause…",
    "talking_points": ["…", "…", "…"],
    "success_probability": 70,
    "reasoning": "Why this counter-clause is likely to be accepted"
  }]
}
```

### Risk mapping (server-side)
| Fair-clause similarity | Risk color | Risk score band |
|------------------------|------------|-----------------|
| > 85%                  | Green      | < 25%           |
| 70–85%                 | Yellow     | 40–70%          |
| < 70%                  | Red        | > 75%           |

---

## Error responses
- `400` — invalid input (e.g. `<2` documents for compare, not exactly 2 for drift; unsupported upload type / unparseable file)
- `404` — document not found
- `413` — upload too large (max `MAX_UPLOAD_MB`, default 10 MB)
- `422` — text too short (< `MIN_TEXT_LENGTH`, default 50) or malformed JSON
- `500` — pipeline / LLM failure (with detail)

All errors follow FastAPI's standard `{"detail": "message"}`.