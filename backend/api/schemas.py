"""Pydantic request and response schemas for CoverScope FastAPI REST API."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# --- Auth Schemas ---
class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: str = "policyholder"


class AuthResponse(BaseModel):
    success: bool
    user: UserResponse
    token: str
    access_token: str | None = None
    token_type: str = "bearer"
    message: str | None = None


# --- Policy & Document Schemas ---
class PolicySummary(BaseModel):
    id: str
    policy_id: str | None = None
    document_name: str
    filename: str | None = None
    document_hash: str
    page_count: int
    total_characters: int = 0
    total_chunks: int = 0
    processing_status: str = "processed"
    status: str = "processed"
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.policy_id:
            object.__setattr__(self, "policy_id", self.id)
        if not self.filename:
            object.__setattr__(self, "filename", self.document_name)
        if not self.total_characters and "char_count" in self.metadata:
            object.__setattr__(self, "total_characters", self.metadata["char_count"])
        if not self.total_chunks and "chunk_count" in self.metadata:
            object.__setattr__(self, "total_chunks", self.metadata["chunk_count"])
        if not self.status:
            object.__setattr__(self, "status", self.processing_status)


class PolicyListResponse(BaseModel):
    policies: list[PolicySummary]
    total: int


class PolicyDetailResponse(BaseModel):
    id: str
    document_name: str
    document_hash: str
    page_count: int
    char_count: int
    chunk_count: int
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PageTextResponse(BaseModel):
    policy_id: str
    page_number: int
    text: str
    char_count: int


class FactItem(BaseModel):
    category: str
    text: str
    page_number: int
    confidence: float = 1.0


class PolicyFactsResponse(BaseModel):
    policy_id: str
    document_name: str
    facts: list[FactItem]
    total_facts: int = 0


# --- Q&A Schemas ---
class CitationItem(BaseModel):
    chunk_id: str
    page_number: int
    quote: str


class AskQuestionRequest(BaseModel):
    policy_id: str
    question: str


class AskQuestionResponse(BaseModel):
    verdict: str
    answer: str
    citations: list[CitationItem]
    confidence: str
    caveats: list[str] = Field(default_factory=list)
    conversation_id: str | None = None
    citations_valid: bool = True
    manual_review_required: bool = False
    warnings: list[str] = Field(default_factory=list)
    unverified_answer: str | None = None


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    evidence_metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    policy_id: str
    messages: list[MessageItem]


# --- Scenario Analyzer Schemas ---
class ScenarioRequest(BaseModel):
    policy_id: str
    ailment: str
    elapsed_months: int = Field(ge=0, le=240, default=12)
    elapsed_days: int | None = Field(default=None, ge=0, le=7300)
    member_age: int | None = Field(ge=0, le=120, default=None)
    scenario_type: str = "pre_existing_condition"
    room_type: str | None = None
    sum_insured: float | None = None


class ScenarioResponse(BaseModel):
    verdict: str
    headline: str
    explanation: str
    applicable_clauses: list[dict[str, Any]] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    user_assumptions: list[str] = Field(default_factory=list)
    calculation_formula: str | None = None
    decision_state: str | None = None
    evidentiary_support: str | None = None



# --- Policy Comparison Schemas ---
class ComparisonRequest(BaseModel):
    policy_id_a: str
    policy_id_b: str
    continuous_months: int = Field(ge=0, le=240, default=24)
    member_age: int = Field(ge=0, le=120, default=45)


class ComparisonDimension(BaseModel):
    name: str
    policy_a_value: str
    policy_b_value: str
    status: str
    assessment: str
    conditions_a: list[str] = Field(default_factory=list)
    conditions_b: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ComparisonProtectionGap(BaseModel):
    severity: str
    dimension: str
    title: str
    description: str


class ComparisonResponse(BaseModel):
    policy_a_name: str
    policy_b_name: str
    dimensions: list[ComparisonDimension]
    gaps: list[ComparisonProtectionGap]
    assumptions_used: dict[str, Any]
    general_limitations: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


# --- Dashboard Schemas ---
class DashboardSummaryResponse(BaseModel):
    total_policies: int
    total_conversations: int
    total_analyses: int
    database_status: str
    recent_policies: list[PolicySummary]
    recent_messages: list[dict[str, Any]]


# --- Claim Rehearsal Schemas ---
class ClaimRehearsalRequest(BaseModel):
    policy_id: str
    treatment_description: str
    estimated_expense: float | None = Field(default=None, ge=0.0)
    member_age: int | None = Field(default=None, ge=0, le=120)
    policy_duration_months: int | None = Field(default=12, ge=0, le=240)
    room_category: str = Field(default="single_private")  # single_private, shared, deluxe_suite, icu, general
    hospital_type: str = Field(default="network_cashless")  # network_cashless, non_network_reimbursement
    is_emergency: bool = False
    is_pre_existing: bool = False


class RehearsalChecklistItem(BaseModel):
    id: str
    title: str
    description: str
    category: str  # pre_admission, documentation, financial, tpa_coordination
    is_mandatory: bool = False
    suggested_action: str
    completed: bool = False


class FinancialBreakdown(BaseModel):
    estimated_bill: float | None = None
    deductible_or_copay_amount: float | None = None
    copayment_percentage: float | None = None
    sublimit_cap_amount: float | None = None
    room_rent_deduction_amount: float | None = None
    estimated_out_of_pocket: float | None = None
    estimated_insurer_coverage: float | None = None
    calculation_notes: list[str] = Field(default_factory=list)


class ClaimRehearsalResponse(BaseModel):
    rehearsal_id: str
    policy_id: str
    policy_name: str
    readiness_status: str  # ready_to_verify, important_checks_required, insufficient_information
    headline: str
    executive_summary: str
    relevant_conditions: list[dict[str, Any]] = Field(default_factory=list)
    financial_breakdown: FinancialBreakdown | None = None
    supporting_clauses: list[dict[str, Any]] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    unresolved_assumptions: list[str] = Field(default_factory=list)
    questions_to_ask_tpa: list[str] = Field(default_factory=list)
    checklist: list[RehearsalChecklistItem] = Field(default_factory=list)
    created_at: str | None = None

