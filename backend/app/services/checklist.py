"""Turn stored analysis negotiation data into a concrete checklist.

Only clauses the analysis actually flagged (negotiation needed or not green)
become items, and the wording comes from the analysis's own talking points or
suggested revision. No example or invented actions are added here.
"""
from __future__ import annotations

from typing import Iterable

MAX_GENERATED_ITEMS = 12


def checklist_from_clauses(clauses: Iterable[dict]) -> list[dict]:
    """Build checklist rows (plain dicts) from a stored analysis payload."""
    rows: list[dict] = []
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        risk = clause.get("risk_level")
        needs_review = bool(clause.get("negotiation_needed")) or risk not in ("green", None)
        if not needs_review:
            continue

        points = clause.get("talking_points")
        action = ""
        if isinstance(points, list):
            action = next((str(p).strip() for p in points if str(p).strip()), "")
        if not action:
            action = str(clause.get("suggested_counter_clause") or "").strip()
        if not action:
            category = str(clause.get("category") or "Other")
            action = f"Review the {category} section and ask for clearer, fairer wording."

        clause_id = clause.get("clause_id")
        rows.append(
            {
                "clause_index": str(clause_id) if clause_id else None,
                "text": action[:500],
                "position": len(rows),
            }
        )
        if len(rows) >= MAX_GENERATED_ITEMS:
            break
    return rows


def missing_rows(existing: Iterable, generated: Iterable[dict]) -> list[dict]:
    """Keep only generated items whose source section is not already listed."""
    covered = {
        item.clause_index
        for item in existing
        if getattr(item, "clause_index", None)
    }
    start = len(list(existing))
    out: list[dict] = []
    for row in generated:
        clause_index = row.get("clause_index")
        if clause_index and clause_index in covered:
            continue
        if clause_index:
            covered.add(clause_index)
        out.append({**row, "position": start + len(out)})
    return out
