# Experimental Methodology & Measured Results

This document is the honest record of how ClauseGuard's classification
performance is measured. Numbers are **measured on the labelled dataset**, never
invented. Anything not yet measured is explicitly labelled "pending".

## 1. Dataset

`backend/data/eval_dataset.json` (format `v2`) — **70 single-clause cases**,
10 per canonical category:

| Category | Cases | Source-style |
|----------|-------|--------------|
| Payment | 10 | gym memberships, subscriptions, fee clauses |
| Auto-Renewal | 10 | renewals, opt-outs, notice periods |
| Liability | 10 | damage, indemnity, exclusions |
| Data Privacy | 10 | data collection/sharing |
| Dispute | 10 | arbitration, jurisdiction |
| Warranty | 10 | guarantees, repair/replace |
| Other | 10 | mixed consumer contract terms |

Each case has a single ground-truth label `expected_risk` in
`{red, yellow, green}` assigned from consumer-protection guidance. Labels are
fixed before evaluation and reviewed in `docs/EVALUATION.md`.

## 2. Metrics

For a run over the full 70 cases:

- **Accuracy** — fraction of cases whose *highest-risk predicted clause* matches
  the expected label.
- **Per-class precision / recall / F1 + support** over the `{red, yellow, green}`
  classes (macro vs micro: both reported in the JSON report).
- **Per-category accuracy** — per individual clause category.

The prediction is the most severe `risk_level` assigned by the pipeline to the
single extracted clause (see `experiments/run_experiments.py::predict`).

## 3. Experimental conditions

| Condition | Orchestrator flag | What changes |
|-----------|-------------------|--------------|
| **WITH-RAG (baseline)** | default | `CompareAgent` retrieves the nearest fair reference(s) from the 197-clause Chroma library; the reference is injected into the ranker prompt. |
| **NO-RAG (ablation)**   | `--ablate-rag` | Same 4-agent pipeline, but the comparator reference is omitted — the ranker scores without any RAG grounding. |

Both use `openai/gpt-oss-120b` (Groq), temperature 0.2, JSON mode. Run:

```bash
python experiments/run_experiments.py                 # WITH-RAG, 70 cases
python experiments/run_experiments.py --ablate-rag    # NO-RAG ablation
python experiments/run_experiments.py --limit 10      # quick sanity
```

Outputs: `experiments/results.csv`, `experiments/report_r<ts>.json`,
`experiments/report_latest.json` (pointer to newest **valid** run).

## 4. Result: WITH-RAG baseline (valid)

Report: `experiments/report_r1789656419.json` — **accuracy 68.57% (48/70)**,
262 LLM calls, runtime ≈ 18 min.

Per-class:

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|---------|
| red    | 55.3% | 100.0% | 71.2 | 21 |
| yellow | 50.0% | 23.8% | 32.3 | 21 |
| green  | 100.0% | 78.6% | 88.0 | 28 |

Per-category accuracy:

| Category | Accuracy |
|----------|----------|
| Auto-Renewal | 90% |
| Data Privacy | 80% |
| Warranty | 80% |
| Payment | 70% |
| Other | 70% |
| Liability | 50% |
| Dispute | 40% |

Interpretation: the model is near-perfect at *not* calling fair clauses riskier
than they are (green precision 100%), but is conservative about marking
moderate-yellow risk (yellow recall 23.8%) — most false negatives land in red
(red recall 100%). The weakest categories are **Dispute** (40%) and
**Liability** (50%), which are the most context/subjectivity-dependent.

## 5. Result: NO-RAG ablation — PENDING (invalidated run)

> ⚠️ **Not a valid result.** An ablation attempt (run `report_r1789672949`)
> hit Groq's daily token cap (`limit 200000`, `rate_limit_exceeded`) around
> case 45/70; the remaining cases returned no clauses (`"unknown"`) and would
> have dragged the headline number to a meaningless 14.29%. That run is kept
> only as `experiments/report_r1789672949_INVALID_TPD.json` as evidence of the
> quota incident and **must not be cited**.

The ablation will be re-run in two chunks after the TPD counter resets and the
valid numbers (with/without-RAG delta, plus a per-category comparison) will be
tabled **here** and in `docs/EVALUATION.md`.

## 6. Threats to validity

- Single-clause cases may not reflect multi-clause real contracts (pipeline
  still runs the full 4 agents).
- Ground-truth labels encode one reviewer's consumer-protection reading.
- Token-based cost figures use a 4 chars/token approximation.
- LLM temperature 0.2 means results are deterministic-ish but not bit-exact.

## 7. Reproducibility

Pin the environment: `pip install -r requirements.txt`, seed Chroma
(`db.seed_fair_clauses()` runs on startup), then run the harness commands in §3.
The full prompt/schema definitions live in `app/agents/`; the harness itself is
`experiments/run_experiments.py` (≈200 lines, no hidden logic).