"""Version-to-version clause comparison for ClauseGuard.

Given two versions of a contract (``old`` then ``new``), determine at clause
level which clauses are:

* ``unchanged`` — text + category are deterministically identical;
* ``modified``   — the pair matched but the value that matters changed
  (e.g. notice period ``30 days -> 60 days``);
* ``added``      — present only in the new version;
* ``removed``    — present only in the old version;
* ``ambiguous``  — two+ strong candidate pairs tie; caller may opt-in to
  LLM/semantic disambiguation (never required).

Design contract (mirrors ``app.cross_clause``):

* the *deterministic* path is always available and always theorem-counted:
  it performs **zero** ``chat()`` calls, and each detected change is backed by
  the two real clause IDs and their normalized canonical values — never an
  LLM narrative and never clause text leaking into observability;
* ``semantic`` (an embedding/retrieval callable) and ``llm_classify`` (a
  structured-output callable) are *optional* and only consulted when the
  deterministic layers cannot decide a pair — i.e. we never run
  ``N x N x LLM``; the candidate set is bounded by deterministic structure;
* ``llm_calls`` and ``semantic_pairs_scanned`` are always surfaced so callers
  can prove that deterministic comparisons (e.g. ``30 days -> 60 days``) made
  **zero** LLM calls.

This mirrors ``app.cross_clause.detect`` in shape so downstream routing and
tests treat the two engines uniformly.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from app.schemas import (
    AttentionEvolutionOut,
    CLAUSE_CATEGORIES,
    ExtractedClause,
    VersionChangeOut,
    VersionComparisonReportOut,
)

UNCHANGED = "unchanged"
MODIFIED = "modified"
ADDED = "added"
REMOVED = "removed"
AMBIGUOUS = "ambiguous"

# Deterministic change-kind detectors: (canonical kind, regex, human label).
# Numeric rules capture ``(number, unit)`` so the shipped values keep their
# unit ("12 months" -> "24 months"); the amount rule captures the written
# amount in one group. The report states neutral value evolution, never a
# legal better/worse verdict.
_VALUE_RULES: list[tuple[str, str, str]] = [
    (
        "notice_period",
        r"(\d{1,4})\s*[-\s]\s*(?:calendar\s+)?(days?|weeks?|months?)['’]?\s*"
        r"(?:(?:prior|written)\s+)?notice",
        "notice period",
    ),
    (
        "payment_period",
        r"pay(?:ment)?\s+(?:within|in)\s+(\d{1,4})\s*(days?|weeks?|months?)",
        "payment period",
    ),
    (
        "duration",
        r"(?:term|agreement|contract)\s+lasts?\s+(\d{1,4})\s*(months?|years?)",
        "duration",
    ),
    (
        "renewal",
        r"renew(?:al)?\s+(?:period\s+of\s+|after\s+|every\s+)?(\d{1,4})\s*(months?|years?)",
        "renewal",
    ),
    ("amount", r"((?:INR|Rs\.?|₹)\s?[\d,]+(?:\s*\.\d+)?)", "amount"),
]


def _normalize(text: str) -> str:
    """Canonical folded text used only to prove equality — never exported."""
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _category_of(category: str) -> str:
    """Map any category label onto the canonical taxonomy ('Other' when unknown)."""
    cat = (category or "").strip()
    for c in CLAUSE_CATEGORIES:
        if cat.lower() == c.lower():
            return c
    if cat:
        return "Other"
    return "Other"


def _label_of(category: str) -> str:
    """Human label for the report: keep the provider's label, default to Other.

    Matching for *pairing* still uses ``_category_of`` so fuzzy labels pair
    correctly, but the shipped report should not throw away useful detail.
    """
    return (category or "").strip() or "Other"


def _display_value(match: re.Match, kind: str) -> str:
    if kind == "amount":
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return f"{int(match.group(1))} {match.group(2).lower()}"


def _canonical_value(match: re.Match, kind: str) -> str:
    """Comparable form: 12 months == 1 year, but 30 days != 30 months."""
    if kind == "amount":
        raw = re.sub(r"[,\s]", "", match.group(1).lower())
        return raw.replace("rs.", "inr").replace("rs", "inr")
    count = int(match.group(1))
    unit = match.group(2).lower().rstrip("s")
    if unit == "year":
        return f"months:{count * 12}"
    if unit == "month":
        return f"months:{count}"
    return f"{unit}:{count}"


def _value_delta(text_a: str, text_b: str) -> Optional[dict]:
    """Deterministic value-level change detection (e.g. 30 days -> 60 days)."""
    for kind, pattern, label in _VALUE_RULES:
        m_a = re.search(pattern, text_a, flags=re.IGNORECASE)
        m_b = re.search(pattern, text_b, flags=re.IGNORECASE)
        if not (m_a and m_b):
            continue
        if _canonical_value(m_a, kind) == _canonical_value(m_b, kind):
            continue
        return {
            "kind": kind,
            "label": label,
            "previous_value": _display_value(m_a, kind),
            "current_value": _display_value(m_b, kind),
        }
    return None


def _text_similarity(text_a: str, text_b: str) -> float:
    """Deterministic, zero-LLM similarity used to disambiguate candidates."""
    return difflib.SequenceMatcher(None, _normalize(text_a), _normalize(text_b)).ratio()


# ----------------------------------------------------------------- dataclasses
@dataclass(frozen=True)
class VersionChange:
    """One grounded clause-level change between version A and version B.

    ``previous_value``/``current_value`` are the canonically-normalized values
    when a deterministic value shift was detected (e.g. ``30 days`` ->
    ``60 days``); otherwise they are empty strings and the caller should treat
    the change as identity-based (added/removed) rather than value-based.
    """

    clause_id_b: str = ""
    clause_id_a: str = ""
    category: str = ""
    change_type: str = UNCHANGED  # unchanged | modified | added | removed | ambiguous
    previous_value: str = ""
    current_value: str = ""
    explanation: str = ""


@dataclass(frozen=True)
class AttentionEvolution:
    """How a matched clause's attention/risk changed across versions.

    Attention levels are the canonical risk bands already used by the ranker
    (red/yellow/green) — this is an *observation* of the engine's own signal
    changing across versions, never a legal better/worse verdict.
    """

    clause_id: str
    category: str
    previous_attention: str = "unknown"
    current_attention: str = "unknown"
    evolution: str = "unknown"  # new | removed | increased | decreased | unchanged


@dataclass(frozen=True)
class VersionComparisonReport:
    version_a: str = ""
    version_b: str = ""
    changes: list[VersionChange] = field(default_factory=list)
    attention_evolution: list[AttentionEvolution] = field(default_factory=list)
    clauses_a: int = 0
    clauses_b: int = 0
    candidate_pairs: int = 0
    matched_pairs: int = 0
    ambiguous_pairs: int = 0
    llm_calls: int = 0
    semantic_pairs_scanned: int = 0
    feedback: str = ""

    def to_dict(self) -> dict:
        return {
            "version_a": self.version_a,
            "version_b": self.version_b,
            "changes": [c.__dict__ for c in self.changes],
            "attention_evolution": [e.__dict__ for e in self.attention_evolution],
            "clauses_a": self.clauses_a,
            "clauses_b": self.clauses_b,
            "candidate_pairs": self.candidate_pairs,
            "matched_pairs": self.matched_pairs,
            "ambiguous_pairs": self.ambiguous_pairs,
            "llm_calls": self.llm_calls,
            "semantic_pairs_scanned": self.semantic_pairs_scanned,
            "feedback": self.feedback,
        }


# ------------------------------------------------------------ public detect
def detect(
    old: Sequence[ExtractedClause],
    new: Sequence[ExtractedClause],
    *,
    version_a: str = "",
    version_b: str = "",
    semantic: Optional[Callable[[str, str], float]] = None,
    semantic_threshold: float = 0.72,
    llm_classify: Optional[Callable[[str, str], Optional[dict]]] = None,
) -> VersionComparisonReport:
    """Deterministic clause-level comparison: old version vs new version.

    Layers, in order:

    1. structural identity — normalized text (same category first, then a
       re-categorised but otherwise identical section);
    2. matched pairs — deterministic value changes first, then single
       candidates, then zero-LLM text similarity for near-duplicate wording;
    3. optional semantic/LLM — only genuinely ambiguous pairs are offered to
       the injected callables; never an N x N LLM scan.

    ``llm_calls`` is 0 unless the caller supplies ``llm_classify`` AND a pair
    is actually ambiguous — the deterministic path (including ``30 days ->
    60 days`` value changes) always reports ``llm_calls == 0``.
    """
    changes: list[VersionChange] = []
    attention: list[AttentionEvolution] = []
    candidate_pairs = 0
    ambiguous_pairs = 0
    llm_calls = 0
    semantic_scanned = 0

    # Exact-wording index used before any category-based candidate search.
    new_by_text: dict[str, list[ExtractedClause]] = {}
    for c in new:
        new_by_text.setdefault(_normalize(c.text), []).append(c)

    consumed_new: set[str] = set()

    for c_old in old:
        exact = [
            c for c in new_by_text.get(_normalize(c_old.text), [])
            if c.clause_id not in consumed_new
        ]
        same_category_exact = [
            c for c in exact
            if _category_of(c.category) == _category_of(c_old.category)
        ]
        if same_category_exact:
            c_new = same_category_exact[0]
            consumed_new.add(c_new.clause_id)
            changes.append(
                VersionChange(
                    clause_id_a=c_old.clause_id,
                    clause_id_b=c_new.clause_id,
                    category=_label_of(c_old.category),
                    change_type=UNCHANGED,
                    explanation="Clause is unchanged across versions.",
                )
            )
            continue
        if exact:
            # Same wording under a different topic is a real revision, not a
            # removal-plus-addition pair.
            c_new = exact[0]
            consumed_new.add(c_new.clause_id)
            changes.append(
                VersionChange(
                    clause_id_a=c_old.clause_id,
                    clause_id_b=c_new.clause_id,
                    category=_label_of(c_old.category),
                    change_type=MODIFIED,
                    explanation=(
                        "The wording is the same but the section topic changed "
                        f"from {_label_of(c_old.category)} to {_label_of(c_new.category)}."
                    ),
                )
            )
            continue

        # Same canonical category, different text -> potential modification.
        candidates = [
            c for c in new
            if c.clause_id not in consumed_new
            and _category_of(c.category) == _category_of(c_old.category)
        ]
        candidate_pairs += len(candidates)
        if not candidates:
            changes.append(
                VersionChange(
                    clause_id_a=c_old.clause_id,
                    category=_label_of(c_old.category),
                    change_type=REMOVED,
                    explanation="Clause is present only in the old version.",
                )
            )
            continue

        # Deterministic tie-break candidate: value-level evidence first.
        delta = None
        best = None
        for cand in candidates:
            d = _value_delta(c_old.text, cand.text)
            if d is not None:
                delta = d
                best = cand
                break
        if delta is not None and best is not None:
            consumed_new.add(best.clause_id)
            changes.append(
                VersionChange(
                    clause_id_a=c_old.clause_id,
                    clause_id_b=best.clause_id,
                    category=_label_of(c_old.category),
                    change_type=MODIFIED,
                    previous_value=delta["previous_value"],
                    current_value=delta["current_value"],
                    explanation=(
                        f"The {delta['label']} changed from {delta['previous_value']} "
                        f"to {delta['current_value']}."
                    ),
                )
            )
            continue
        if len(candidates) == 1:
            best = candidates[0]
            consumed_new.add(best.clause_id)
            changes.append(
                VersionChange(
                    clause_id_a=c_old.clause_id,
                    clause_id_b=best.clause_id,
                    category=_label_of(c_old.category),
                    change_type=MODIFIED,
                    explanation=(
                        f"The {_category_of(c_old.category).lower()} clause was revised "
                        "across versions (no single value changed deterministically)."
                    ),
                )
            )
            continue

        # More than one plausible target: deterministic wording similarity can
        # settle most of these without a model call. Only a genuine tie is
        # offered to the opt-in callables (never N x N).
        scored = sorted(
            ((_text_similarity(c_old.text, c.text), c) for c in candidates),
            key=lambda item: item[0],
            reverse=True,
        )
        best_sim, best = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        if best is not None and best_sim >= 0.55 and best_sim - runner_up >= 0.02:
            consumed_new.add(best.clause_id)
            changes.append(
                VersionChange(
                    clause_id_a=c_old.clause_id,
                    clause_id_b=best.clause_id,
                    category=_label_of(c_old.category),
                    change_type=MODIFIED,
                    explanation=(
                        "Clause matched the closest wording among several "
                        f"candidates (text similarity {round(best_sim, 2)})."
                    ),
                )
            )
            continue

        ambiguous_pairs += 1
        if semantic is not None:
            best = None
            best_sim = -1.0
            for cand in candidates:
                semantic_scanned += 1
                try:
                    sim = float(semantic(c_old.text, cand.text) or 0.0)
                except Exception:  # noqa: BLE001 — semantic is best-effort
                    sim = 0.0
                if sim > best_sim:
                    best_sim, best = sim, cand
            if best is not None and best_sim >= semantic_threshold:
                consumed_new.add(best.clause_id)
                changes.append(
                    VersionChange(
                        clause_id_a=c_old.clause_id,
                        clause_id_b=best.clause_id,
                        category=_label_of(c_old.category),
                        change_type=MODIFIED,
                        explanation=(
                            f"Clause matched its nearest candidate "
                            f"(semantic score {round(best_sim, 2)})."
                        ),
                    )
                )
                continue
        if llm_classify is not None:
            llm_calls += 1
            try:
                verdict = llm_classify(c_old.text, ",".join(c.text for c in candidates)) or {}
                target_id = verdict.get("target_clause_id", "")
                target = next((c for c in candidates if c.clause_id == target_id), None)
                if target is not None:
                    consumed_new.add(target.clause_id)
                    changes.append(
                        VersionChange(
                            clause_id_a=c_old.clause_id,
                            clause_id_b=target.clause_id,
                            category=_label_of(c_old.category),
                            change_type=MODIFIED,
                            explanation=(
                                verdict.get("explanation")
                                or "Clause matched via LLM-disambiguated pair."
                            ),
                        )
                    )
                    continue
            except Exception:  # noqa: BLE001 — a bad LLM verdict falls back
                pass
        # Still unresolved. Report the ambiguity honestly instead of
        # pretending the old section vanished and the new one appeared.
        changes.append(
            VersionChange(
                clause_id_a=c_old.clause_id,
                category=_label_of(c_old.category),
                change_type=AMBIGUOUS,
                explanation=(
                    "This section had more than one possible match in the newer "
                    "version, so it needs a manual check."
                ),
            )
        )

    # Anything not consumed in the new version -> added.
    consumed_new_ids = consumed_new
    for c in new:
        if c.clause_id in consumed_new_ids:
            continue
        changes.append(
            VersionChange(
                clause_id_b=c.clause_id,
                category=_label_of(c.category),
                change_type=ADDED,
                explanation="Clause is present only in the new version.",
            )
        )

    matched_pairs = sum(1 for c in changes if c.change_type in (UNCHANGED, MODIFIED))

    # Attention evolution for matched clauses (canonical risk bands only).
    for c in changes:
        if c.change_type == UNCHANGED:
            attention.append(
                AttentionEvolution(
                    clause_id=c.clause_id_b or c.clause_id_a,
                    category=c.category,
                    previous_attention=_band(c.clause_id_a, old),
                    current_attention=_band(c.clause_id_b, new),
                    evolution=_evolution(c.clause_id_a, c.clause_id_b, old, new),
                )
            )
        elif c.change_type == MODIFIED:
            attention.append(
                AttentionEvolution(
                    clause_id=c.clause_id_b or c.clause_id_a,
                    category=c.category,
                    previous_attention=_band(c.clause_id_a, old),
                    current_attention=_band(c.clause_id_b, new),
                    evolution=_evolution(c.clause_id_a, c.clause_id_b, old, new),
                )
            )
        elif c.change_type == ADDED:
            attention.append(
                AttentionEvolution(
                    clause_id=c.clause_id_b,
                    category=c.category,
                    current_attention=_band(c.clause_id_b, new),
                    evolution="new",
                )
            )
        elif c.change_type == REMOVED:
            attention.append(
                AttentionEvolution(
                    clause_id=c.clause_id_a,
                    category=c.category,
                    previous_attention=_band(c.clause_id_a, old),
                    evolution="removed",
                )
            )
        elif c.change_type == AMBIGUOUS:
            attention.append(
                AttentionEvolution(
                    clause_id=c.clause_id_a,
                    category=c.category,
                    previous_attention=_band(c.clause_id_a, old),
                    evolution="unknown",
                )
            )

    n_unchanged = sum(1 for c in changes if c.change_type == UNCHANGED)
    n_modified = sum(1 for c in changes if c.change_type == MODIFIED)
    n_added = sum(1 for c in changes if c.change_type == ADDED)
    n_removed = sum(1 for c in changes if c.change_type == REMOVED)
    n_ambiguous = sum(1 for c in changes if c.change_type == AMBIGUOUS)

    # ``changes`` is the *actionable* diff: unchanged clauses are counted in the
    # feedback/attention sections but are not shipped as changes, so consumers
    # only render terms that actually moved.
    reported_changes = [c for c in changes if c.change_type != UNCHANGED]

    feedback = (
        f"{n_unchanged} unchanged, {n_modified} modified, "
        f"{n_added} added, {n_removed} removed, {n_ambiguous} needing a manual "
        f"check — {llm_calls} LLM call(s) ({ambiguous_pairs} ambiguous pair(s))."
    )

    return VersionComparisonReport(
        version_a=version_a,
        version_b=version_b,
        changes=reported_changes,
        attention_evolution=attention,
        clauses_a=len(old),
        clauses_b=len(new),
        candidate_pairs=candidate_pairs,
        matched_pairs=matched_pairs,
        ambiguous_pairs=ambiguous_pairs,
        llm_calls=llm_calls,
        semantic_pairs_scanned=semantic_scanned,
        feedback=feedback,
    )


# ----------------------------------------------------------- attention bands
def _band(
    clause_id: str,
    clauses: Sequence[ExtractedClause],
    fallback: Optional[Sequence[ExtractedClause]] = None,
) -> str:
    if not clause_id:
        return "unknown"
    for c in clauses:
        if c.clause_id == clause_id:
            return _risk_band(c)
    if fallback is not None:
        for c in fallback:
            if c.clause_id == clause_id:
                return _risk_band(c)
    return "unknown"


def _risk_band(clause: ExtractedClause) -> str:
    from app.schemas import AnalyzedClause, LLMClause, RiskLevel  # noqa: PLC0415

    rl = getattr(clause, "risk_level", None) or getattr(clause, "risk_score", None)
    if rl is None:
        return "unknown"
    if isinstance(rl, str) and rl in ("red", "yellow", "green"):
        return rl
    if isinstance(rl, (int, float)):
        return "red" if rl >= 80 else "yellow" if rl >= 50 else "green"
    return "unknown"


# ------------------------------------------------------------- wire mapping
def to_out(report: VersionComparisonReport) -> VersionComparisonReportOut:
    """Map the engine report onto the exact wire schema the API ships.

    1:1 field mapping — every clause-id/category/value is carried, never an LLM
    verdict and never clause text leaking into observability.
    """
    return VersionComparisonReportOut(
        version_a=report.version_a,
        version_b=report.version_b,
        changes=[
            VersionChangeOut(
                clause_id_a=c.clause_id_a,
                clause_id_b=c.clause_id_b,
                category=c.category,
                change_type=c.change_type,
                previous_value=c.previous_value,
                current_value=c.current_value,
                explanation=c.explanation,
            )
            for c in report.changes
        ],
        attention_evolution=[
            AttentionEvolutionOut(
                clause_id=e.clause_id,
                category=e.category,
                previous_attention=e.previous_attention,
                current_attention=e.current_attention,
                evolution=e.evolution,
            )
            for e in report.attention_evolution
        ],
        clauses_a=report.clauses_a,
        clauses_b=report.clauses_b,
        candidate_pairs=report.candidate_pairs,
        matched_pairs=report.matched_pairs,
        ambiguous_pairs=report.ambiguous_pairs,
        llm_calls=report.llm_calls,
        semantic_pairs_scanned=report.semantic_pairs_scanned,
        feedback=report.feedback,
    )


def _evolution(clause_id_a: str, clause_id_b: str, old, new) -> str:
    a = _band(clause_id_a, old)
    b = _band(clause_id_b, new)
    order = {"green": 0, "yellow": 1, "red": 2}
    if a not in order or b not in order:
        # No comparable risk signal on one side => attention is unchanged as far
        # as the engine can observe (the raw bands are still reported).
        return "unchanged"
    if order[b] > order[a]:
        return "increased"
    if order[b] < order[a]:
        return "decreased"
    return "unchanged"
