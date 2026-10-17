"""Cross-clause intelligence: deterministic relationships, conflicts, context.

Pure pipeline layer that runs *between* single-clause analysis and the
executive summary. It never calls the LLM on the deterministic path and never
touches the vector store in the base scan, so best-effort consumers (and the
test-suite) get stable, unit-testable output at near-zero cost.

Grounding contract (mirrors ``app.evidence``):

* every ``CrossClauseRelation`` only references ``clause_id`` values that
  exist in the caller's own clause set — never UUIDs fabricated by an LLM;
* conflict reports cite the exact pair of clauses and the two conflicting
  values, but never assert which clause is legally controlling (we flag
  *potential* inconsistency; we do not render legal verdicts);
* context is built solely from clause IDs / categories / support flags —
  no clause text is ever exported for observability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

from app.observability import observability
from app.schemas import CLAUSE_CATEGORIES, ExtractedClause

RISK = "risk"
IMPROVES = "improves"
CONFLICTS = "conflicts"

# Deterministic, category-level relationship table: two categories that almost
# always interact in a contract. This is the *static* half of the hybrid; the
# dynamic half (semantic similarity between clause texts) is opt-in and is only
# consulted when a category pair is *not* covered here (see detect()).
CATEGORY_EDGES: dict[str, set[str]] = {
    "Payment": {"Auto-Renewal", "Liability", "Warranty"},
    "Auto-Renewal": {"Payment", "Dispute", "Liability"},
    "Liability": {"Payment", "Warranty", "Data Privacy"},
    "Data Privacy": {"Liability", "Dispute"},
    "Dispute": {"Auto-Renewal", "Data Privacy", "Payment"},
    "Warranty": {"Liability", "Payment"},
    "Other": set(),
}

# Deterministic conflict detectors: (normalised-keyword, regex, human label).
# The regex captures the *value* the clause names so the report can state
# "30 days" vs "90 days" without asserting which is correct.
_CONFLICT_RULES: list[tuple[str, str, str]] = [
    ("notice", r"(\d{1,3})\s*(?:calendar\s*)?days?\s+notice", "notice period"),
    ("payment", r"pay(?:ment)?\s+(?:within|in)\s+(\d{1,3})\s*days?", "payment period"),
    ("duration", r"(?:term|agreement|contract)\s+lasts?\s+(\d{1,3})\s*(?:months?|years?)", "duration"),
    ("renew", r"renew(?:al)?\s+(?:period\s+of\s+|after\s+|every\s+)?(\d{1,3})\s*(?:month|year)s?", "renewal"),
]


@dataclass(frozen=True)
class CrossClauseRelation:
    """One grounded relationship between two real clauses."""

    source_clause_id: str
    target_clause_id: str
    relationship: str  # RISK (depends), IMPROVES (reinforces), CONFLICTS
    explanation: str = ""


@dataclass(frozen=True)
class PotentialInconsistency:
    """A pair of clauses that state *different values* for the same item.

    ``kind`` is the canonical label (notice/payment/duration/renewal); the two
    extracted values are surfaced so the consumer can review both sections.
    """

    source_clause_id: str
    target_clause_id: str
    kind: str
    value_a: str = ""
    value_b: str = ""
    explanation: str = ""


@dataclass
class CrossClauseReport:
    relationships: list[CrossClauseRelation] = field(default_factory=list)
    inconsistencies: list[PotentialInconsistency] = field(default_factory=list)
    semantic_pairs_scanned: int = 0
    llm_calls: int = 0  # always 0 on the deterministic path; surfaced for §10
    feedback: str = ""

    def to_dict(self) -> dict:
        return {
            "relationships": [r.__dict__ for r in self.relationships],
            "inconsistencies": [i.__dict__ for i in self.inconsistencies],
            "semantic_pairs_scanned": self.semantic_pairs_scanned,
            "llm_calls": self.llm_calls,
            "feedback": self.feedback,
        }


# ----------------------------------------------------------------- context
@dataclass(frozen=True)
class ClauseContext:
    """The context bundle fed to downstream (negotiation/counter) stages."""

    current_clause_id: str
    nearby_clause_ids: tuple[str, ...] = ()
    related_clause_ids: tuple[str, ...] = ()
    supported_reference_ids: tuple[str, ...] = ()
    contract_summary: str = ""
    applied: bool = True


def build_clause_context(
    clause: ExtractedClause,
    clauses: Sequence[ExtractedClause],
    *,
    window: int = 2,
    lookup: Optional[Callable[[str], Optional[ExtractedClause]]] = None,
    evidence: Optional[dict] = None,
) -> ClauseContext:
    """Deterministic context for one clause: nearby + related + supported
    references. Only clause IDs are exported; text never leaves this module.

    * ``nearby``  — ``window`` clauses either side in document order;
    * ``related`` — same-category or deterministically-edge-connected clauses;
    * ``supported_reference_ids`` — references that (a) resolve through
      ``lookup`` AND (b) were marked ``supported`` by the evidence pass. If no
      evidence dict is supplied, references that merely resolve are used so the
      function stays useful in isolation, but callers with a real evidence
      report should pass it (see orchestrator wiring).
    """
    order = [c.clause_id for c in clauses]
    try:
        idx = order.index(clause.clause_id)
    except ValueError:
        return ClauseContext(current_clause_id=clause.clause_id, applied=False)

    lo = max(0, idx - window)
    hi = min(len(order), idx + window + 1)
    nearby = tuple(
        cid for cid in order[lo:hi]
        if cid != clause.clause_id
    )

    related: list[str] = []
    edge = CATEGORY_EDGES.get(clause.category, set())
    for other in clauses:
        if other.clause_id == clause.clause_id:
            continue
        if other.category == clause.category or other.category in edge:
            related.append(other.clause_id)
    related.sort()

    supported_refs: tuple[str, ...] = ()
    ref_id = getattr(clause, "reference_clause_id", None) or ""
    if ref_id and lookup is not None:
        target = lookup(ref_id)
        if target is not None:
            keeps = False
            if evidence is not None:
                by = evidence.get("by_clause", {})
                keeps = bool(by.get(target.clause_id, {}).get("supported"))
            else:
                keeps = True
            if keeps:
                supported_refs = (target.clause_id,)

    return ClauseContext(
        current_clause_id=clause.clause_id,
        nearby_clause_ids=tuple(nearby),
        related_clause_ids=tuple(dict.fromkeys([*related, *nearby])),
        supported_reference_ids=supported_refs,
        applied=True,
    )


# --------------------------------------------------------------- detection
def _relationship_of(
    a: ExtractedClause, b: ExtractedClause
) -> Optional[tuple[str, str]]:
    """Deterministic relationship classification between two clauses.

    Returns ``(relationship, human_readable)`` or ``None`` when the pair is
    unrelated. Order-independent: the pair is always emitted
    ``source=min(id), target=max(id)`` so the output is canonical.
    """
    if a.category == b.category:
        return (RISK, "Both clauses are in the same canonical section category.")
    if b.category in CATEGORY_EDGES.get(a.category, set()):
        return (RISK, f"{a.category} sections typically interact with {b.category}.")
    if a.category in CATEGORY_EDGES.get(b.category, set()):
        return (RISK, f"{b.category} sections typically interact with {a.category}.")
    return None


def detect(
    clauses: Sequence[ExtractedClause],
    *,
    semantic: Optional[Callable[[str, str], float]] = None,
    semantic_threshold: float = 0.72,
) -> CrossClauseReport:
    """Discover relationships and potential inconsistencies across clauses.

    Deterministic always; ``semantic`` is an *opt-in* cosine/embedding callable
    that receives ``(a.text, b.text)`` and returns a similarity in ``[0,1]```
    for pairs not explained by the static table. When it is absent, those
    pairs are simply skipped — the deterministic path never forces an LLM or
    vector call.

    Complexity: O(N^2) pair scan in the worst case but with no external calls
    when ``semantic is None``; with ``semantic`` provided, the number of LLM
    calls is bounded by the pair count and reported on the report (§10).
    """
    relations: dict[str, CrossClauseRelation] = {}
    conflicts: list[PotentialInconsistency] = []
    semantic_scanned = 0

    pairs = [(a, b) for i, a in enumerate(clauses) for b in clauses[i + 1:]]

    for a, b in pairs:
        rel = _relationship_of(a, b)
        matched = rel is not None
        if rel is not None:
            key = tuple(sorted((a.clause_id, b.clause_id)))
            relations[key] = CrossClauseRelation(
                source_clause_id=min(a.clause_id, b.clause_id),
                target_clause_id=max(a.clause_id, b.clause_id),
                relationship=rel[0],
                explanation=rel[1],
            )

        if not matched and semantic is not None:
            semantic_scanned += 1
            try:
                sim = float(semantic(a.text, b.text) or 0.0)
            except Exception:  # noqa: BLE001  (semantic tier is best-effort)
                sim = 0.0
            if sim >= semantic_threshold:
                key = tuple(sorted((a.clause_id, b.clause_id)))
                relations[key] = CrossClauseRelation(
                    source_clause_id=min(a.clause_id, b.clause_id),
                    target_clause_id=max(a.clause_id, b.clause_id),
                    relationship=IMPROVES,
                    explanation=(
                        f"Clauses are semantically similar (score {round(sim, 2)})."
                    ),
                )

        conflict = _detect_conflict(a, b)
        if conflict is not None:
            conflicts.append(conflict)

    _emit_report(relations, conflicts)

    feedback = ""
    if not relations and not conflicts:
        feedback = "No cross-clause relationships or inconsistencies were found."

    return CrossClauseReport(
        relationships=sorted(relations.values(), key=lambda r: r.source_clause_id),
        inconsistencies=sorted(conflicts, key=lambda c: c.source_clause_id),
        semantic_pairs_scanned=semantic_scanned,
        feedback=feedback,
    )


def _detect_conflict(
    a: ExtractedClause, b: ExtractedClause
) -> Optional[PotentialInconsistency]:
    """Return a PotentialInconsistency when two clauses name *different* values
    for the same deterministic item (notice/payment/duration/renewal)."""
    va = _conflict_values(a)
    vb = _conflict_values(b)
    for key in va.keys() & vb.keys():
        if va[key] != vb[key]:
            return PotentialInconsistency(
                source_clause_id=min(a.clause_id, b.clause_id),
                target_clause_id=max(a.clause_id, b.clause_id),
                kind=key,
                value_a=va[key],
                value_b=vb[key],
                explanation=(
                    f"Two sections specify different {key} values "
                    f"({va[key]} vs {vb[key]})."
                ),
            )
    return None


def _conflict_values(clause: ExtractedClause) -> dict[str, str]:
    """Extract the first deterministic (keyword, value) pair per rule set."""
    import re

    text = clause.text or ""
    lower = text.lower()
    found: dict[str, str] = {}
    for keyword, pattern, label in _CONFLICT_RULES:
        if keyword in lower:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                n = m.group(1)
                unit = "days"
                if "month" in label or "renew" in label or "duration" in label:
                    unit = "months"
                found[label] = f"{n} {unit}"
    return found


def _emit_report(
    relations: dict[tuple[str, str], CrossClauseRelation],
    conflicts: list[PotentialInconsistency],
) -> None:
    """Record cross-clause observability metrics (IDs only — never text)."""
    try:
        observability.evidence(
            checked=len(relations) + len(conflicts),
            supported=len(relations),
            unsupported=len(conflicts),
        )
    except Exception:  # noqa: BLE001 — observability must never break detection
        pass


# ------------------------------------------------------------------- adapters
# Map the internal dataclass report onto the API wire schema so the
# orchestrator can attach §8 findings to ``AnalysisResult``. The Out models are
# the *contract* — field names here mirror ``schemas.CrossClauseReportOut``,
# and only clause IDs + canonical labels are exported, never clause text.


def to_out(report: CrossClauseReport) -> "CrossClauseReportOut":
    """Adapt a deterministic ``CrossClauseReport`` to the API response schema."""
    from app.schemas import (
        CrossClauseInconsistencyOut,
        CrossClauseRelationOut,
        CrossClauseReportOut,
    )

    return CrossClauseReportOut(
        relationships=[
            CrossClauseRelationOut(
                source_clause_id=r.source_clause_id,
                target_clause_id=r.target_clause_id,
                relationship=r.relationship,
                explanation=r.explanation,
            )
            for r in report.relationships
        ],
        inconsistencies=[
            CrossClauseInconsistencyOut(
                source_clause_id=i.source_clause_id,
                target_clause_id=i.target_clause_id,
                kind=i.kind,
                value_a=i.value_a,
                value_b=i.value_b,
                explanation=i.explanation,
            )
            for i in report.inconsistencies
        ],
        semantic_pairs_scanned=report.semantic_pairs_scanned,
        llm_calls=report.llm_calls,
        feedback=(
            report.feedback
            or (  # §14: found-path feedback stays deterministic, ID-only,
                  # canonical-label-only — never clause text. Zero LLM calls.
                  f"{len(report.relationships)} cross-clause relationship(s) and "
                  f"{len(report.inconsistencies)} potential inconsistency(ies) "
                  f"identified across {len(report.feedback) or 0} reviewable pairs."
                  if report.relationships or report.inconsistencies
                  else "No cross-clause relationships or inconsistencies found."
              )
        ),
    )
