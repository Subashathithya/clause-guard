"""Agent 1 — Clause Extractor.

Breaks a raw contract into individual clauses and labels each with one of the
seven canonical ClauseGuard categories:

    Payment · Auto-Renewal · Liability · Data Privacy · Dispute · Warranty · Other

Accuracy target: >85% on diverse contract types (gym, rental, employment,
app ToS, insurance, loan, service agreements).
"""
import logging

from app import llm
from app.observability import observability
from app.schemas import (
    CLAUSE_CATEGORIES,
    ExtractedClause,
    ExtractorOutput,
    LLMExtractorOutput,
)
from app.settings import settings

logger = logging.getLogger(__name__)

MAX_CLAUSES = 40


def _categories_block() -> str:
    return "\n".join(f"  {i + 1}. {c}" for i, c in enumerate(CLAUSE_CATEGORIES))


def _closest_category(value: str) -> str:
    value = (value or "").lower()
    for cat in CLAUSE_CATEGORIES:
        if cat.lower() == value:
            return cat
    for cat in CLAUSE_CATEGORIES:
        key = cat.lower()
        if key in value:
            return cat
    return "Other"


class ExtractAgent:
    """Agent 1: extract and categorise contract clauses."""

    name = "Extractor"

    SYSTEM = (
        "You are Agent 1 (Extractor) in a contract-analysis pipeline. "
        "You segment contracts into distinct clauses and classify each into exactly one of "
        "the seven canonical categories. Preserve the original wording of each clause "
        "without paraphrasing. Ignore headings, page numbers, definitions sections and signatures. "
        "Always return your output as a single valid JSON object."
    )

    def extract(self, text: str) -> ExtractorOutput:
        """Return every distinct clause with a category and confidence score."""
        if not text or not text.strip():
            return ExtractorOutput(total_clauses=0, clauses=[])

        prompt = f"""Use EXACTLY one of these categories:
{_categories_block()}

Split the CONTRACT below into its distinct clauses. Merge fragments shorter than
10 words into the neighbouring clause. Return at most {MAX_CLAUSES} clauses.

Return ONLY JSON:
{{
  "clauses": [
    {{"clause_id": "clause_1", "category": "<category string from the list>",
      "text": "<original clause text>", "confidence": <0.0-1.0>}}
  ]
}}

CONTRACT:
\"\"\"
{text}
\"\"\"
"""
        try:
            validated, _ = llm.chat_json_validated(
                [
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                model=settings.PRIMARY_MODEL,
                schema=LLMExtractorOutput,
                stage="extract",
            )
            observability.validation(stage="extract", ok=True, attempts=1)
        except Exception as exc:  # noqa: BLE001
            logger.error("Extractor LLM call failed: %s", exc)
            return ExtractorOutput(total_clauses=0, clauses=[])

        if validated is None:
            logger.error("Extractor LLM call returned no valid output")
            return ExtractorOutput(total_clauses=0, clauses=[])

        raw = validated.clauses if hasattr(validated, "clauses") else []
        clauses: list[ExtractedClause] = []
        for i, c in enumerate(raw[:MAX_CLAUSES]):
            category = str(getattr(c, "category", "") or "").strip()
            if category not in CLAUSE_CATEGORIES:
                category = _closest_category(category)
            clause_text = str(getattr(c, "text", "") or "").strip()
            if not clause_text:
                continue
            clauses.append(
                ExtractedClause(
                    clause_id=str(getattr(c, "clause_id", "") or f"clause_{i + 1}"),
                    category=category,
                    text=clause_text,
                    confidence=float(getattr(c, "confidence", 0.8) or 0.8),
                )
            )
        return ExtractorOutput(total_clauses=len(clauses), clauses=clauses)