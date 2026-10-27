"""Tests for PolicyService domain integration, evidence extraction, and isolation."""
from __future__ import annotations

import sys
from pathlib import Path
import pymupdf
import pytest
from streamlit.testing.v1 import AppTest

from backend.domain.enums import (
    DocumentType,
    FactCategory,
    FactValidationStatus,
)
from backend.domain.models import PolicyFact
from backend.qa.workflow import prepare_policy
from backend.services.policy_service import PolicyService
from frontend.app import DOC_KEY
from frontend.state import ACTIVE_VIEW_KEY, VIEW_EXPLORER

APP_PATH = Path(__file__).resolve().parents[1] / "frontend" / "app.py"

POLICY_TEXT_A = (
    "SECTION 1: WAITING PERIODS\n"
    "Pre-existing diseases (PED) are excluded for 36 months of continuous coverage.\n"
    "SECTION 2: EXCLUSIONS\n"
    "Treatment for alcoholism is excluded.\n"
    "Cataract surgery is subject to a sublimit of Rs 50,000 per eye."
)

POLICY_TEXT_B = (
    "SECTION 1: MATERNITY BENEFIT\n"
    "Maternity expenses are covered up to a limit of Rs 40,000 per delivery.\n"
    "Pre-existing diseases are excluded for 24 months."
)


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_domain_package_has_no_streamlit_imports():
    """Verify backend.domain does not import Streamlit."""
    import backend.domain as domain_mod

    assert "streamlit" not in sys.modules or "streamlit" not in domain_mod.__dict__


def test_policy_service_source_document_conversion():
    service = PolicyService()
    pdf_bytes = make_pdf(POLICY_TEXT_A)
    policy = service.prepare_policy(pdf_bytes, "ReAssure_Policy.pdf")

    source_doc = service.to_source_document(policy, policy_id="pol_reassure_01")
    assert source_doc.document_id == policy.fingerprint
    assert source_doc.policy_id == "pol_reassure_01"
    assert source_doc.filename == "ReAssure_Policy.pdf"
    assert source_doc.page_count == 1
    assert source_doc.document_type == DocumentType.POLICY_WORDING
    assert source_doc.extraction_status == "extracted"


def test_policy_service_evidence_references():
    service = PolicyService()
    pdf_bytes = make_pdf(POLICY_TEXT_A)
    policy = service.prepare_policy(pdf_bytes, "ReAssure_Policy.pdf")

    evidence = service.get_document_evidence(policy)
    assert len(evidence) == len(policy.chunks)
    assert all(ev.document_id == policy.fingerprint for ev in evidence)
    assert all(ev.page_number == 1 for ev in evidence)
    assert all(ev.chunk_id.startswith("P1-C") for ev in evidence)


def test_policy_service_extract_candidate_facts():
    service = PolicyService()
    pdf_bytes = make_pdf(POLICY_TEXT_A)
    policy = service.prepare_policy(pdf_bytes, "ReAssure_Policy.pdf")

    facts = service.extract_facts(policy)
    assert len(facts) >= 2

    categories = {f.category for f in facts}
    assert FactCategory.WAITING_PERIOD in categories
    assert FactCategory.EXCLUSION in categories

    ped_fact = next(f for f in facts if f.category == FactCategory.WAITING_PERIOD)
    assert ped_fact.structured_value is not None
    assert getattr(ped_fact.structured_value, "amount", None) == 36
    assert ped_fact.evidence_references[0].page_number == 1
    assert "pre-existing" in ped_fact.evidence_references[0].exact_text.lower()


def test_policy_service_multi_policy_fact_isolation():
    service = PolicyService()
    pol_a = service.prepare_policy(make_pdf(POLICY_TEXT_A), "Policy_A.pdf")
    pol_b = service.prepare_policy(make_pdf(POLICY_TEXT_B), "Policy_B.pdf")

    facts_a = service.extract_facts(pol_a)
    facts_b = service.extract_facts(pol_b)

    service.register_facts(pol_a.fingerprint, facts_a, policy=pol_a)
    service.register_facts(pol_b.fingerprint, facts_b, policy=pol_b)

    reg_a = service.get_facts(pol_a.fingerprint)
    reg_b = service.get_facts(pol_b.fingerprint)

    assert len(reg_a) == len(facts_a)
    assert len(reg_b) == len(facts_b)
    # Ensure no cross-contamination of document facts
    assert all(f.document_id == pol_a.fingerprint for f in reg_a)
    assert all(f.document_id == pol_b.fingerprint for f in reg_b)


def test_policy_service_provenance_summary():
    service = PolicyService()
    pol_a = service.prepare_policy(make_pdf(POLICY_TEXT_A), "Policy_A.pdf")
    facts_a = service.extract_facts(pol_a)
    service.register_facts(pol_a.fingerprint, facts_a, policy=pol_a)

    summary = service.get_provenance_summary(pol_a)
    assert summary["document_id"] == pol_a.fingerprint
    assert summary["filename"] == "Policy_A.pdf"
    assert summary["facts_count"] == len(facts_a)
    assert summary["page_count"] == 1


def test_explorer_view_with_evidence_linked_facts_apptest():
    policy = prepare_policy(make_pdf(POLICY_TEXT_A), "Explorer-Coverage.pdf")
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.session_state[DOC_KEY] = policy
    at.session_state[ACTIVE_VIEW_KEY] = VIEW_EXPLORER
    at.run()

    assert not list(at.exception)
    rendered = " ".join(m.value for m in at.markdown)
    assert "Explorer-Coverage.pdf" in rendered
    assert "Policy Explorer" in rendered
    # Check that candidate facts expander rendered
    assert any("Evidence-Linked Candidate Facts" in exp.label for exp in at.expander)
