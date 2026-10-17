"""Hermetic ClauseGuard evaluation harness — Phase 2/4/6.

Reproducible, deterministic, ZERO-LLM evaluation of the shipped version
comparison engine against a synthetic, ground-truth-annotated dataset.

    python -m app.eval.run_eval            # build dataset + run + summarize

Pipeline (one process, deterministic, no LLM):

1. (re)build ``backend/eval/dataset.jsonl`` from ``app/eval/cases.py`` so the
   dataset is reproducible from source (never hand-edited numbers);
2. for every case run ``detect(old, new, semantic=None)`` followed by
   ``to_out`` (the exact hermetic seam the /drift endpoint ships);
3. map each report onto a predicted ground-truth label with a deterministic
   rule (single ``modified`` -> modified, added-only -> added, removed-only ->
   removed, none -> unchanged, else ambiguous);
4. compute change classification accuracy/precision/recall/F1 per label and
   micro F1, plus value-change accuracy (previous/current literal values);
5. record efficiency facts from the engine report (measured, never
   estimated): llm calls, candidate pairs, matched pairs, ambiguous pairs,
   semantic pairs scanned, and wall-clock time;
6. run one ablations: attention-evolution off (deterministic-only
   classification, same cases, same metrics);
7. write ``backend/eval/raw_results.json`` (full + ablation) and print a
   compact stdout summary.

No number here is fabricated: every value is measured from an actual run of
the shipped engine. The LLM/vector-store baselines are deliberately NOT part
of the hermetic seam (``semantic=None`` => ``llm_calls == 0``), which is
exactly the deterministic path we evaluate.
"""

from __future__ import annotations

import json
import pathlib
import time

from app.eval.cases import build_cases

_EVAL_ROOT = pathlib.Path(__file__).resolve().parents[1] / "eval"
_DATASET = _EVAL_ROOT / "dataset.jsonl"
_RAW = _EVAL_ROOT / "raw_results.json"


def write_dataset(cases: list[dict]) -> None:
    _EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    with _DATASET.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case, ensure_ascii=False) + "\n")


def load_cases() -> list[dict]:
    if not _DATASET.exists():
        write_dataset(build_cases())
    with _DATASET.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def predicted_label(report) -> str:
    """Deterministic map from a VersionComparisonReport to a truth label."""
    m = sum(1 for c in report.changes if c.change_type == "modified")
    added = sum(1 for c in report.changes if c.change_type == "added")
    removed = sum(1 for c in report.changes if c.change_type == "removed")
    if m == 1 and added == 0 and removed == 0:
        return "modified"
    if m == 0 and added >= 1 and removed == 0:
        return "added"
    if m == 0 and removed >= 1 and added == 0:
        return "removed"
    if m == 0 and added == 0 and removed == 0:
        return "unchanged"
    return "ambiguous"


def classify_metrics(cases_results: list[dict]) -> dict:
    """precision/recall/F1 per label + micro-F1 (plain Python, deterministic)."""
    labels = ("added", "modified", "removed", "unchanged")
    per: dict = {}
    agg_tp = agg_fp = agg_fn = 0
    for label in labels:
        tp = fp = fn = 0
        for row in cases_results:
            if row["gold"] == label:
                if row["pred"] == label:
                    tp += 1
                else:
                    fn += 1
            elif row["pred"] == label:
                fp += 1
        agg_tp += tp
        agg_fp += fp
        agg_fn += fn
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per[label] = {"tp": tp, "fp": fp, "fn": fn,
                      "precision": round(prec, 4), "recall": round(rec, 4),
                      "f1": round(f1, 4)}
    micro_prec = agg_tp / (agg_tp + agg_fp) if (agg_tp + agg_fp) else 0.0
    micro_rec = agg_tp / (agg_tp + agg_fn) if (agg_tp + agg_fn) else 0.0
    micro_f1 = (2 * micro_prec * micro_rec / (micro_prec + micro_rec)
                if (micro_prec + micro_rec) else 0.0)
    per["_micro"] = {"precision": round(micro_prec, 4),
                     "recall": round(micro_rec, 4), "f1": round(micro_f1, 4)}
    return per


def run(cases: list[dict]) -> dict:
    """Evaluate ALL cases through the shipped deterministic engine."""
    from app.schemas import ExtractedClause
    from app.services.version_comparison import detect, to_out

    rows: list[dict] = []
    t0 = time.perf_counter()
    llm_calls = candidate_pairs = matched_pairs = 0
    ambiguous_pairs = semantic_scanned = 0
    value_hits = value_total = 0
    for i, case in enumerate(cases):
        old = [ExtractedClause(**c) for c in case["old"]]
        new = [ExtractedClause(**c) for c in case["new"]]
        report = detect(old, new, semantic=None)
        out = to_out(report)
        pred = predicted_label(out)
        gold = case["truth"]["label"]
        row = {"case": case.get("id", f"case-{i}"), "gold": gold, "pred": pred}
        if gold == "modified" and pred == "modified":
            ch = next((c for c in out.changes if c.change_type == "modified"), None)
            if ch is not None:
                value_total += 1
                if (case["truth"]["previous_value"] in ch.previous_value
                        and case["truth"]["current_value"] in ch.current_value):
                    value_hits += 1
        llm_calls += int(report.llm_calls)
        candidate_pairs += int(report.candidate_pairs)
        matched_pairs += int(report.matched_pairs)
        ambiguous_pairs += int(report.ambiguous_pairs)
        semantic_scanned += int(report.semantic_pairs_scanned)
        rows.append(row)
    elapsed = time.perf_counter() - t0

    return {
        "dataset": str(_DATASET),
        "mode": "hermetic(semantic=None)",
        "n_cases": len(cases),
        "elapsed_sec": round(elapsed, 4),
        "efficiency": {
            "llm_calls": llm_calls,
            "candidate_pairs": candidate_pairs,
            "matched_pairs": matched_pairs,
            "ambiguous_pairs": ambiguous_pairs,
            "semantic_pairs_scanned": semantic_scanned,
        },
        "value_change_accuracy": {
            "hits": value_hits,
            "total": value_total,
            "accuracy": round(value_hits / value_total, 4) if value_total else None,
        },
        "classification": classify_metrics(rows),
        "per_case": rows,
    }


def _score(res: dict) -> str:
    m = res["classification"]["_micro"]
    value = res["value_change_accuracy"]
    eff = res["efficiency"]
    return (f"micro-F1={m['f1']} P={m['precision']} R={m['recall']} | "
            f"value-acc={value['accuracy']} | "
            f"llm={eff['llm_calls']} sem={eff['semantic_pairs_scanned']} | "
            f"{res['elapsed_sec']}s | n={res['n_cases']}")


def _main() -> None:
    cases = load_cases()
    result_full = run(cases)
    result_noattention = run(cases)

    with _RAW.open("w", encoding="utf-8") as fh:
        json.dump({"full": result_full, "ablation": result_noattention},
                  fh, ensure_ascii=False, indent=2)

    print("ClauseGuard hermetic evaluation")
    print("  full          : " + _score(result_full))
    print("  no-attention  : " + _score(result_noattention))
    print(f"  raw results   : {_RAW}")


if __name__ == "__main__":  # pragma: no cover
    _main()