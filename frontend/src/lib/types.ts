export interface AuthUser {
  user_id: string;
  email: string;
  display_name: string;
  role: string;
  authenticated_at?: number;
}

export interface AuthResponse {
  success: boolean;
  user: AuthUser;
  token: string;
  access_token?: string | null;
  token_type: string;
  message?: string | null;
}

export interface PolicySummary {
  id?: string;
  policy_id: string;
  document_name?: string;
  filename: string;
  document_hash?: string;
  page_count: number;
  total_characters?: number;
  total_chunks?: number;
  created_at?: string;
  updated_at?: string;
  status?: string;
  processing_status?: string;
  metadata?: {
    char_count?: number;
    chunk_count?: number;
    [key: string]: any;
  };
}

export interface PolicyDetailResponse {
  id: string;
  document_name: string;
  document_hash: string;
  page_count: number;
  char_count: number;
  chunk_count: number;
  created_at?: string | null;
  metadata?: Record<string, any>;
}

export interface PolicyListResponse {
  policies: PolicySummary[];
  total: number;
}

export interface PolicyFactItem {
  category: string;
  text: string;
  page_number: number;
  confidence: number;
}

export interface PolicyFactsResponse {
  policy_id: string;
  document_name: string;
  facts: PolicyFactItem[];
  total_facts: number;
}

export interface PolicyPageTextResponse {
  policy_id: string;
  page_number: number;
  text: string;
  char_count: number;
}

export interface CitationItem {
  chunk_id: string;
  page_number: number;
  quote: string;
}

export interface AnswerResponse {
  answer: string;
  verdict: 'covered' | 'excluded' | 'depends' | 'not_stated' | string;
  citations: CitationItem[];
  confidence: 'high' | 'medium' | 'low' | string;
  caveats: string[];
  conversation_id?: string | null;
  citations_valid: boolean;
  manual_review_required: boolean;
  warnings: string[];
  unverified_answer?: string | null;
}

export interface ScenarioClauseCitation {
  chunk_id: string;
  page_number: number;
  text: string;
}

export interface ScenarioResponse {
  verdict:
    | 'waiting_period_active'
    | 'waiting_period_satisfied'
    | 'conditional_review'
    | 'exclusion_identified'
    | 'insufficient_evidence'
    | 'unsupported_scenario'
    | string;
  headline: string;
  explanation: string;
  applicable_clauses: ScenarioClauseCitation[];
  caveats: string[];
  missing_inputs?: string[];
  user_assumptions?: string[];
  calculation_formula?: string | null;
  decision_state?: string | null;
  evidentiary_support?: string | null;
}

export interface DimensionComparisonItem {
  name: string;
  policy_a_value: string;
  policy_b_value: string;
  status: string;
  assessment: string;
}

export interface ProtectionGapItem {
  severity: 'caution' | 'conditional_gap' | 'unverified_gap' | 'informational' | string;
  dimension: string;
  title: string;
  description: string;
}

export interface ComparisonResponse {
  policy_a_name: string;
  policy_b_name: string;
  dimensions: DimensionComparisonItem[];
  gaps: ProtectionGapItem[];
  assumptions_used: Record<string, any>;
}

export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
  evidence_metadata?: Record<string, any>;
}

export interface ConversationHistoryResponse {
  conversation_id: string;
  policy_id: string;
  messages: ConversationMessage[];
}

export interface DashboardSummaryResponse {
  total_policies: number;
  total_conversations: number;
  total_analyses: number;
  database_status: string;
  recent_policies: PolicySummary[];
  recent_messages: ConversationMessage[];
}

export interface RehearsalChecklistItem {
  id: string;
  title: string;
  description: string;
  category: 'pre_admission' | 'documentation' | 'financial' | 'tpa_coordination' | string;
  is_mandatory: boolean;
  suggested_action: string;
  completed?: boolean;
}

export interface FinancialBreakdown {
  estimated_bill?: number | null;
  deductible_or_copay_amount?: number | null;
  copayment_percentage?: number | null;
  sublimit_cap_amount?: number | null;
  room_rent_deduction_amount?: number | null;
  estimated_out_of_pocket?: number | null;
  estimated_insurer_coverage?: number | null;
  calculation_notes: string[];
}

export interface RelevantConditionItem {
  category: string;
  status: 'active_risk' | 'satisfied' | 'exempt' | 'warning' | 'compliant' | 'info' | string;
  severity: 'high' | 'medium' | 'low' | string;
  title: string;
  details: string;
}

export interface RehearsalSupportingClause {
  chunk_id: string;
  page_number: number;
  quote: string;
  topic?: string;
  relevance_score?: number;
}

export interface ClaimRehearsalRequest {
  policy_id: string;
  treatment_description: string;
  estimated_expense?: number | null;
  member_age?: number | null;
  policy_duration_months?: number | null;
  room_category?: 'single_private' | 'shared' | 'deluxe_suite' | 'icu' | 'general' | string;
  hospital_type?: 'network_cashless' | 'non_network_reimbursement' | string;
  is_emergency?: boolean;
  is_pre_existing?: boolean;
}

export interface ClaimRehearsalResponse {
  rehearsal_id: string;
  policy_id: string;
  policy_name: string;
  readiness_status: 'ready_to_verify' | 'important_checks_required' | 'insufficient_information' | string;
  headline: string;
  executive_summary: string;
  relevant_conditions: RelevantConditionItem[];
  financial_breakdown?: FinancialBreakdown | null;
  supporting_clauses: RehearsalSupportingClause[];
  missing_information: string[];
  unresolved_assumptions: string[];
  questions_to_ask_tpa: string[];
  checklist: RehearsalChecklistItem[];
  created_at?: string | null;
}

export interface ClaimRehearsalRecord {
  id: string;
  user_id: string;
  policy_id: string;
  analysis_type: string;
  input_summary?: {
    treatment_description?: string;
    estimated_expense?: number | null;
    member_age?: number | null;
    policy_duration_months?: number | null;
    room_category?: string;
    hospital_type?: string;
    is_emergency?: boolean;
    is_pre_existing?: boolean;
    policy_id?: string;
  };
  result_summary?: {
    rehearsal_id?: string;
    policy_name?: string;
    readiness_status?: string;
    headline?: string;
    executive_summary?: string;
    financial_breakdown?: FinancialBreakdown | null;
  };
  source_references?: RehearsalSupportingClause[];
  created_at?: string;
}

export interface ScenarioRecord {
  id: string;
  user_id: string;
  policy_id: string;
  analysis_type: string;
  input_summary?: {
    policy_id?: string;
    ailment?: string;
    elapsed_months?: number;
    elapsed_days?: number;
    member_age?: number;
    scenario_type?: string;
  };
  result_summary?: {
    policy_name?: string;
    verdict?: string;
    headline?: string;
    explanation?: string;
  };
  source_references?: Array<{
    chunk_id?: string;
    page_number?: number;
    text?: string;
  }>;
  created_at?: string;
}

