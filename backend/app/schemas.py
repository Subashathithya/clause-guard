"""Pydantic schemas shared across the ClauseGuard API and agents."""
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

RiskLevel = Literal["red", "yellow", "green"]

# The 7 canonical clause categories used by Agent 1 (Extractor).
CLAUSE_CATEGORIES = [
    "Payment",
    "Auto-Renewal",
    "Liability",
    "Data Privacy",
    "Dispute",
    "Warranty",
    "Other",
]


# ---------------------------------------------------------------- requests
class DocumentInput(BaseModel):
    text: str
    document_name: str = "Unnamed Document"


class ChatInput(BaseModel):
    question: str
    document_ids: list[str] = Field(default_factory=list)
    history: list[dict] = Field(default_factory=list)


class CompareInput(BaseModel):
    document_ids: list[str] = Field(default_factory=list)


class DriftInput(BaseModel):
    document_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- agent I/O
class ExtractedClause(BaseModel):
    clause_id: str
    category: str
    text: str
    confidence: float = 0.8


class ExtractorOutput(BaseModel):
    total_clauses: int = 0
    clauses: list[ExtractedClause] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    standard_match: str = "unknown"  # "better" | "match" | "worse" | "unknown"
    similarity: float = 0.0
    reference_clause: Optional[str] = None
    reference_category: Optional[str] = None
    notes: str = ""


class RankerOutput(BaseModel):
    risk_level: RiskLevel = "yellow"
    risk_score: int = 50
    risk_percentage: int = 50
    explanation: str = ""
    financial_impact: str = ""
    financial_impact_inr: Optional[int] = None


class NegotiatorOutput(BaseModel):
    negotiation_needed: bool = False
    suggested_counter_clause: str = ""
    talking_points: list[str] = Field(default_factory=list)
    success_probability: int = 50
    reasoning: str = ""


class AnalyzedClause(BaseModel):
    clause_id: str
    category: str
    text: str
    risk_level: RiskLevel
    risk_score: int
    risk_percentage: int
    explanation: str
    confidence: float
    comparison: ComparisonResult = Field(default_factory=ComparisonResult)
    financial_impact: str = ""
    financial_impact_inr: Optional[int] = None
    negotiation_needed: bool = False
    suggested_counter_clause: str = ""
    talking_points: list[str] = Field(default_factory=list)
    success_probability: int = 50
    reasoning: str = ""


class RiskSummary(BaseModel):
    red_count: int = 0
    yellow_count: int = 0
    green_count: int = 0
    overall_risk: str = "UNKNOWN"
    average_risk_score: float = 0.0
    total_financial_exposure_inr: int = 0


class AnalysisSummary(BaseModel):
    total_analyzed: int = 0
    red_flags: int = 0
    warnings: int = 0
    safe: int = 0
    recommendation: str = ""
    top_priorities: list[str] = Field(default_factory=list)


class CrossClauseRelationOut(BaseModel):
    source_clause_id: str = ""
    target_clause_id: str = ""
    relationship: str = ""
    explanation: str = ""


class CrossClauseInconsistencyOut(BaseModel):
    source_clause_id: str = ""
    target_clause_id: str = ""
    kind: str = ""
    value_a: str = ""
    value_b: str = ""
    explanation: str = ""


class CrossClauseReportOut(BaseModel):
    relationships: list[CrossClauseRelationOut] = Field(default_factory=list)
    inconsistencies: list[CrossClauseInconsistencyOut] = Field(default_factory=list)
    semantic_pairs_scanned: int = 0
    llm_calls: int = 0
    feedback: str = ""


# ----------------------------------------------------------- evidence report
# Deterministic, per-clause evidence flags shipped with every analysis. These
# state *what was checked*, never a new risk verdict: the UI can show how many
# sections were compared against the fair-clause library without exposing any
# clause text or internal scoring details.
class EvidenceClauseOut(BaseModel):
    text: bool = False
    category: bool = False
    risk_consistent: bool = False
    reference_present: bool = False
    reference_credible: bool = False
    supported: bool = False
    reference_backed: bool = False


class EvidenceReportOut(BaseModel):
    total: int = 0
    supported: int = 0
    unsupported: int = 0
    reference_backed: int = 0
    by_clause: dict[str, EvidenceClauseOut] = Field(default_factory=dict)


# --------------------------------------------------- version comparison (drift)
# Wire models for the clause-level change report returned by ``POST /drift``.
# Every change is grounded in the two real clause IDs; values are the
# canonical previous/current values (e.g. ``30 days`` -> ``60 days``), never an
# LLM verdict and never clause text leaking into observability.
class VersionChangeOut(BaseModel):
    clause_id_a: str = ""
    clause_id_b: str = ""
    category: str = ""
    change_type: str = "unchanged"  # unchanged | modified | added | removed | ambiguous
    previous_value: str = ""
    current_value: str = ""
    explanation: str = ""


