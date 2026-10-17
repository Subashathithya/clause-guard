"""ClauseGuard experiment harness (Phase 1 — Evaluation & strong baseline).

Runs the full 4-agent pipeline over backend/data/eval_dataset.json (v2, 70
labelled cases across the 7 canonical categories) and produces:

  * overall accuracy
  * per-category accuracy
  * per-class precision / recall / F1 (red / yellow / green)
  * estimated LLM calls + tokens + Groq cost per clause
  * a WITH-RAG vs WITHOUT-RAG ablation so reviewers can see RAG's contribution

Outputs:
  experiments/results.csv          one row per case, per run
  experiments/report_r{run_id}.json  full per-run metrics
  experiments/report_latest.json     pointer to the newest run

Usage (from backend/, with the venv active):
  python experiments/run_experiments.py                  # RAG mode (70 cases)
  python experiments/run_experiments.py --ablate-rag     # plain-LLM mode
  python experiments/run_experiments.py --limit 10       # quick sanity run
  python experiments/run_experiments.py --delay 0.5      # be nice to Groq
"""
import argparse
import csv
import json
import os
import sys
import time

from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import llm  # noqa: E402
from app.agents.orchestrator import Orchestrator  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
EXPERIMENTS_DIR = os.path.dirname(os.path.abspath(__file__))
LABELS = ["red", "yellow", "green"]
ORDER = {"red": 0, "yellow": 1, "green": 2, "unknown": 3}
TOKENS_PER_CHAR = 0.25  # ~4 chars/token approximation
GROQ_PER_1K_TOKENS = 0.002  # approximate $/1k tokens for gpt-oss-120b


def load_cases() -> list[dict]:
    with open(os.path.join(DATA_DIR, "eval_dataset.json"), encoding="utf-8") as fh:
        return json.load(fh)["cases"]


def predict(case: dict, ablate: bool) -> str:
    """Return the highest-risk level predicted for the single-clause case."""
    result = Orchestrator(ablate_rag=ablate).run(case["text"], document_name=f"eval_{case['id']}")
    clauses = result.clauses
    if not clauses:
        return "unknown"
    clauses_sorted = sorted(clauses, key=lambda c: ORDER.get(c.risk_level, 3))
    return clauses_sorted[0].risk_level


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0


def run(cases: list[dict], ablate: bool, delay: float) -> dict:
    rows = []
    correct = 0
    confusion = defaultdict(lambda: defaultdict(int))
    cat_correct = defaultdict(int)
    cat_total = defaultdict(int)
    total_chars = 0

    calls_before = llm.get_call_count()
    chars_before = llm.get_char_count()
    t0 = time.perf_counter()

    for i, case in enumerate(cases, 1):
        expected = case["expected_risk"]
        predicted = "error"
        try:
            predicted = predict(case, ablate)
        except Exception as exc:  # noqa: BLE001
            predicted = "error"
            print(f"  [{i}/{len(cases)}] {case['id']}: ERROR - {exc}")
        ok = predicted == expected
        correct += int(ok)
        confusion[expected][predicted] += 1
        cat_correct[case["category"]] += int(ok)
        cat_total[case["category"]] += 1
        total_chars += len(case["text"])
        rows.append({**case, "predicted": predicted, "correct": ok})
        print(
            f"  [{i}/{len(cases)}] {case['id']} [{case['category']:<13}] "
            f"expected={expected:<6} predicted={predicted:<6} {'PASS' if ok else 'FAIL'}"
        )
        if delay:
            time.sleep(delay)

    elapsed = time.perf_counter() - t0
    accuracy = (correct / len(cases)) * 100 if cases else 0.0

    per_class = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) * 100 if (tp + fp) else 0.0
        recall = tp / (tp + fn) * 100 if (tp + fn) else 0.0
        per_class[label] = {
            "precision": round(precision, 1),
            "recall": round(recall, 1),
            "f1": round(_f1(precision, recall), 1),
            "support": tp + fn,
        }

    per_category = {
        cat: {
            "accuracy": round(cat_correct[cat] / cat_total[cat] * 100, 1),
            "correct": cat_correct[cat],
            "total": cat_total[cat],
        }
        for cat in cat_total
    }

    calls = llm.get_call_count() - calls_before
    chars = llm.get_char_count() - chars_before
    tokens = int(chars * TOKENS_PER_CHAR)
    cost_usd = round(tokens / 1000 * GROQ_PER_1K_TOKENS, 3)

    return {
        "cases": len(cases),
        "correct": correct,
        "accuracy": round(accuracy, 2),
        "per_class": per_class,
        "per_category": per_category,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "rows": rows,
        "runtime_seconds": round(elapsed, 1),
        "llm_calls": calls,
        "prompt_chars": chars,
        "est_tokens": tokens,
        "est_cost_usd": cost_usd,
        "cost_caveat": "tokens approximated at 4 chars/token; price per 1k tokens set in harness.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ClauseGuard evaluation experiments")
    parser.add_argument("--limit", type=int, default=0, help="only the first N cases")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds between cases")
    parser.add_argument("--ablate-rag", action="store_true",
                        help="rank clauses WITHOUT the RAG fair-clause reference (ablation)")
    args = parser.parse_args()

    cases = load_cases()
    if args.limit:
        cases = cases[: args.limit]

    mode = "WITH-RAG" if not args.ablate_rag else "NO-RAG (ablation)"
    print(f"Evaluating {len(cases)} labelled cases — mode: {mode}\n")

    report = run(cases, args.ablate_rag, args.delay)
    report["mode"] = mode
    report["timestamp"] = time.time()
    report["llm_model"] = "openai/gpt-oss-120b"

    run_id = int(time.time())
    os.makedirs(EXPERIMENTS_DIR, exist_ok=True)
    csv_path = os.path.join(EXPERIMENTS_DIR, "results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["id", "category", "expected_risk", "predicted", "correct", "text"],
        )
        writer.writeheader()
        for r in report["rows"]:
            writer.writerow({k: r.get(k) for k in ["id", "category", "expected_risk", "predicted", "correct", "text"]})

    report_path = os.path.join(EXPERIMENTS_DIR, f"report_r{run_id}.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    with open(os.path.join(EXPERIMENTS_DIR, "report_latest.json"), "w", encoding="utf-8") as fh:
        json.dump({**report, "_report_file": report_path}, fh, indent=2)

    print("\n" + "-" * 56)
    print(f"Mode: {mode}")
    print(f"Accuracy: {report['accuracy']:.2f}%  ({report['correct']}/{report['cases']})")
    print("Per-class (precision / recall / F1):")
    for label in LABELS:
        m = report["per_class"][label]
        print(f"  {label:<6} P={m['precision']:>5}%  R={m['recall']:>5}%  F1={m['f1']:>5}  n={m['support']}")
    print("Per-category accuracy:")
    for cat, m in sorted(report["per_category"].items()):
        print(f"  {cat:<13} {m['correct']}/{m['total']} = {m['accuracy']}%")
    print("-" * 56)
    print(f"CSV   -> {csv_path}")
    print(f"Report -> {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())