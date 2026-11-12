"""Pipeline Orchestrator.

Connects the four agents in sequence and returns a single, fully-enriched
AnalysisResult:

    1. Agent 1 Extract   -> clauses
    2. Agent 2 Compare   -> fair-clause similarity (RAG, parallel)
    3. Agent 3 Rank      -> risk levels + explanations (parallel)
    4. Agent 4 Negotiate -> counter-clauses for risky clauses (parallel)

If any agent fails, the pipeline continues with partial results and records
which agent failed in `agent_flags`.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import cross_clause, llm
from app.agents.compare_agent import CompareAgent
from app.agents.extract_agent import ExtractAgent
from app.agents.negotiator_agent import NegotiateAgent
from app.agents.ranker_agent import RankAgent
from app.evidence import verify_analysis_evidence
from app.schemas import (
    AnalysisResult,
    AnalysisSummary,
    AnalyzedClause,
    ComparisonResult,
    CrossClauseReportOut,
    LLMSummaryOutput,
    NegotiatorOutput,
    RankerOutput,
    RiskSummary,
)
from app.settings import settings

logger = logging.getLogger(__name__)

MAX_WORKERS = 4


class Orchestrator:
    """Runs the complete 4-agent pipeline over a contract."""

    def __init__(self, ablate_rag: bool = False) -> None:
        self.extractor = ExtractAgent()
        self.comparator = CompareAgent()
        self.ranker = RankAgent()
        self.negotiator = NegotiateAgent()
        self.agent_flags: list[str] = []
        # ablation mode: Ranker scores clauses WITHOUT RAG reference/similarity
        self.ablate_rag = ablate_rag

    # ------------------------------------------------------------------
    def run(self, text: str, document_name: str = "Unnamed Document") -> AnalysisResult:
        """Execute the full pipeline. Never raises for a single agent failure."""
        trace: list[dict] = []

        # 1. Extract
        t0 = time.perf_counter()
        try:
            extracted = self.extractor.extract(text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Extractor crashed")
            self.agent_flags.append("Extractor")
            return AnalysisResult(
                document_name=document_name,
                status="EXTRACTOR_ERROR",
                # The raw error stays in the log; the response says only
                # that the document could not be read.
                agent_trace=[{
                    "agent": "Extractor",
                    "error": "We could not read this document.",
                }],
            )
        trace.append({"agent": "Extractor", "clauses": len(extracted.clauses),
                      "ms": round((time.perf_counter() - t0) * 1000)})
        if not extracted.clauses:
            return AnalysisResult(document_name=document_name, status="NO_CLAUSES", agent_trace=trace)

        # 2. Compare (parallel, RAG)
        t0 = time.perf_counter()
        comparisons: dict[str, ComparisonResult] = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(self.comparator.compare, c): c for c in extracted.clauses}
            for fut in as_completed(futures):
                clause = futures[fut]
                try:
                    comparisons[clause.clause_id] = fut.result()
                except Exception as exc:  # noqa: BLE001
                    self.agent_flags.append("Comparator")
                    logger.warning("Comparator failed for %s: %s", clause.clause_id, exc)
                    comparisons[clause.clause_id] = ComparisonResult(
                        notes="The reference comparison was unavailable for this section."
                    )
        trace.append({"agent": "Comparator", "comparisons": len(comparisons),
                      "ms": round((time.perf_counter() - t0) * 1000)})

        # Evidence verification (deterministic; never leaks clause text).
        # A clause is only *supported* when its text, category and RAG
        # reference all check out. The report is attached to AnalysisResult
        # below (once the analyzed clauses exist) so the API and UI describe
        # what was verified without inventing a second, always-empty pass.

        # 5. Cross-clause detection (deterministic; §10: semantic=None ⇒ never
        # an LLM/semantic call). Relationships + inconsistencies are mapped to
        # the API contract before the summary, so they ship on every AnalysisResult.
        try:
            cross_out = cross_clause.to_out(
                cross_clause.detect(extracted.clauses, semantic=None)
            )
            trace.append({"agent": "CrossClause",
                          "relationships": len(cross_out.relationships),
                          "inconsistencies": len(cross_out.inconsistencies),
                          "llm_calls": cross_out.llm_calls})
        except Exception as exc:  # noqa: BLE001 — never let §6 break the pipeline
            cross_out = CrossClauseReportOut()
            self.agent_flags.append("CrossClause")
            logger.warning("Cross-clause detection failed: %s", exc)

        # 6. Rank (parallel, LLM) — highest risk first
        t0 = time.perf_counter()
        ranks: dict[str, RankerOutput] = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {
                pool.submit(
                    self.ranker.rank,
                    c,
                    comparisons.get(c.clause_id, ComparisonResult()),
                    self.ablate_rag,
                ): c
                for c in extracted.clauses
            }
            for fut in as_completed(futures):
                clause = futures[fut]
                try:
                    ranks[clause.clause_id] = fut.result()
                except Exception as exc:  # noqa: BLE001
                    self.agent_flags.append("Ranker")
                    logger.warning("Ranker failed for %s: %s", clause.clause_id, exc)
                    ranks[clause.clause_id] = RankerOutput(explanation="Scoring unavailable.")
        trace.append({"agent": "Ranker", "ranked": len(ranks),
                      "ms": round((time.perf_counter() - t0) * 1000)})

        # 4. Negotiate (parallel, only non-green clauses)
        t0 = time.perf_counter()
        negotiations: dict[str, NegotiatorOutput] = {}
        to_negotiate = [
            c for c in extracted.clauses
            if ranks.get(c.clause_id, RankerOutput()).risk_level != "green"
        ]
        if to_negotiate:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {
                    pool.submit(
                        self.negotiator.negotiate,
                        c,
                        comparisons.get(c.clause_id, ComparisonResult()),
                        ranks.get(c.clause_id, RankerOutput()),
                    ): c
                    for c in to_negotiate
                }
                for fut in as_completed(futures):
                    clause = futures[fut]
                    try:
                        negotiations[clause.clause_id] = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        self.agent_flags.append("Negotiator")
                        logger.warning("Negotiator failed for %s: %s", clause.clause_id, exc)
        trace.append({"agent": "Negotiator", "negotiated": len(negotiations),
                      "ms": round((time.perf_counter() - t0) * 1000)})

        # Merge into final clause list
        analyzed: list[AnalyzedClause] = []
        for c in extracted.clauses:
            comp = comparisons.get(c.clause_id, ComparisonResult())
            rank = ranks.get(c.clause_id, RankerOutput())
            neg = negotiations.get(c.clause_id, NegotiatorOutput(negotiation_needed=False))
            analyzed.append(
                AnalyzedClause(
                    clause_id=c.clause_id,
                    category=c.category,
                    text=c.text,
                    risk_level=rank.risk_level,
                    risk_score=rank.risk_score,
                    risk_percentage=rank.risk_percentage,
                    explanation=rank.explanation,
                    confidence=c.confidence,
                    comparison=comp,
                    financial_impact=rank.financial_impact,
                    financial_impact_inr=rank.financial_impact_inr,
                    negotiation_needed=neg.negotiation_needed,
                    suggested_counter_clause=neg.suggested_counter_clause,
                    talking_points=neg.talking_points,
                    success_probability=neg.success_probability,
                    reasoning=neg.reasoning,
                )
            )

        # Evidence verification (deterministic, no clause text in observability):
        # every compared claim must be backed by a real, non-empty fair-clause
        # reference, and the risk band must be internally consistent with its
        # score. The report ships as aggregate counts + per-clause flags; it
        # never upgrades or suppresses a verdict, so users keep seeing every
        # section while knowing what was checked.
        t0 = time.perf_counter()
        evidence = verify_analysis_evidence(analyzed)
        trace.append({"agent": "Evidence", "checked": evidence["total"],
                      "supported": evidence["supported"],
                      "unsupported": evidence["unsupported"],
                      "reference_backed": evidence["reference_backed"],
                      "ms": round((time.perf_counter() - t0) * 1000)})

        analyzed.sort(key=lambda c: c.risk_score, reverse=True)
        risk_summary = self._aggregate(analyzed)
        summary = self._synthesize(document_name, analyzed, risk_summary, cross_out)

        result = AnalysisResult(
            document_name=document_name,
            total_clauses=len(analyzed),
            risk_summary=risk_summary,
            clauses=analyzed,
            cross_clause=cross_out,
            evidence=evidence,
            summary=summary,
            agent_trace=trace,
            status="SUCCESS",
        )
        if self.agent_flags:
            result.status = "PARTIAL_SUCCESS"
        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _aggregate(clauses: list[AnalyzedClause]) -> RiskSummary:
        red = sum(1 for c in clauses if c.risk_level == "red")
        yellow = sum(1 for c in clauses if c.risk_level == "yellow")
        green = sum(1 for c in clauses if c.risk_level == "green")
        avg = round(sum(c.risk_score for c in clauses) / len(clauses), 1) if clauses else 0.0
        exposure = sum(c.financial_impact_inr or 0 for c in clauses)
        if red:
            overall = "HIGH"
        elif yellow:
            overall = "MODERATE"
        else:
            overall = "SAFE"
        return RiskSummary(
            red_count=red,
            yellow_count=yellow,
            green_count=green,
            overall_risk=overall,
            average_risk_score=avg,
            total_financial_exposure_inr=exposure,
        )

    @staticmethod
    def _fallback_priorities(
        clauses: list[AnalyzedClause], cross: CrossClauseReportOut
    ) -> list[str]:
        """Deterministic, user-facing priorities when synthesis is unavailable.

        Inconsistencies come first because they describe two real sections that
        disagree; the remaining slots name the highest-risk categories. Nothing
        here invents a finding — every line is built from an existing clause.
        """
        priorities: list[str] = []
        for inc in cross.inconsistencies[:2]:
            values = " vs ".join(v for v in (inc.value_a, inc.value_b) if v)
            detail = f" ({values})" if values else ""
            priorities.append(
                f"Check the two sections that give different {inc.kind}{detail}."
            )

        seen_categories: set[str] = set()
        for clause in sorted(clauses, key=lambda c: c.risk_score, reverse=True):
            if clause.risk_level == "green" or clause.category in seen_categories:
                continue
            seen_categories.add(clause.category)
            first_sentence = (clause.explanation or "").strip().split(". ")[0].strip()
            first_sentence = first_sentence.rstrip(".")
            if len(first_sentence) > 140:
                first_sentence = first_sentence[:137].rstrip() + "..."
            if first_sentence:
                priorities.append(
                    f"Review the {clause.category} section: {first_sentence}."
                )
            else:
                priorities.append(f"Review the {clause.category} section.")
            if len(priorities) >= 3:
                break
        return priorities[:3]

    @staticmethod
    def _synthesize(
        document_name: str,
        clauses: list[AnalyzedClause],
        risk: RiskSummary,
        cross: CrossClauseReportOut,
    ) -> AnalysisSummary:
        if not clauses:
            return AnalysisSummary(recommendation="No clauses could be extracted from this document.")

        digest = "\n".join(
            f"- [{c.risk_level.upper()} {c.risk_score}] {c.category}: {c.explanation[:180]}"
            for c in clauses
        )
        cross_notes = "\n".join(
            f"- Two sections set different {i.kind} values "
            f"({i.value_a} vs {i.value_b})."
            for i in cross.inconsistencies
        )
        cross_block = (
            f"\nCROSS-SECTION NOTES (possible internal disagreements):\n{cross_notes}\n"
            if cross_notes
            else ""
        )
        prompt = f"""Document: {document_name}
