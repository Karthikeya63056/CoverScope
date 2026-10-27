"""Headless policy intelligence service for CoverScope.

This service coordinates policy document preparation, in-memory caching, section/clause
exploration, and evidence-grounded question answering using the verified backend pipeline.
It does not import Streamlit or any UI framework.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable, Sequence

from backend.config import Settings, settings as default_settings
from backend.document_processing.text_extractor import ExtractedPage
from backend.domain import (
    ComparisonAssumptions,
    DocumentAssociationStatus,
    DocumentType,
    EvidenceReference,
    FactRelationship,
    PolicyComparisonEngine,
    PolicyComparisonResult,
    PolicyFact,
    PolicySchedule,
    PolicyScheduleAssociator,
    PolicyScheduleExtractor,
    ScenarioEvaluator,
    ScenarioInput,
    ScenarioResult,
    ScheduleFieldStatus,
    SourceDocument,
    ValidationReport,
    create_evidence_from_chunk,
    create_source_document,
    extract_candidate_facts,
    validate_domain_bundle,
    validate_fact,
)
import backend.llm.groq_client as groq_client_module
from backend.qa.answer import AnswerResult, StructuredClient
from backend.qa.workflow import (
    PolicyProcessingError,
    ProcessedPolicy,
    ask_policy_question,
    prepare_policy,
)

_SECTION_HEADING_RE = re.compile(
    r"^(?:"
    r"(?:SECTION|Section|Part|PART)\s+[0-9A-Za-z]+[.:\- ]+.*"
    r"|[0-9]{1,2}\.[0-9]{1,2}(?:\.[0-9]{1,2})?\s+[A-Z].*"
    r"|(?:DEFINITIONS|EXCLUSIONS|WAITING PERIODS|BENEFITS|CONDITIONS|CLAIMS PROCEDURE|GRIEVANCE REDRESSAL)"
    r")$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class PolicySearchResult:
    """A search hit within an extracted policy page."""

    page_number: int
    char_count: int
    matched_term: str
    snippet: str
    is_table_review: bool = False
    is_text_poor: bool = False


@dataclass(frozen=True)
class PolicyDocumentRecord:
    """Document record encapsulating a processed policy and its session Q&A history."""

    policy: ProcessedPolicy
    history: tuple[tuple[str, AnswerResult], ...] = ()
    last_question: str | None = None
    last_result: AnswerResult | None = None
    error: str | None = None


class PolicyService:
    """Headless service orchestrating policy preparation, exploration, and Q&A."""

    def __init__(
        self,
        *,
        settings: Settings = default_settings,
        client_factory: Callable[[], StructuredClient] | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory
        self._facts: dict[str, list[PolicyFact]] = {}
        self._relationships: dict[str, list[FactRelationship]] = {}

    def prepare_policy(
        self,
        data: bytes,
        filename: str,
        *,
        max_upload_bytes: int | None = None,
        max_extracted_chars: int | None = None,
        min_page_chars: int | None = None,
        chunk_chars: int | None = None,
    ) -> ProcessedPolicy:
        """Validate, extract, and chunk a PDF in memory.

        Raises PolicyProcessingError if the document is oversized, invalid, or text-poor.
        """
        return prepare_policy(
            data,
            filename,
            max_upload_bytes=max_upload_bytes if max_upload_bytes is not None else self.settings.max_upload_bytes,
            max_extracted_chars=max_extracted_chars if max_extracted_chars is not None else self.settings.max_extracted_chars,
            min_page_chars=min_page_chars if min_page_chars is not None else self.settings.min_page_chars,
            chunk_chars=chunk_chars if chunk_chars is not None else self.settings.chunk_chars,
        )

    def ask_question(
        self,
        policy: ProcessedPolicy,
        question: str,
        *,
        client: StructuredClient | None = None,
        top_k: int | None = None,
        unreliable_pages: Sequence[int] | None = None,
    ) -> AnswerResult:
        """Answer a coverage question with evidence retrieval and citation validation."""
        active_client = client
        if active_client is None:
            if self._client_factory is not None:
                active_client = self._client_factory()
            else:
                active_client = groq_client_module.GroqClient(
                    model=self.settings.groq_model,
                    timeout=self.settings.groq_timeout_seconds,
                    max_completion_tokens=self.settings.groq_max_completion_tokens,
                )

        return ask_policy_question(
            question,
            policy,
            active_client,
            top_k=top_k if top_k is not None else self.settings.retrieval_top_k,
            unreliable_pages=(
                unreliable_pages
                if unreliable_pages is not None
                else self.settings.unreliable_pages
            ),
        )

    def search_policy_text(
        self,
        policy: ProcessedPolicy,
        query: str,
        *,
        max_results: int = 50,
    ) -> list[PolicySearchResult]:
        """Search page text for query occurrences with contextual snippets."""
        clean_query = query.strip()
        if not clean_query or not policy.pages:
            return []

        lower_query = clean_query.lower()
        results: list[PolicySearchResult] = []
        table_pages = set(getattr(policy.quality, "table_review_pages", ()))
        text_poor = set(getattr(policy.quality, "text_poor_pages", ()))

        for page in policy.pages:
            lower_text = page.text.lower()
            start_pos = 0
            while True:
                idx = lower_text.find(lower_query, start_pos)
                if idx == -1:
                    break
                snippet_start = max(0, idx - 60)
                snippet_end = min(len(page.text), idx + len(clean_query) + 80)
                snippet = page.text[snippet_start:snippet_end].replace("\n", " ").strip()
                if snippet_start > 0:
                    snippet = "..." + snippet
                if snippet_end < len(page.text):
                    snippet = snippet + "..."

                results.append(
                    PolicySearchResult(
                        page_number=page.page_number,
                        char_count=page.char_count,
                        matched_term=clean_query,
                        snippet=snippet,
                        is_table_review=page.page_number in table_pages,
                        is_text_poor=page.page_number in text_poor,
                    )
                )
                if len(results) >= max_results:
                    return results
                start_pos = idx + len(clean_query)

        return results

    def get_page(
        self,
        policy: ProcessedPolicy,
        page_number: int,
    ) -> ExtractedPage | None:
        """Return the specific page from the policy, or None if out of bounds."""
        for page in policy.pages:
            if page.page_number == page_number:
                return page
        return None

    def detect_headings(self, text: str) -> list[str]:
        """Detect likely section headings from raw page text without inventing hierarchies."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        headings: list[str] = []
        for line in lines:
            if _SECTION_HEADING_RE.match(line):
                headings.append(line)
        return headings

    def get_policy_summary(self, policy: ProcessedPolicy) -> dict:
        """Return high-level summary metrics for a policy document."""
        return {
            "fingerprint": policy.fingerprint,
            "filename": policy.filename,
            "size_bytes": policy.size_bytes,
            "page_count": policy.page_count,
            "extracted_characters": policy.extracted_characters,
            "chunk_count": len(policy.chunks),
            "is_usable": policy.quality.is_usable,
            "warnings_count": len(policy.quality.warnings),
            "errors_count": len(policy.quality.errors),
        }

    # =========================================================================
    # Policy Domain Foundation & Evidence-Linked Facts (Phase 1.2)
    # =========================================================================

    def to_source_document(
        self,
        policy: ProcessedPolicy,
        *,
        policy_id: str | None = None,
        document_type: DocumentType = DocumentType.POLICY_WORDING,
    ) -> SourceDocument:
        """Construct a canonical SourceDocument entity from a processed policy."""
        return create_source_document(policy, policy_id=policy_id, document_type=document_type)

    def get_document_evidence(
        self,
        policy: ProcessedPolicy,
    ) -> list[EvidenceReference]:
        """Produce canonical evidence references from policy chunks with stable IDs."""
        table_pages = set(getattr(policy.quality, "table_review_pages", ()) or ())
        evidence_list: list[EvidenceReference] = []
        for chunk in policy.chunks:
            warning = None
            if chunk.page_number in table_pages:
                warning = "Page flagged for table review."
            evidence_list.append(
                create_evidence_from_chunk(
                    chunk,
                    policy.fingerprint,
                    quality_warning=warning,
                )
            )
        return evidence_list

    def extract_facts(
        self,
        policy: ProcessedPolicy,
    ) -> list[PolicyFact]:
        """Deterministically extract evidence-backed candidate facts from a policy."""
        return extract_candidate_facts(policy)

    def evaluate_scenario(
        self,
        policy: ProcessedPolicy,
        scenario_input: ScenarioInput,
        *,
        facts: Sequence[PolicyFact] | None = None,
    ) -> ScenarioResult:
        """Evaluate an insurance scenario deterministically against policy facts."""
        evaluator = ScenarioEvaluator()
        return evaluator.evaluate(policy, scenario_input, facts=facts)

    def register_facts(
        self,
        document_id: str,
        facts: Sequence[PolicyFact],
        *,
        policy: ProcessedPolicy | None = None,
    ) -> ValidationReport:
        """Validate and register a collection of facts for a document."""
        doc = None
        page_texts = None
        if policy is not None:
            doc = self.to_source_document(policy)
            page_texts = {(policy.fingerprint, p.page_number): p.text for p in policy.pages}

        docs = [doc] if doc else []
        report = validate_domain_bundle(
            documents=docs,
            facts=facts,
            relationships=(),
            page_texts=page_texts,
        )
        if report.is_valid:
            self._facts.setdefault(document_id, []).extend(facts)
        return report

    def get_facts(
        self,
        document_id: str,
    ) -> list[PolicyFact]:
        """Return registered facts for the given document identifier."""
        return list(self._facts.get(document_id, []))

    def register_relationship(
        self,
        document_id: str,
        relationship: FactRelationship,
    ) -> ValidationReport:
        """Validate and register a semantic relationship linking two facts."""
        facts = {f.fact_id: f for f in self._facts.get(document_id, [])}
        doc_facts = list(facts.values())
        report = validate_domain_bundle(
            documents=[],
            facts=doc_facts,
            relationships=[relationship],
        )
        if report.is_valid:
            self._relationships.setdefault(document_id, []).append(relationship)
        return report

    def get_relationships(
        self,
        document_id: str,
    ) -> list[FactRelationship]:
        """Return registered relationships for the given document identifier."""
        return list(self._relationships.get(document_id, []))

    def get_provenance_summary(
        self,
        policy: ProcessedPolicy,
    ) -> dict:
        """Produce a provenance-aware domain summary for policy inspection."""
        source_doc = self.to_source_document(policy)
        registered_facts = self.get_facts(policy.fingerprint)
        registered_rels = self.get_relationships(policy.fingerprint)

        return {
            "document_id": source_doc.document_id,
            "filename": source_doc.filename,
            "document_type": source_doc.document_type.value,
            "content_hash": source_doc.content_hash,
            "page_count": source_doc.page_count,
            "extracted_characters": source_doc.extracted_characters,
            "chunk_count": len(policy.chunks),
            "table_review_pages": list(source_doc.table_review_pages),
            "text_poor_pages": list(source_doc.text_poor_pages),
            "facts_count": len(registered_facts),
            "relationships_count": len(registered_rels),
        }

    def compare_policies(
        self,
        policy_a: ProcessedPolicy,
        policy_b: ProcessedPolicy,
        assumptions: ComparisonAssumptions | None = None,
        schedule_a: PolicySchedule | None = None,
        schedule_b: PolicySchedule | None = None,
    ) -> PolicyComparisonResult:
        """Compare two policies side-by-side and identify protection gaps."""
        facts_a = self.get_facts(policy_a.fingerprint)
        facts_b = self.get_facts(policy_b.fingerprint)
        engine = PolicyComparisonEngine()
        return engine.compare(
            policy_a,
            policy_b,
            assumptions=assumptions,
            facts_a=facts_a if facts_a else None,
            facts_b=facts_b if facts_b else None,
            schedule_a=schedule_a,
            schedule_b=schedule_b,
        )

    def prepare_schedule(
        self,
        pdf_bytes: bytes,
        filename: str,
    ) -> PolicySchedule:
        """Parse and extract a Policy Schedule or Certificate of Insurance."""
        proc_schedule = self.prepare_policy(
            pdf_bytes,
            filename,
            max_upload_bytes=self.settings.max_upload_bytes,
            max_extracted_chars=self.settings.max_extracted_chars,
            min_page_chars=self.settings.min_page_chars,
            chunk_chars=self.settings.chunk_chars,
        )
        extractor = PolicyScheduleExtractor()
        return extractor.extract(proc_schedule)

    def associate_schedule(
        self,
        schedule: PolicySchedule,
        policy: ProcessedPolicy,
        *,
        user_confirmed: bool = False,
    ) -> PolicySchedule:
        """Associate a Policy Schedule with a target policy wording and check for conflicts."""
        associator = PolicyScheduleAssociator()
        status, reasons = associator.evaluate_association(schedule, policy)

        if user_confirmed:
            if status == DocumentAssociationStatus.CONFLICT_DETECTED:
                reasons = list(reasons) + ["User confirmation rejected: Document conflict cannot be overridden while contractual contradictions persist."]
            else:
                status = DocumentAssociationStatus.USER_CONFIRMED

        conflicts = reasons if status == DocumentAssociationStatus.CONFLICT_DETECTED else ()

        return PolicySchedule(
            schedule_id=schedule.schedule_id,
            filename=schedule.filename,
            document_fingerprint=schedule.document_fingerprint,
            associated_policy_fingerprint=policy.fingerprint if status != DocumentAssociationStatus.CONFLICT_DETECTED else None,
            association_status=status,
            insurer_name=schedule.insurer_name,
            product_name=schedule.product_name,
            product_variant=schedule.product_variant,
            policy_version_or_uin=schedule.policy_version_or_uin,
            policy_number_masked=schedule.policy_number_masked,
            inception_date=schedule.inception_date,
            expiry_date=schedule.expiry_date,
            sum_insured=schedule.sum_insured,
            voluntary_deductible=schedule.voluntary_deductible,
            members=schedule.members,
            optional_riders=schedule.optional_riders,
            fields=schedule.fields,
            conflicts=tuple(conflicts),
            unresolved_conditions=schedule.unresolved_conditions,
            endorsement_policy_refs=schedule.endorsement_policy_refs,
            raw_text_summary=schedule.raw_text_summary,
        )
