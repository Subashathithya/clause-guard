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

from collections.abc import Callable, Iterable
from typing import Optional

from app.observability import observability
from app.schemas import CLAUSE_CATEGORIES, ExtractedClause

__all__ = [
    "clause_text_nonempty",
    "category_valid",
    "reference_clause_id",
    "evidence_for_clause",
    "verify_evidence",
]


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
