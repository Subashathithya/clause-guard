"""Deterministic, evidence-grounded clause verification for ClauseGuard.

Pure, side-effect-free checks decide whether an extracted clause is
*supported*. No LLM is called and no vector store is touched: everything here
is deterministic and unit-testable, and the caller injects the ``lookup``
callable so resolution stays crate-dry and store-agnostic.

A clause is only ``supported`` when every check passes. The individual flags
let the UI/API explain *why* a clause lacks support without ever leaking the
clause text back into observability payloads (privacy contract).

Following the pipeline contract:

* ``evidence_for_clause`` - one clause's deterministic evidence map.
* ``verify_evidence``    - aggregate report across a set of clauses.

``Observability.evidence(...)`` (defined in ``app.observability``) is the only
integration point into the observability layer; it is invoked defensively and
never raises into the caller.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Optional

from app.observability import observability
from app.schemas import CLAUSE_CATEGORIES, ExtractedClause

__all__ = [
    "clause_text_nonempty",
    "category_valid",
    "reference_clause_id",
    "evidence_for_clause",
    "analysis_clause_evidence",
    "verify_evidence",
    "verify_analysis_evidence",
    "payload_clause_evidence",
    "verify_payload_evidence",
]


def _risk_band(score: float) -> str:
    """Mirror the ranker's score -> level thresholds (34 / 67)."""
    if score >= 67:
        return "red"
    if score >= 34:
        return "yellow"
    return "green"


def _reference_flags(comparison) -> tuple[bool, bool]:
    """Return ``(reference_present, reference_credible)`` for a comparison."""
    if comparison is None:
        return False, False
    reference = getattr(comparison, "reference_clause", None)
    if isinstance(comparison, Mapping):
        reference = comparison.get("reference_clause")
        similarity = comparison.get("similarity")
    else:
        similarity = getattr(comparison, "similarity", None)
    present = bool(str(reference or "").strip())
    credible = (
        present
        and isinstance(similarity, (int, float))
        and not isinstance(similarity, bool)
        and 0.0 <= float(similarity) <= 1.0
    )
    return present, credible


def _evidence_flags(
    *,
    text,
    category,
    risk_level,
    risk_score,
    comparison,
) -> dict[str, bool]:
    """Build the deterministic evidence map shared by every caller."""
    text_ok = bool(str(text or "").strip())
    category_ok = str(category or "") in CLAUSE_CATEGORIES
    level = str(risk_level or "").lower()
    score_ok = (
        isinstance(risk_score, (int, float))
        and not isinstance(risk_score, bool)
        and 0 <= float(risk_score) <= 100
    )
    risk_consistent = bool(
        score_ok and level in ("red", "yellow", "green") and _risk_band(float(risk_score)) == level
    )
    reference_present, reference_credible = _reference_flags(comparison)
    reference_backed = bool(text_ok and category_ok and reference_credible)
    return {
        "text": text_ok,
        "category": category_ok,
        "risk_consistent": risk_consistent,
        "reference_present": reference_present,
        "reference_credible": reference_credible,
        "supported": bool(risk_consistent and reference_backed),
        "reference_backed": reference_backed,
    }


def clause_text_nonempty(clause: Optional[ExtractedClause]) -> bool:
    """True when the clause carries real (non-whitespace) text."""
    if clause is None:
        return False
    return bool((getattr(clause, "text", None) or "").strip())


def category_valid(clause: Optional[ExtractedClause]) -> bool:
    """True when the clause category is one of the known categories."""
    if clause is None:
        return False
    return bool((getattr(clause, "category", None) or "") in CLAUSE_CATEGORIES)


def reference_clause_id(
    lookup: Callable[[str], Optional[ExtractedClause]],
    clause: Optional[ExtractedClause],
) -> Optional[str]:
    """Return the clause_id an evidence reference should target, or None.

    A clause references another clause only when it declares a
    ``reference_clause_id`` AND that id resolves through ``lookup`` to a real
    clause. Dangling references are not evidence.
    """
    if not clause:
        return None
    ref = getattr(clause, "reference_clause_id", None) or ""
    if not ref:
        return None
    target = lookup(ref)
    if not target:
        return None
    return getattr(target, "clause_id", None)


