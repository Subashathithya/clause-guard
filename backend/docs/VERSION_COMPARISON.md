# Version-to-Version Clause Comparison (the `/drift` seam)

The consumer-facing question this feature answers:

> You signed Old Co. on v3. Now it's the same agreement on v4. As the
> person whose money is at risk — what actually **changed**, and did any of
> it get **riskier**?

We answer it deterministically, at clause level, with **zero LLM calls** on the
path that matters, and we ship the answer in the exact wire schema the API
already uses — so observability never sees raw clause text.

## 1. The golden scenario (the contract)

Two versions of a `Termination` clause, otherwise identical, differ only in the
written-notice term:

```text
v_old:  Either party may terminate with 30 days written notice.
v_new:  Either party may terminate with 60 days written notice.
```

Deterministic result: **exactly one** change, `change_type = "modified"`,
`previous_value = "30 days"`, `current_value = "60 days"` — clause ids and the
literal 30→60 values only. A matching `Confidentiality` clause that did **not**
change produces **no** change at all.

## 2. Engine (deterministic, not a verdict)

`app/services/version_comparison.py`
* `detect(old, new, *, semantic=None)` → `VersionComparisonReport`
  * value-level diffing only. `30 days → 60 days` is one `modified` change;
    identical clauses are `unchanged` and never reported; a value that only
    exists on one side is `added`/`removed`.
  * the deterministic path scans **zero** semantic pairs and makes **zero**
    LLM calls — `llm_calls == 0`, `semantic_pairs_scanned == 0`. The LLM tier
    is opt-in and never required (§10 compliance; hermetic tests run strictly
    on this path).
* `to_out(report)` → `VersionComparisonReportOut` — maps the engine report
  *exactly* onto the wire schema the API ships: the report carries only
  clause ids (`clause_id_a/clause_id_b`), the canonical category, the canonical
  change label (`modified/added/removed/unchanged/ambiguous`), and the literal
  previous/current values. **Never** raw clause text, **never** an LLM verdict.

## 3. Wire contract (`app/schemas.py`)

`POST /drift` ships:
```json
{
  "status": "SUCCESS",
  "version_comparison": {
    "version_a": "...", "version_b": "...",
    "changes": [
      {"clause_id_a": "a1", "clause_id_b": "b1", "category": "Termination",
       "change_type": "modified",
       "previous_value": "30 days", "current_value": "60 days",
       "explanation": "…"}
    ],
    "attention_evolution": [
      {"clause_id": "a1", "category": "Termination",
       "previous_attention": "red", "current_attention": "red",
       "evolution": "unchanged"}
    ],
    "clauses_a": 2, "clauses_b": 2,
    "candidate_pairs": 闻, "matched_pairs": 1, "ambiguous_pairs": 0,
    "llm_calls": 0, "semantic_pairs_scanned": 0,
    "feedback": "…"
  }
}
```

`version_comparison` is **additive** to the existing `/drift` aggregate
(`overall_delta`, `changes`… are untouched), so no consumer of the old
contract breaks.

`attention_evolution` rides the same seam: each clause's `previous_attention`
→ `current_attention` band (`red|yellow|green|unknown`) and its
`evolution` (`unchanged|increased|decreased|new|removed`) — so the API can
say "this term now demands more attention" without a second model call.

## 4. Hermetic (nothing external)

Tests live in `backend/tests/test_version_comparison_seam.py` (join the
existing hermetic seam suite). They import `app.services.version_comparison`
on a path with `GROQ_API_KEY=""` and assert:

* golden: `30 days → 60 days` is one `modified` change with the literal
  values, `llm_calls == 0`, `semantic_pairs_scanned == 0`;
* wire: `to_out` ships exactly `VersionComparisonReportOut` / `VersionChangeOut`
  / `AttentionEvolutionOut` — header comment asserts clause-text never leaks
  and no LLM verdict ever ships;
* `AttentionEvolutionOut` domains are literals (`red/yellow/green`,
  `unchanged/increased/decreased/new/removed`).

These run in CI with no LLM, no vector store, no real DB.

---

**Running the hermetic seam** (from `backend/`):

```
cd backend
python -m pytest tests/test_version_comparison_seam.py -q
```

Both the golden seam and the wire seam stay green.
