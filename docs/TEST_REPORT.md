# Test Report

Status of the automated test suite for ClauseGuard. Every LLM call is stubbed,
and the vector store + relational database run against throwaway temp paths, so
the suite is deterministic, hermetic and runs without an API key.

## Run it

```bash
cd backend
python -m pytest -q                          # full suite
python -m pytest tests/test_security.py -q   # security posture only
```

CI runs the same command in `.github/workflows/ci.yml` (backend job) on every
push/PR to `main`, alongside the frontend type check, translation audit and
frontend tests.

## Coverage by file

| File | Tests | What it verifies |
|------|------:|------------------|
| `tests/test_agents.py` | 1 | The four agents and the orchestrator: extractor (empty input, parsed output, fuzzy category mapping, LLM-failure fallback) · comparator (mapping + failure) · ranker (threshold mapping, LLM path, deterministic fallback) · negotiator (green→no negotiation, red→pack) · orchestrator (full pipeline, short-circuit, extractor crash) |
| `tests/test_api.py` | 9 | `/health`, `/analyze` 422 for short/empty text, `/analyze` success shape + `reasoning` + `quota_remaining`, contract row persisted + list/fetch/delete round-trip, `/upload` 422, `/fair-clauses` v2 shape + 7 categories, `/stats` + `/history` |
| `tests/test_auth.py` | 3 | register → login → `/auth/me` round-trip (errors: duplicate email, invalid email, weak password, wrong password, missing token) · password stored hashed · **user-scoped** contract isolation (Alice can't see/fetch/delete guest docs) |
| `tests/test_uploads.py` | 7 | File-type detection (PDF/TXT/MD/DOCX by MIME + extension fallback; legacy `.doc`) · DOCX extraction (paragraphs + `Term \| 12 months` table cells) · TXT/MD decode · `.doc` → helpful 400 message · unsupported type → ValueError · empty DOCX → ValueError |
| `tests/test_store_facade.py` | 3 | `app.db` facade still exposes all store functions + `DATA_DIR` · `ChromaStore` satisfies the `Store` protocol (swap-in seam) · `chunk_text` delegation |
| `tests/test_engine_correctness.py` | 9 | Retrieval ranking + similarity band + empty corpus + per-document scoping + empty scope never falls back to the global corpus · chat grounding (refuses without context, refuses unknown docs, cites exact source clauses) · structured-output validation + fallback |
| `tests/test_cross_clause_seam.py` | 3 | Deterministic cross-clause detection (LLM-free) · inconsistency flagging · clause IDs/values preserved on the wire |
| `tests/test_cross_clause_pipeline_seam.py` | 3 | Orchestrator → cross-clause report seam · notice-period inconsistency · serialization to the API report schema |
| `tests/test_cross_clause_integration.py` | 3 | Relationship + inconsistency without an LLM · privacy-preserving serialization (no raw clause text) · ships through the orchestrator seam |
| `tests/test_version_comparison_seam.py` | 2 | Golden `30 days → 60 days` modified change, zero LLM calls · exact `VersionComparisonReportOut` wire mapping |
| `tests/test_phase3_quality.py` | 14 | Evidence computed after ranking · evidence attached to every clause · `cross_clause` present on the wire · deterministic `top_priorities` fallback · unit-preserving cross-clause comparison · version comparison keeps the original unit |
| `tests/test_phase4.py` | 7 | Tracked dates CRUD + reminder window (overdue counted, far-future excluded) · owner scoping (another account cannot read or write your rows) · bookmarks are idempotent and validated · checklist generation is additive and deduped · date suggestions are explicit dates only (relative wording is never converted) · deleting a contract removes its tracking rows |
| `tests/test_security.py` | 14 | CORS: allowed origin gets credentials, unknown origin gets none, no wildcard · internal failures never reach the caller (analysis, upload, agent trace, key check) · `REQUIRE_AUTH` blocks guests · sign-in rate limiting · the production guard refuses unsafe settings · security headers · oversized bodies rejected |
| **Total** | **90** | |

## Frontend

| Suite | Tests | What it verifies |
|-------|------:|------------------|
| `src/__tests__/app.test.tsx` | 5 | Routing: landing page, analyse page, friendly 404, redirect to login when auth is required, navigation from the landing page |
| `src/__tests__/pwa.test.tsx` | 9 | The manifest is installable and points at icons that exist · the service worker caches the shell and **never** caches API traffic, `Authorization` requests or cross-origin requests |
| `src/__tests__/i18n.test.tsx` | 7 | The app renders in हिन्दी, தமிழ் and తెలుగు · every catalogue has exactly the same keys as English · no translation is empty |
| **Total** | **21** | |

The translation audit (`frontend/scripts/check_i18n_keys.py`) proves that every
`t('…')` key used in the code exists in all four catalogues; it runs in CI.

## Latest results

```
90 passed, 34 warnings in ~136s — backend suite
21 passed in ~15s — frontend suite
```

(The warnings are FastAPI `on_event` / httpx deprecation notices only.)

## What is not yet automated

- **Live LLM evaluation** — run manually with `python evaluate_system.py` or the
  experiment harness `python experiments/run_experiments.py`
  (uses the labelled dataset in `backend/data/eval_dataset.json`,
  writes `backend/data/eval_report.json` + `backend/experiments/report_latest.json`).
  See `docs/EVALUATION.md`.
- **Biometric unlock on a real device** — the app lock uses WebAuthn; the
  prompt itself can only be exercised on hardware with a fingerprint or face.
- **Android release smoke test** — the signed `.aab` is built and verified in
  CI-free local runs, but the app is not installed on a device in this repo.
- **Upload (PDF) end-to-end** — covered structurally via `uploads.extract_text`;
  a full PDF fixture test is a follow-up. DOCX is covered end-to-end including
  table cells (`tests/test_uploads.py`).