def evidence_for_clause(
    clause: Optional[ExtractedClause],
    lookup: Callable[[str], Optional[ExtractedClause]],
) -> dict[str, bool]:
    """Run the full deterministic evidence suite for one clause.

    Returns a map of check-name -> verdict. ``supported`` is only True when
    every check passes; the individual flags let callers (or the UI) explain
    *why* a clause lacks support without leaking the clause text.
    """
    nonempty = clause_text_nonempty(clause)
    cat = category_valid(clause)
    ref_id = reference_clause_id(lookup, clause)
    ref_present = ref_id is not None
    ref_credible = ref_present and clause_text_nonempty(lookup(ref_id)) if ref_id else False
    return {
        "nonempty": nonempty,
        "category": cat,
        "reference_present": ref_present,
        "reference_credible": ref_credible,
        "supported": bool(nonempty and cat and ref_present and ref_credible),
    }


def verify_evidence(
    clauses: Iterable[ExtractedClause],
    lookup: Callable[[str], Optional[ExtractedClause]],
) -> dict[str, object]:
    """Run evidence checks over every clause.

    ``lookup`` is injected so this stays unit-testable without a vector store:
    the caller supplies ``lambda clause_id: by_id.get(clause_id)`` against its
    own clause dict.

    Returns an aggregate report:

    * ``total`` -- clauses examined
    * ``supported`` / ``unsupported`` -- deterministic support counts
    * ``by_clause`` -- per-clause_id flags (keys scoped to the caller's data)
    """
    by_clause: dict[str, dict[str, bool]] = {}
    supported = unsupported = 0
    for clause in clauses:
        result = evidence_for_clause(clause, lookup)
        by_clause[clause.clause_id] = result
        if result["supported"]:
            supported += 1
        else:
            unsupported += 1
    report = {
        "total": supported + unsupported,
        "supported": supported,
        "unsupported": unsupported,
        "by_clause": by_clause,
    }
    try:
        observability.evidence(
            checked=report["total"],
            supported=report["supported"],
            unsupported=report["unsupported"],
        )
    except Exception:  # observability must never break the evidence pass
        pass
    return report


# --------------------------------------------------------- analyzed-clause API
# The pipeline ships ``AnalyzedClause`` objects (risk verdict + RAG comparison),
# not only extracted clauses. The reference-resolution suite above is still the
# right contract for extraction-time evidence; the helpers below verify the
# *claims* the analysis actually makes: a real risk band and a real, credible
# reference when one is cited.

def analysis_clause_evidence(clause) -> dict[str, bool]:
    """Deterministic evidence flags for one ``AnalyzedClause``-like object."""
    return _evidence_flags(
        text=getattr(clause, "text", None),
        category=getattr(clause, "category", None),
        risk_level=getattr(clause, "risk_level", None),
        risk_score=getattr(clause, "risk_score", None),
        comparison=getattr(clause, "comparison", None),
    )


def payload_clause_evidence(clause: Mapping) -> dict[str, bool]:
    """Same flags for a stored (JSON) clause payload."""
    return _evidence_flags(
        text=clause.get("text"),
        category=clause.get("category"),
        risk_level=clause.get("risk_level"),
        risk_score=clause.get("risk_score"),
        comparison=clause.get("comparison"),
    )


def _aggregate(by_clause: dict[str, dict[str, bool]]) -> dict[str, object]:
    supported = sum(1 for flags in by_clause.values() if flags["supported"])
    reference_backed = sum(1 for flags in by_clause.values() if flags["reference_backed"])
    report: dict[str, object] = {
        "total": len(by_clause),
        "supported": supported,
        "unsupported": len(by_clause) - supported,
        "reference_backed": reference_backed,
        "by_clause": by_clause,
    }
    try:
        observability.evidence(
            checked=report["total"],
            supported=report["supported"],
            unsupported=report["unsupported"],
        )
    except Exception:  # noqa: BLE001 — observability must never break analysis
        pass
    return report


def verify_analysis_evidence(clauses: Iterable) -> dict[str, object]:
    """Aggregate evidence report for analyzed clauses (IDs only, never text)."""
    by_clause = {c.clause_id: analysis_clause_evidence(c) for c in clauses}
    return _aggregate(by_clause)


def verify_payload_evidence(clauses: Iterable[Mapping]) -> dict[str, object]:
    """Aggregate evidence report for stored clause dictionaries."""
    by_clause: dict[str, dict[str, bool]] = {}
    for index, clause in enumerate(clauses):
        clause_id = str(clause.get("clause_id") or f"clause_{index + 1}")
        by_clause[clause_id] = payload_clause_evidence(clause)
    return _aggregate(by_clause)