class AttentionEvolutionOut(BaseModel):
    clause_id: str = ""
    category: str = ""
    previous_attention: str = "unknown"  # red | yellow | green | unknown
    current_attention: str = "unknown"
    evolution: str = "unknown"  # unchanged | increased | decreased | new | removed


class VersionComparisonReportOut(BaseModel):
    version_a: str = ""
    version_b: str = ""
    changes: list[VersionChangeOut] = Field(default_factory=list)
    attention_evolution: list[AttentionEvolutionOut] = Field(default_factory=list)
    clauses_a: int = 0
    clauses_b: int = 0
    candidate_pairs: int = 0
    matched_pairs: int = 0
    ambiguous_pairs: int = 0
    llm_calls: int = 0
    semantic_pairs_scanned: int = 0
    feedback: str = ""


class AnalysisResult(BaseModel):
    document_id: Optional[str] = None
    document_name: str = "Unnamed Document"
    total_clauses: int = 0
    risk_summary: RiskSummary = Field(default_factory=RiskSummary)
    clauses: list[AnalyzedClause] = Field(default_factory=list)
    cross_clause: CrossClauseReportOut = Field(default_factory=CrossClauseReportOut)
    evidence: EvidenceReportOut = Field(default_factory=EvidenceReportOut)
    summary: AnalysisSummary = Field(default_factory=AnalysisSummary)
    agent_trace: list[dict] = Field(default_factory=list)
    status: str = "SUCCESS"


# ------------------------------------------------------- Phase 4: tracking
# User-owned dates, bookmarks and checklist items. These are intentionally
# separate from the analysis payload: the analysis can be re-run, while the
# user's reminders, saved sections and negotiation progress must survive it.
DateKind = Literal["payment", "renewal", "notice", "termination", "other"]


class ContractDateCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    due_date: date
    kind: DateKind = "other"
    notes: str = Field(default="", max_length=1000)
    remind_days_before: int = Field(default=7, ge=0, le=365)


class ContractDateUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=120)
    due_date: Optional[date] = None
    kind: Optional[DateKind] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    remind_days_before: Optional[int] = Field(default=None, ge=0, le=365)


class ContractDateOut(BaseModel):
    id: str
    contract_id: str
    label: str
    due_date: date
    kind: str
    notes: str = ""
    remind_days_before: int = 7
    created_at: datetime
    days_until: int
    remind_on: date
    is_overdue: bool = False


class ReminderOut(ContractDateOut):
    contract_name: str


class BookmarkCreate(BaseModel):
    clause_index: str = Field(min_length=1, max_length=30)
    note: str = Field(default="", max_length=1000)


class BookmarkOut(BaseModel):
    id: str
    contract_id: str
    clause_index: str
    note: str = ""
    created_at: datetime


class ChecklistItemCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    clause_index: Optional[str] = Field(default=None, max_length=30)


class ChecklistItemUpdate(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=500)
    done: Optional[bool] = None


class ChecklistItemOut(BaseModel):
    id: str
    contract_id: str
    clause_index: Optional[str] = None
    text: str
    done: bool = False
    position: int = 0
    created_at: datetime



# ------------------------------------------------------- LLM wire schemas
# Schemas the LLM output is validated against BEFORE it is coerced into the
# result models above. The field names mirror the JSON shape the prompts ask
# for (the "existing contract"); validation here rejects malformed output so
# the pipeline can retry or fall back instead of silently coercing garbage.
class LLMClause(BaseModel):
    clause_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    text: str = Field(min_length=1)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class LLMExtractorOutput(BaseModel):
    clauses: list[LLMClause] = Field(default_factory=list)


class LLMRankOutput(BaseModel):
    risk_level: Literal["red", "yellow", "green"] = "yellow"
    risk_score: int = Field(default=50, ge=0, le=100)
    explanation: str = ""
    financial_impact: str = "None identified"
    financial_impact_inr: Optional[int] = None


class LLMNegotiationOutput(BaseModel):
    negotiation_needed: bool = True
    suggested_counter_clause: str = ""
    talking_points: list[str] = Field(default_factory=list)
    success_probability: int = Field(default=50, ge=0, le=100)
    reasoning: str = ""


class LLMSummaryOutput(BaseModel):
    recommendation: str = ""
    top_priorities: list[str] = Field(default_factory=list)
