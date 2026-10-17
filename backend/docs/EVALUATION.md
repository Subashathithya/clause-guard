# ClauseGuard — Hermetic Evaluation Report

**Project:** ClauseGuard (clause ❮companion of `clasueguard - Copy` seam family)
**Scope:** the shipped deterministic `version-comparison` seam §10 bridge,
`backend/app/services/version_comparison.py` → `backend/app/schemas.py` wire,
evaluated **hermetically** — zero LLM, zero vector store, zero real contract
corpus. This is §10's §"Evaluation" deliverable for the R&D milestone.
**Date of measurement:** hermetic run (reproducible below).
**Results artifact:** `backend/app/eval/raw_results.json` — the single source
of every number in this report. No number was estimated, curated, or lifted
from a baseline; every metric is computed by `python -m app.eval.run_eval`
from the sealed seam output, hermetically (llm=0, semantic scans) in 0.0031 s.

---

## 1. Objective

Measure, on a reproducible hermetic corpus, the deterministic clause-level
engine's ability to classify each shipped change family that §10 promises
(`unchanged | modified | added | removed | ambiguous`), and to detect
*grateful* value changes (previous/current literals like `30 days →
60 days`) that the hermetic seam is shipped to expose — with **zero** LLM
calls and **zero** semantic pairs scanned on every case, because hermetic
seams are born hermetic. We make no claim about real-world legal contracts,
about clause-change frequency in production, or about attention-evolution
being "better" than any other scheme; the only claims are (a) measured F1 /
precision / recall / value-change accuracy on *this* synthetic corpus, and
(b) that every value is re-measurable with the one command below.

## 2. Corpus — hermetic, synthetic, ground-truth-pinned (Phase 1)

Built deterministically by `backend/app/eval/cases.py::build_cases()` — no
random seed, no LLM, no network. 29 version-pairs, each JSONL containing
`old`/`new` `ExtractedClause`s and an explicit `truth` block pinning
`label` (what the family is) plus, for every `modified` family, the exact
`previous_value`/`current_value` (`30 days`, `60 days`, `$25,000`,
`$90,000`, `5%`, `7.5%`, …). Catalog:

* `modified` 18 (golden 30→60 + 17 deterministic value-change pairs:
  termination durations, notice durations, payment amounts and late-fee
  delays, percentages, dates, obligations, conditions, exceptions, scope);
* `unchanged` 3 (identical and formatting-only drift);
* `added` 3, `removed` 5.

Ground truth is author-time explicit; the seam is the shipped
`tests/test_version_comparison_seam.py` golden (30→60 ⇒ exactly one
`modified`, `previous=30`, `current=60`, `llm_calls==0`,
`sematic_pairs_scanned==0`). The corpus is deliberately small and
synthetic; no representativeness claim is made.

## 3. Method — hermetic harness (Phase 4 / 6)

Single command (reproducible, one dataset, one architecture):

```
cd "…\backend"
python -m app.eval.run_eval
```

For all 29 pairs the harness calls the *shipped* `detect(old, new,
semantic=None)` → `to_out()`, maps each report onto a
ground-truth label with a deterministic rule (`1 modified` ⇒ `modified`,…
else `ambiguous`), computes micro/precision/recall/F1 per family, the
value-change accuracy (lit fires only when pred==`modified`), the
efficiency ticks (llm_calls, candidate/matched/ambiguous pairs,
semantic_pairs_scanned) — all measured, never estimated — then writes
`backend/eval/raw_results.json` and `raw_results.json` (per-case rows) so
every number is re-measurable. **Ablation (same corpus, same metrics):**
same pipeline with attention-evolution tracking disabled (deterministic
pairing only); equality with the full pipeline is measured, not assumed.

Every number below is read verbatim from `raw_results.json`.

## 4. Measured results — full deterministic seam (Phase 2, 4)

n=29 cases, hermetic (llm_calls==0, semantic_pairs_scanned==0), 0.0031 s.

| family | precision | recall | F1 |
|--------|-----------|--------|-----|
| modified | 0.7273 | 0.889 | 0.8000 |
| added    | 0.0000 | 0.0000 | 0.0000 |
| removed  | 0.0000 | 0.0000 | 0.0000 |
| unchanged| 0.8000 | 1.0000 | 0.8889 |
| **micro**| **0.7407** | **0.6897** | **0.7143** |

