"""Agent 3 — Risk Ranker.

Assigns a Red/Yellow/Green risk level from the Comparator's similarity score and
produces a plain-English explanation and quantified financial impact.

Mapping (from specifications):
    similarity > 85%  -> Green   (risk < 25%)
    70% <= similarity <= 85% -> Yellow (risk 40–70%)
    similarity < 70%  -> Red    (risk > 75%)

The LLM receives the provisional similarity-based verdict as a strong prior and
refines the explanation + financial impact. If the LLM call fails, the
deterministic threshold verdict is used, so scoring never fails.
"""
import logging

from app import llm
from app.schemas import (
    ComparisonResult,
    ExtractedClause,
    LLMRankOutput,
    RankerOutput,
)
from app.settings import settings

logger = logging.getLogger(__name__)

SIMILARITY_GREEN = 0.85
SIMILARITY_YELLOW = 0.70

LEVEL_WEIGHT = {
    "green": 20,   # < 25% risk
    "yellow": 55,  # 40–70% risk
    "red": 85,     # > 75% risk
}


def _provisional_risk(similarity: float) -> str:
    if similarity >= SIMILARITY_GREEN:
        return "green"
    if similarity >= SIMILARITY_YELLOW:
        return "yellow"
    return "red"


def _level_from_score(score: int) -> str:
    if score >= 67:
        return "red"
    if score >= 34:
        return "yellow"
    return "green"


def _to_int(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


class RankAgent:
    """Agent 3: score risk and explain it in plain English."""

    name = "Ranker"

    SYSTEM = (
        "You are Agent 3 (Ranker) in a contract-analysis pipeline. You explain how risky "
        "a clause is for a typical consumer in plain English (no legal jargon), quantify "
        "the plausible financial exposure in Indian Rupees, and give a 0-100 risk score. "
        "Higher risk_score means more dangerous to the consumer. "
        "Always return your output as a single valid JSON object."
    )

    def rank(
        self,
        clause: ExtractedClause,
        comparison: ComparisonResult,
        include_reference: bool = True,
    ) -> RankerOutput:
        """Return risk assessment informed by the fair-clause similarity.

        `include_reference=False` runs the ablation variant (plain-LLM scoring
        with no RAG reference / similarity injected) so experiments can measure
        how much the comparator contributes to accuracy.
        """
        similarity = comparison.similarity
        provisional = _provisional_risk(similarity)
        reference = comparison.reference_clause or "(no close industry-standard reference found)"

        if include_reference:
            grounding = f"""NEAREST FAIR/INDUSTRY-STANDARD REFERENCE (similarity {similarity * 100:.0f}%):
\"\"\"{reference}\"\"\"

Similarity mapping used by the system:
  >85% -> green, 70-85% -> yellow, <70% -> red.
Provisionally this clause maps to: {provisional.upper()}.

Confirm or adjust the risk based on how the clause compares to the fair
reference above, then explain why."""
        else:
            grounding = (
                "Score the clause purely from its text, with no external standard "
                "to compare against, then explain why."
            )

        prompt = f"""CLAUSE CATEGORY: {clause.category}
CLAUSE TEXT:
\"\"\"{clause.text}\"\"\"

{grounding}

Also give a realistic rupee (₹) financial impact figure. Be specific, not generic.

Return ONLY JSON:
{{
  "risk_level": "red|yellow|green",
  "risk_score": <0-100 integer>,
  "explanation": "<2-4 sentence plain-English explanation a non-lawyer understands>",
  "financial_impact": "<concise description of potential rupee impact, or 'None identified'>",
  "financial_impact_inr": <integer estimated rupees, 0 if none>
}}"""
        try:
            validated_data, _ = llm.chat_json_validated(
                [
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                model=settings.PRIMARY_MODEL,
                temperature=0.1,
                schema=LLMRankOutput,
            )
            if validated_data is None:
                raise ValueError("LLM returned no valid rank output")
            score = max(0, min(100, int(validated_data.risk_score)))
            level = str(validated_data.risk_level).lower()
            if level not in ("red", "yellow", "green"):
                level = _level_from_score(score)
            return RankerOutput(
                risk_level=level,
                risk_score=score,
                risk_percentage=score,
                explanation=str(validated_data.explanation or "").strip(),
                financial_impact=str(validated_data.financial_impact or "None identified").strip(),
                financial_impact_inr=_to_int(validated_data.financial_impact_inr),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ranker LLM call failed (%s); using similarity fallback", exc)
            score = LEVEL_WEIGHT[provisional]
            explanation = (
                f"This clause has only {similarity * 100:.0f}% similarity to a fair "
                f"industry-standard reference, so it is rated {provisional.upper()}."
            )
            return RankerOutput(
                risk_level=provisional,
                risk_score=score,
                risk_percentage=score,
                explanation=explanation,
                financial_impact="None identified",
                financial_impact_inr=None,
            )