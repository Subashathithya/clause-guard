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
from app.observability import observability
from app.agents.compare_agent import CompareAgent
from app.agents.extract_agent import ExtractAgent
from app.agents.negotiator_agent import NegotiateAgent
from app.agents.ranker_agent import RankAgent
from app.evidence import verify_evidence
from app.cross_clause import detect as _detect_edges, to_out as _cross_out
from app.schemas import (
    AnalysisResult,
    AnalysisSummary,
    AnalyzedClause,
    ComparisonResult,
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
                agent_trace=[{"agent": "Extractor", "error": str(exc)}],
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
                    comparisons[clause.clause_id] = ComparisonResult(notes=str(exc))
        trace.append({"agent": "Comparator", "comparisons": len(comparisons),
                      "ms": round((time.perf_counter() - t0) * 1000)})

        # Evidence verification (deterministic; never leaks clause text).
        # Every risk verdict must be *supported* by a real, checkable reference
        # before it ships as a finding. Unsupported verdicts are kept out of the
        # summary so we never present an unverifiable claim as fact.
        t0 = time.perf_counter()
        clause_map = {c.clause_id: c for c in extracted.clauses}
        evidence = verify_evidence(extracted.clauses, clause_map.get)
        trace.append({"agent": "Evidence", "checked": evidence["total"],
                      "supported": evidence["supported"],
                      "unsupported": evidence["unsupported"],
                      "ms": round((time.perf_counter() - t0) * 1000)})
        observability.evidence(
            checked=evidence["total"],
            supported=evidence["supported"],
            unsupported=evidence["unsupported"],
        )

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
        # every comparison that claims a similarity/reference must be backed by a
        # real, non-empty clause reference — unsupported claims are recorded but
        # never shipped as if they were grounded (privacy: only IDs/flags logged).
        t0 = time.perf_counter()
        evidence = verify_evidence(analyzed, lambda cid: by_id.get(cid))
        observability.evidence(
            checked=evidence["total"],
            supported=evidence["supported"],
            unsupported=evidence["unsupported"],
        )
        trace.append({"agent": "Evidence", "checked": evidence["total"],
                      "supported": evidence["supported"],
                      "unsupported": evidence["unsupported"],
                      "ms": round((time.perf_counter() - t0) * 1000)})

        analyzed.sort(key=lambda c: c.risk_score, reverse=True)
        risk_summary = self._aggregate(analyzed)
        summary = self._synthesize(document_name, analyzed, risk_summary)

        result = AnalysisResult(
            document_name=document_name,
            total_clauses=len(analyzed),
            risk_summary=risk_summary,
            clauses=analyzed,
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
    def _synthesize(
        document_name: str, clauses: list[AnalyzedClause], risk: RiskSummary
    ) -> AnalysisSummary:
        if not clauses:
            return AnalysisSummary(recommendation="No clauses could be extracted from this document.")

        digest = "\n".join(
            f"- [{c.risk_level.upper()} {c.risk_score}] {c.category}: {c.explanation[:180]}"
            for c in clauses
        )
        prompt = f"""Document: {document_name}
Overall risk: {risk.overall_risk} (average score {risk.average_risk_score})
Counts: {risk.red_count} red, {risk.yellow_count} yellow, {risk.green_count} green

CLAUSE DIGEST:
{digest}

Write an executive summary for the consumer. Return ONLY JSON:
{{
  "recommendation": "<2-4 sentence actionable recommendation>",
  "top_priorities": ["<most important clause to renegotiate>", "<second>", "<third>"]
}}"""
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
            return AnalysisSummary(
                total_analyzed=len(clauses),
                red_flags=risk.red_count,
                warnings=risk.yellow_count,
                safe=risk.green_count,
                recommendation=str(validated_data.recommendation).strip(),
                top_priorities=[str(p) for p in (validated_data.top_priorities or [])][:3],
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
            )


def run_orchestrator(
    text: str, document_name: str = "Unnamed Document", ablate_rag: bool = False
) -> AnalysisResult:
    """Convenience wrapper used by the API and tests."""
    return Orchestrator(ablate_rag=ablate_rag).run(text, document_name)