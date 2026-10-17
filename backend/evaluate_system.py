"""ClauseGuard accuracy evaluation harness.

Runs the full 4-agent pipeline (orchestrator) against the labelled dataset in
data/eval_dataset.json and reports accuracy, per-class precision/recall and a
confusion matrix, then writes data/eval_report.json.

Usage (from backend/, with the venv active):
    python evaluate_system.py                 # evaluate every case
    python evaluate_system.py --limit 10      # quick sanity run
    python evaluate_system.py --delay 2       # pause between cases (rate limits)
    python evaluate_system.py --api           # evaluate against a running server
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict

from app.agents.orchestrator import run_orchestrator

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LABELS = ["red", "yellow", "green"]


def load_cases() -> list[dict]:
    with open(os.path.join(DATA_DIR, "eval_dataset.json"), encoding="utf-8") as fh:
        return json.load(fh)["cases"]


def predict_inprocess(case: dict) -> str:
    """Return the highest-risk level predicted for the case."""
    result = run_orchestrator(case["text"], document_name=f"eval_{case['id']}")
    clauses = result.clauses
    if not clauses:
        return "unknown"
    # The case is a single clause; take the highest risk among outputs.
    order = {"red": 0, "yellow": 1, "green": 2, "unknown": 3}
    clauses_sorted = sorted(clauses, key=lambda c: order.get(c.risk_level, 3))
    return clauses_sorted[0].risk_level


def predict_api(case: dict, api_url: str) -> str:
    import requests

    resp = requests.post(
        f"{api_url}/analyze",
        json={"text": case["text"], "document_name": f"eval_{case['id']}"},
        timeout=180,
    )
    data = resp.json()
    clauses = data.get("clauses", [])
    if not clauses:
        return "unknown"
    order = {"red": 0, "yellow": 1, "green": 2, "unknown": 3}
    clauses_sorted = sorted(clauses, key=lambda c: order.get(c.get("risk_level"), 3))
    return clauses_sorted[0].get("risk_level", "unknown")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate ClauseGuard accuracy")
    parser.add_argument("--limit", type=int, default=0, help="evaluate only the first N cases")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between cases")
    parser.add_argument("--api", action="store_true", help="use a running server instead of in-process")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    cases = load_cases()
    if args.limit:
        cases = cases[: args.limit]

    print(f"Evaluating {len(cases)} labelled cases "
          f"({'API' if args.api else 'in-process'} pipeline)...\n")

    confusion = defaultdict(lambda: defaultdict(int))
    correct = 0
    results = []

    for i, case in enumerate(cases, 1):
        expected = case["expected_risk"]
        try:
            predicted = predict_api(case, args.api_url) if args.api else predict_inprocess(case)
        except Exception as exc:  # noqa: BLE001
            predicted = "error"
            print(f"  [{i}/{len(cases)}] {case['id']}: ERROR - {exc}")
            results.append({**case, "predicted": predicted, "correct": False})
            if args.delay:
                time.sleep(args.delay)
            continue

        ok = predicted == expected
        correct += int(ok)
        confusion[expected][predicted] += 1
        results.append({**case, "predicted": predicted, "correct": ok})
        print(f"  [{i}/{len(cases)}] {case['id']}: expected={expected:<6} "
              f"predicted={predicted:<6} {'PASS' if ok else 'FAIL'}")
        if args.delay:
            time.sleep(args.delay)

    accuracy = (correct / len(cases)) * 100 if cases else 0.0

    # per-class precision / recall
    metrics = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) * 100 if (tp + fp) else 0.0
        recall = tp / (tp + fn) * 100 if (tp + fn) else 0.0
        metrics[label] = {"precision": round(precision, 1), "recall": round(recall, 1),
                          "support": tp + fn}

    report = {
        "cases": len(cases),
        "correct": correct,
        "accuracy": round(accuracy, 2),
        "metrics": metrics,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "results": results,
    }

    out_path = os.path.join(DATA_DIR, "eval_report.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("\n" + "-" * 48)
    print(f"Accuracy: {accuracy:.2f}%  ({correct}/{len(cases)})")
    for label in LABELS:
        m = metrics[label]
        print(f"  {label:<6} precision={m['precision']:>5}%  recall={m['recall']:>5}%  n={m['support']}")
    print("-" * 48)
    print(f"Full report written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
