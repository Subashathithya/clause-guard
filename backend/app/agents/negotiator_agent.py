"""Agent 4 — Negotiation Suggester.

For Red clauses: a concrete fair counter-clause, 3-5 talking points, an estimated
success probability and the reasoning behind it.
For Yellow clauses: the same, flagged as lower priority.
For Green clauses: returns "No negotiation needed" — the clause is standard.
"""
import logging

from app import llm
from app.schemas import (
    ComparisonResult,
    ExtractedClause,
    LLMNegotiationOutput,
    NegotiatorOutput,
    RankerOutput,
)
from app.settings import settings

logger = logging.getLogger(__name__)


class NegotiateAgent:
    """Agent 4: draft negotiation packs for risky clauses."""

    name = "Negotiator"

    SYSTEM = (
        "You are Agent 4 (Negotiator) in a contract-analysis pipeline. You draft balanced "
        "replacement clauses and practical negotiation talking points a consumer can use "
        "with the other party, estimate how likely a reasonable counterparty is to accept, "
        "and explain your reasoning. Always return your output as a single valid JSON object."
    )

    def negotiate(
        self,
        clause: ExtractedClause,
        comparison: ComparisonResult,
        rank: RankerOutput,
    ) -> NegotiatorOutput:
        """Return the negotiation pack for a single clause."""
        if rank.risk_level == "green":
            return NegotiatorOutput(
                negotiation_needed=False,
                suggested_counter_clause="No negotiation needed — this clause is standard.",
                talking_points=[],
                success_probability=100,
                reasoning="Clause closely resembles the fair industry-standard reference.",
            )

        reference = comparison.reference_clause or "(none)"
        priority = "HIGH" if rank.risk_level == "red" else "LOW"
        prompt = f"""PRIORITY: {priority}
CLAUSE ({rank.risk_level.upper()}, risk score {rank.risk_score}/100) in {clause.category}:
\"\"\"{clause.text}\"\"\"

FAIR REFERENCE TO EMULATE:
\"\"\"{reference}\"\"\"

Draft a negotiation package a consumer can send. The counter-clause must be
concrete, balanced and in plain professional language. Talking points should be
actionable (e.g. what to say on the phone).

Return ONLY JSON:
{{
  "negotiation_needed": true,
  "suggested_counter_clause": "<rewritten fair clause>",
  "talking_points": ["<point 1>", "<point 2>", "<point 3>", "<point 4>"],
  "success_probability": <0-100 integer>,
  "reasoning": "<1-2 sentence explanation of why this likely succeeds>"
}}"""
        try:
            validated_data, _ = llm.chat_json_validated(
                [
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                model=settings.PRIMARY_MODEL,
                temperature=0.3,
                schema=LLMNegotiationOutput,
            )
            if validated_data is None:
                raise ValueError("LLM returned no valid negotiation output")
            prob = max(0, min(100, int(validated_data.success_probability)))
            return NegotiatorOutput(
                negotiation_needed=True,
                suggested_counter_clause=str(validated_data.suggested_counter_clause or "").strip(),
                talking_points=[str(p) for p in (validated_data.talking_points or [])][:5],
                success_probability=prob,
                reasoning=str(validated_data.reasoning or "").strip(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Negotiator LLM call failed: %s", exc)
            return NegotiatorOutput(
                negotiation_needed=True,
                suggested_counter_clause=reference,
                talking_points=[
                    f"Ask them to replace the {clause.category} clause with the "
                    "industry-standard wording provided.",
                    "Point out that a fair alternative exists and similar companies accept it.",
                    "Offer to sign immediately once the clause is corrected.",
                ],
                success_probability=50,
                reasoning="Automatic fallback generated because the LLM call failed.",
            )