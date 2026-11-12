export type RiskLevel = 'red' | 'yellow' | 'green';

export interface Comparison {
  standard_match: string;
  similarity: number;
  reference_clause?: string | null;
  reference_category?: string | null;
  notes?: string;
}

export interface Clause {
  clause_id: string;
  category: string;
  text: string;
  risk_level: RiskLevel;
  risk_score: number;
  risk_percentage: number;
  explanation: string;
  confidence: number;
  comparison: Comparison;
  financial_impact: string;
  financial_impact_inr?: number | null;
  negotiation_needed: boolean;
  suggested_counter_clause: string;
  talking_points: string[];
  success_probability: number;
  reasoning?: string;
}

export interface RiskSummary {
  red_count: number;
  yellow_count: number;
  green_count: number;
  overall_risk: string;
  average_risk_score: number;
  total_financial_exposure_inr: number;
}

export interface AnalysisSummary {
  total_analyzed: number;
  red_flags: number;
  warnings: number;
  safe: number;
  recommendation: string;
  top_priorities: string[];
}

export interface AgentTraceItem {
  agent: string;
  ms: number;
  [key: string]: unknown;
}

export interface CrossClauseRelation {
  source_clause_id: string;
  target_clause_id: string;
  relationship: string;
  explanation: string;
}

export interface CrossClauseInconsistency {
  source_clause_id: string;
  target_clause_id: string;
  kind: string;
  value_a: string;
  value_b: string;
  explanation: string;
}

export interface CrossClauseReport {
  relationships: CrossClauseRelation[];
  inconsistencies: CrossClauseInconsistency[];
  semantic_pairs_scanned: number;
  llm_calls: number;
  feedback: string;
}

export interface EvidenceClause {
  text: boolean;
  category: boolean;
  risk_consistent: boolean;
  reference_present: boolean;
  reference_credible: boolean;
  supported: boolean;
  reference_backed: boolean;
}

export interface EvidenceReport {
  total: number;
  supported: number;
  unsupported: number;
  reference_backed: number;
  by_clause: Record<string, EvidenceClause>;
}

export interface AnalysisResult {
  document_id?: string;
  document_name: string;
  source?: string;
  user_id?: string | null;
  total_clauses: number;
  risk_summary: RiskSummary;
  clauses: Clause[];
  cross_clause?: CrossClauseReport;
  evidence?: EvidenceReport;
  summary: AnalysisSummary;
  agent_trace?: AgentTraceItem[];
  status: string;
  /** Explicit calendar dates found in the contract text (Phase 4). */
  date_suggestions?: DateSuggestion[];
}

export interface Contract {
  document_id: string;
  document_name: string;
  status?: string;
  overall_risk?: string;
  source?: string;
  chunk_count?: number;
  char_count: number;
  total_clauses?: number;
  red_count?: number;
  yellow_count?: number;
  green_count?: number;
  total_financial_exposure_inr?: number;
  created_at: string;
}

export interface ChatSource {
  text: string;
  document_id: string;
  document_name: string;
  similarity: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
}

export interface ChatResponse {
  answer: string;
  status: string;
  used_documents: string[];
  sources: ChatSource[];
}

export interface CompareResult {
  status: string;
  documents: {
    document_id: string;
    document_name: string;
    overall_risk: string;
    average_risk_score: number;
  }[];
  category_matrix: {
    category: string;
    by_document: Record<string, number>;
    winner: string | null;
  }[];
  narrative: string;
}

export type ChangeType = 'unchanged' | 'modified' | 'added' | 'removed' | 'ambiguous';

export interface VersionChange {
  clause_id_a: string;
  clause_id_b: string;
  category: string;
  change_type: ChangeType;
  previous_value: string;
  current_value: string;
  explanation: string;
}

export interface AttentionEvolution {
  clause_id: string;
  category: string;
  previous_attention: string;
  current_attention: string;
  evolution: string;
}

export interface VersionComparison {
  version_a: string;
  version_b: string;
  changes: VersionChange[];
  attention_evolution: AttentionEvolution[];
  clauses_a: number;
  clauses_b: number;
  candidate_pairs: number;
  matched_pairs: number;
  ambiguous_pairs: number;
  llm_calls: number;
  semantic_pairs_scanned: number;
  feedback: string;
}

export interface DriftResult {
  status: string;
  old: { document_id: string; document_name: string; average_risk_score: number; overall_risk: string };
  new: { document_id: string; document_name: string; average_risk_score: number; overall_risk: string };
  overall_delta: number;
  overall_direction: string;
  changes: {
    category: string;
    before: number | null;
    after: number | null;
    delta: number | null;
    direction: string;
  }[];
  /** Additive clause-level, version-to-version comparison from the backend. */
  version_comparison?: VersionComparison | null;
}

export interface UserQuota {
  monthly_limit: number;
  used: number;
  remaining: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
  quota: UserQuota;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Stats {
  total_contracts: number;
  contracts_this_month: number;
  total_clauses: number;
  red_clauses: number;
  yellow_clauses: number;
  green_clauses: number;
  analysis_credits_this_month: number;
  scope: 'user' | 'guest';
}

export interface FairClausesResponse {
  version: string;
  count: number;
  indexed: number;
  by_category: Record<string, number>;
  samples_by_category: Record<string, string[]>;
}

export type AttentionLevel = 'high' | 'moderate' | 'low' | 'unknown';

/* ---------------------------------------------------------- Phase 4 tracking */
export type DateKind = 'payment' | 'renewal' | 'notice' | 'termination' | 'other';

/** A date found in the contract text — informational until the user adds it. */
export interface DateSuggestion {
  date: string;
  label: string;
  kind: DateKind;
  clause_id?: string | null;
  clause_index?: string | null;
  context: string;
}

export interface ContractDate {
  id: string;
  contract_id: string;
  label: string;
  due_date: string;
  kind: DateKind;
  notes: string;
  remind_days_before: number;
  created_at: string;
  days_until: number;
  remind_on: string;
  is_overdue: boolean;
}

export interface Reminder extends ContractDate {
  contract_name: string;
}

export interface ContractDateInput {
  label: string;
  due_date: string;
  kind?: DateKind;
  notes?: string;
  remind_days_before?: number;
}

export interface Bookmark {
  id: string;
  contract_id: string;
  clause_index: string;
  note: string;
  created_at: string;
}

export interface ChecklistItem {
  id: string;
  contract_id: string;
  clause_index?: string | null;
  text: string;
  done: boolean;
  position: number;
  created_at: string;
}