Overall risk: {risk.overall_risk} (average score {risk.average_risk_score})
Counts: {risk.red_count} red, {risk.yellow_count} yellow, {risk.green_count} green

CLAUSE DIGEST:
{digest}
{cross_block}
Write an executive summary for the consumer. Return ONLY JSON:
{{
  "recommendation": "<2-4 sentence actionable recommendation>",
  "top_priorities": ["<most important clause to renegotiate>", "<second>", "<third>"]
}}"""
        fallback_priorities = Orchestrator._fallback_priorities(clauses, cross)
        try:
            validated_data, _ = llm.chat_json_validated(
                [
                    {"role": "system", "content": "You are a concise consumer-protection advisor. Always return your output as a single valid JSON object."},
                    {"role": "user", "content": prompt},
                ],
                model=settings.PRIMARY_MODEL,
                temperature=0.2,
                schema=LLMSummaryOutput,
            )
            if validated_data is None:
                raise ValueError("LLM returned no valid summary output")
            priorities = [str(p) for p in (validated_data.top_priorities or [])][:3]
            return AnalysisSummary(
                total_analyzed=len(clauses),
                red_flags=risk.red_count,
                warnings=risk.yellow_count,
                safe=risk.green_count,
                recommendation=str(validated_data.recommendation).strip(),
                top_priorities=priorities or fallback_priorities,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Summary synthesis failed: %s", exc)
            return AnalysisSummary(
                total_analyzed=len(clauses),
                red_flags=risk.red_count,
                warnings=risk.yellow_count,
                safe=risk.green_count,
                recommendation=(
                    "Review the red and yellow clauses below and use the suggested "
                    "counter-clauses when negotiating."
                ),
                top_priorities=fallback_priorities,
            )


def run_orchestrator(
    text: str, document_name: str = "Unnamed Document", ablate_rag: bool = False
) -> AnalysisResult:
    """Convenience wrapper used by the API and tests."""
    return Orchestrator(ablate_rag=ablate_rag).run(text, document_name)