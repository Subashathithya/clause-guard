"""Deterministic helpers for Phase 4 dates and negotiation checklists.

Nothing here calls an LLM. Date suggestions only surface *explicit calendar
dates* written in the contract (e.g. "1 January 2027"); relative wording such
as "within 30 days" is deliberately not turned into a date, because there is no
reliable anchor to resolve it from. Users decide which suggestions to keep.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable

# Long and short month names, mapped to 1..12.
_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
_MONTH_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))

# "1 January 2027" / "1st Jan 2027"
_DMY = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_PATTERN})\.?,?\s+(\d{{4}})\b",
    re.IGNORECASE,
)
# "January 1, 2027" / "Jan 1st 2027"
_MDY = re.compile(
    rf"\b({_MONTH_PATTERN})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b",
    re.IGNORECASE,
)
# "2027-01-01"
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

_KIND_BY_CATEGORY = {
    "Payment": "payment",
    "Auto-Renewal": "renewal",
    "Dispute": "other",
    "Liability": "other",
    "Data Privacy": "other",
    "Warranty": "other",
    "Other": "other",
}

_KIND_HINTS = (
    (re.compile(r"\brenew", re.IGNORECASE), "renewal"),
    (re.compile(r"\bnotice\b", re.IGNORECASE), "notice"),
    (re.compile(r"\bterminat", re.IGNORECASE), "termination"),
    (re.compile(r"\bcancel", re.IGNORECASE), "termination"),
    (re.compile(r"\bpayment\b", re.IGNORECASE), "payment"),
    (re.compile(r"\bpay\b", re.IGNORECASE), "payment"),
    (re.compile(r"\brent\b", re.IGNORECASE), "payment"),
    (re.compile(r"\bfee\b", re.IGNORECASE), "payment"),
    (re.compile(r"\binvoice\b", re.IGNORECASE), "payment"),
    (re.compile(r"\bdue\b", re.IGNORECASE), "payment"),
)


def _kind_for(category: str, text: str, position: int) -> str:
    """Pick the kind from whichever clue sits closest to the matched date."""
    best: tuple[int, str] | None = None
    for pattern, kind in _KIND_HINTS:
        for match in pattern.finditer(text):
            distance = abs(match.start() - position)
            if best is None or distance < best[0]:
                best = (distance, kind)
    if best is not None and best[0] <= 80:
        return best[1]
    return _KIND_BY_CATEGORY.get(category, "other")


def _safe_date(year: int, month: int, day: int) -> date | None:
    if not (1950 <= year <= 2100):
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _explicit_dates(text: str) -> list[tuple[date, int]]:
    """Explicit calendar dates with the offset where each match starts."""
    found: list[tuple[date, int]] = []
    for match in _DMY.finditer(text):
        day, month_name, year = match.groups()
        d = _safe_date(int(year), _MONTHS[month_name.lower()], int(day))
        if d:
            found.append((d, match.start()))
    for match in _MDY.finditer(text):
        month_name, day, year = match.groups()
        d = _safe_date(int(year), _MONTHS[month_name.lower()], int(day))
        if d:
            found.append((d, match.start()))
    for match in _ISO.finditer(text):
        year, month, day = match.groups()
        d = _safe_date(int(year), int(month), int(day))
        if d:
            found.append((d, match.start()))
    found.sort(key=lambda row: row[1])
    return found


def suggest_dates(clauses: Iterable[dict]) -> list[dict]:
    """Return explicit dates found in clause text, for the user to consider.

    Suggestions are informational: the caller decides whether to add them.
    """
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        text = str(clause.get("text") or "")
        clause_id = str(clause.get("clause_id") or "")
        category = str(clause.get("category") or "Other")
        for found, position in _explicit_dates(text):
            key = (clause_id, found.isoformat())
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "date": found.isoformat(),
                    "label": f"Date mentioned in the {category} section",
                    "kind": _kind_for(category, text, position),
                    "clause_id": clause_id or None,
                    "clause_index": clause_id or None,
                    "context": text[:240],
                }
            )
    out.sort(key=lambda row: (row["date"], row["label"]))
    return out