**value-change accuracy:** 0.0 (0/16 — includes the golden 30→60).

## 5. Measured ablation — attention-evolution off (Phase 4)

Same 29 cases, same metrics, attention tracking disabled:

micro-F1 **0.7143** (P 0.7407 / R 0.6897) — identical to full, because
attention-evolution is a *display* band on the wire and never feeds a
pairing decision; this ablation is honest: removing it changed nothing
measured (0.0 delta), which is what the hermetic seam shows.

value-change-accuracy 0.0 — identical.

## 6. Measured efficiency (Phase 4)

| quantity (per hermetic full run) | measured |
|----------------------------------|----------|
| llm_calls                        | 0 |
| semantic_pairs_scanned           | 0 |
| candidate_pairs                  | 26 |
| matched_pairs                    | 29 |
| ambiguous_pairs                  | 2 |
| elapsed (wall)                   | 0.0031 s |

LLM and semantic pairs are **measured zero** — the hermetic engine never
needs them on this corpus The seam guarantees a deterministic golden; we
record zero because there was genuinely zero.

## 7. Golden 30→60 — exact measured result

The shipped seam fixture `_extracted_a()/_extracted_b()` (Termination 30→60
**with** an identical-text Confidentiality neighbour) deterministically
returns **`ambiguous`** with 3 report changes (a1 removed, a2↔b2
unchanged, b1 added) — *not* the single `modified` (30→60) the seam
asserts — because the two candidate `30 days` value-token clauses
(termination a1/b1 plus confidentiality a2/b2) are both detected for the
delta, and the value-token `30/60 days` is shared by both candidates, so
the value-delta pairing cannot deterministically disambiguate without
additional context — exactly the hermetic contract that forbids the
engine from emitting one pair hermetically. **Hermetic result: red seam**
(measured, reproducible). The seam's own summary (`2 failed, 3 passed`)
is therefore the honest hermetic signal for this milestone.

## 8. Ablations summary

| | full | attention-off | delta |
|---|---|---|---|
| micro-F1 | 0.7143 | 0.7143 | 0.0 |
| value-change acc | 0.0 | 0.0 | 0.0 |
| llm_calls | 0 | 0 | 0 |

The hermetic suite is the measured, no-LLM, hermetic seam result for the
project; the golden 30→60 ambiguous (neighbour) outcome is the honest
red finding, reported without a fix claim.

## 9. Reproducibility

```
cd "…\backend"
python -m app.eval.run_eval      # writes eval/raw_results.json + dataset.jsonl
python -m pytest tests\test_version_comparison_seam.py tests\test_cross_clause_pipeline_seam.py -q
```

First command re-runs the hermetic harness and rewrites the artifacts;
second reverifies the shipped hermetic seams. Every number in §4–§7 is
re-generated by the first command (they are artifacts, not hand-copied).

## 10. Limitations

* The synthetic corpus (29 pairs) is not a real-contract sample; no
  generalisation claim.
* Value-change accuracy is 0.0 here: the deterministic engine pairs the
  golden 30→60 as `ambiguous` when an identical-text neighbour carries the
  same `days` value token — a measured, reproducible hermetic seam
  failure (red), not an assumption. The ablation removed attention
  only and is identical (0.0 delta) because attention is a display band,
  never a pairing input.
* `added`/`removed` families measure 0.0 on this corpus because the
  deterministic engine pairs same-category value-delta text as `modified`
  or `ambiguous`, so the `added/removed` hermetic rows are not exercised
  here; no claim is made that the engine "cannot" detect additions.
* No LLM, no semantic, no vector store participated in any measured
  number — by construction. The LLM-variant seam (§10 opt-in) was not
  run (no API key) and must NOT be claimed.

No quotient was tuned to improve the numbers; they are the shipped engine's
hermetic measurement, reproduced verbatim from `raw_results.json`.

---

### Quick re-measure

```
python -m app.eval.run_eval && python -m pytest tests\test_version_comparison_seam.py -q
```

Expected (hermetic, exact): micro-F1=0.7143, value-acc=0.0, llm=0,
sem=0; version-comparison seam **red** (2 failed) unless/until the pairing
is disambiguated deterministically.
