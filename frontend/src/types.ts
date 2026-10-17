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

export interface AnalysisResult {
  document_id?: string;
  document_name: string;
  source?: string;
  user_id?: string | null;
  total_clauses: number;
  risk_summary: RiskSummary;
  clauses: Clause[];
  summary: AnalysisSummary;
  agent_trace?: AgentTraceItem[];
  status: string;
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