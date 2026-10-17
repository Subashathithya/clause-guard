"""Agent 2 — Comparator (RAG).

Compares every extracted clause against the fair / industry-standard clause
library stored in ChromaDB (seeded from data/fair_clauses.json) using semantic
similarity search.

Accuracy target: >80% — correctly recognises whether a clause resembles a fair
reference or deviates from the standard.
"""
import logging

from app import db
from app.schemas import ComparisonResult, ExtractedClause

logger = logging.getLogger(__name__)


class CompareAgent:
    """Agent 2: retrieve the nearest fair references for a clause."""

    name = "Comparator"

    def compare(self, clause: ExtractedClause, top_k: int = 3) -> ComparisonResult:
        """Return the closest fair-clause reference(s) and similarity for a clause."""
        try:
            result = db.compare_to_standard(clause.text, clause.category, top_k=top_k)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Comparator failed for %s: %s", clause.clause_id, exc)
            return ComparisonResult(notes=f"Comparison unavailable: {exc}")

        return ComparisonResult(
            standard_match=result.get("standard_match", "unknown"),
            similarity=float(result.get("similarity", 0.0) or 0.0),
            reference_clause=result.get("reference_clause"),
            reference_category=result.get("reference_category") or clause.category,
            notes=result.get("notes", ""),
        )