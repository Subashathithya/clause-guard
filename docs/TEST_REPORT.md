# Test Report

Status of the automated test suite for the ClauseGuard backend. Every LLM call is
stubbed, and the vector store + relational database run against throwaway temp
paths, so the suite is deterministic, hermetic and runs without an API key.

## Run it

```bash
cd backend
python -m pytest -q            # full suite
python -m pytest tests/test_api.py -q   # API layer only
```

CI runs the same command in `.github/workflows/ci.yml` (backend job) on every
push/PR to `main`.

## Coverage by file

| File | Tests | What it verifies |
|------|------:|------------------|
| `tests/test_agents.py` | 13 | Extractor (empty input, parsed output, fuzzy category mapping, LLM failure fallback) · Comparator (mapping + failure) · Ranker (threshold mapping, LLM path, deterministic fallback) · Negotiator (green→no negotiation, red→pack) · Orchestrator (full pipeline, short-circuit, extractor crash) |
| `tests/test_api.py` | 9 | `/health`, `/analyze` 422 for short/empty text, `/analyze` success shape + `reasoning` + `quota_remaining`, contract row persisted + list/fetch/delete round-trip, `/upload` 422, `/fair-clauses` v2 shape + 7 categories, `/stats` + `/history` |
| `tests/test_auth.py` | 3 | register → login → `/auth/me` round-trip (errors: duplicate email, invalid email, weak password, wrong password, missing token) · password stored hashed · **user-scoped** contract isolation (Alice can't see/fetch/delete guest docs) |
| `tests/test_uploads.py` | 7 | File-type detection (PDF/TXT/MD/DOCX by MIME + extension fallback; legacy `.doc`) · DOCX extraction (paragraphs + `Term \| 12 months` table cells) · TXT/MD decode · `.doc` → helpful 400 message · unsupported type → ValueError · empty DOCX → ValueError |
| `tests/test_store_facade.py` | 3 | `app.db` facade still exposes all store functions + `DATA_DIR` · `ChromaStore` satisfies the `Store` protocol (swap-in seam) · `chunk_text` delegation |
| `tests/test_engine_correctness.py` | 9 | Retrieval ranking + similarity band + empty corpus + per-document scoping + empty scope never falls back to the global corpus · chat grounding (refuses without context, refuses unknown docs, cites exact source clauses) · structured-output validation + fallback |
| `tests/test_cross_clause_seam.py` | 3 | Deterministic cross-clause detection (LLM-free) · inconsistency flagging · clause IDs/values preserved on the wire |
| `tests/test_cross_clause_pipeline_seam.py` | 3 | Orchestrator → cross-clause report seam · notice-period inconsistency · serialization to the API report schema |
| `tests/test_cross_clause_integration.py` | 3 | Relationship + inconsistency without an LLM · privacy-preserving serialization (no raw clause text) · ships through the orchestrator seam |
| `tests/test_version_comparison_seam.py` | 2 | Golden `30 days → 60 days` modified change, zero LLM calls · exact `VersionComparisonReportOut` wire mapping |
| **Total** | **55** | |

## Latest results

```
55 passed, 14 warnings in ~76s — backend suite
```

(The warnings are FastAPI `on_event` / httpx deprecation notices only.)

## What is not yet automated

- **Live LLM evaluation** — run manually with `python evaluate_system.py` or the
  experiment harness `python experiments/run_experiments.py`
  (uses the 70-case labelled dataset in `backend/data/eval_dataset.json`,
  writes `backend/data/eval_report.json` + `backend/experiments/report_latest.json`).
  See `docs/EVALUATION.md`.
- **Frontend component tests** — the UI is type-checked (`tsc --noEmit`) and
  production-built in CI; add `@testing-library/react` specs before shipping
  paid features.
- **Upload (PDF) end-to-end** — covered structurally via `uploads.extract_text`;
  a full PDF fixture test is a follow-up. DOCX is covered end-to-end including
  table cells (`tests/test_uploads.py`).