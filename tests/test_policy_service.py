"""Tests for the headless PolicyService layer."""
from __future__ import annotations

import sys
import pymupdf
import pytest

from backend.document_processing.text_extractor import ExtractedPage
from backend.qa.workflow import PolicyProcessingError
from backend.services.policy_service import PolicySearchResult, PolicyService

POLICY_TEXT_PAGE_1 = (
    "SECTION 1: DEFINITIONS\n"
    "Expenses related to the treatment of a pre-existing disease (PED) are excluded "
    "until the expiry of 36 months of continuous coverage.\n"
    "Hospitalization expenses are covered subject to policy limits."
)

POLICY_TEXT_PAGE_2 = (
    "SECTION 4: EXCLUSIONS\n"
    "Treatment for alcoholism and drug addiction is excluded.\n"
    "Cataract surgery is subject to a sublimit of Rs 50,000 per eye."
)


def make_sample_pdf() -> bytes:
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), POLICY_TEXT_PAGE_1)
    p2 = doc.new_page()
    p2.insert_text((72, 72), POLICY_TEXT_PAGE_2)
    data = doc.tobytes()
    doc.close()
    return data


class FakeStructuredClient:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {
            "verdict": "excluded",
            "answer": "Pre-existing diseases are excluded for 36 months.",
            "citations": [],
            "confidence": "high",
            "caveats": [],
        }
        self.calls = 0

    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict | None = None) -> dict:
        self.calls += 1
        return self.payload


def test_policy_service_has_no_streamlit_imports():
    """Verify backend.services.policy_service does not import Streamlit."""
    import backend.services.policy_service as service_module

    assert "streamlit" not in sys.modules or "streamlit" not in service_module.__dict__
    assert not hasattr(service_module, "st")


def test_policy_service_prepare_and_summary():
    service = PolicyService()
    pdf_bytes = make_sample_pdf()
    policy = service.prepare_policy(pdf_bytes, "health_policy.pdf")

    assert policy.filename == "health_policy.pdf"
    assert policy.page_count == 2
    assert len(policy.pages) == 2
    assert policy.chunks
    assert policy.quality.is_usable

    summary = service.get_policy_summary(policy)
    assert summary["filename"] == "health_policy.pdf"
    assert summary["page_count"] == 2
    assert summary["is_usable"] is True
    assert summary["chunk_count"] == len(policy.chunks)


def test_policy_service_repeat_questions_reuse_prepared_policy():
    service = PolicyService()
    policy = service.prepare_policy(make_sample_pdf(), "health_policy.pdf")

    chunk = policy.chunks[0]
    quote = (
        "Expenses related to the treatment of a pre-existing disease (PED) are excluded "
        "until the expiry of 36 months"
    )
    client = FakeStructuredClient({
        "verdict": "excluded",
        "answer": "PED is excluded for 36 months.",
        "citations": [{"chunk_id": chunk.chunk_id, "quote": quote}],
        "confidence": "high",
        "caveats": [],
    })

    # Question 1
    res1 = service.ask_question(policy, "Is PED covered in month 20?", client=client)
    assert client.calls == 1
    assert res1.verdict == "excluded"
    assert res1.citations_valid

    # Question 2 (same prepared policy, no re-extraction)
    res2 = service.ask_question(policy, "Is cataract surgery covered?", client=client)
    assert client.calls == 2
    assert res2.verdict == "excluded"


def test_policy_service_search_policy_text():
    service = PolicyService()
    policy = service.prepare_policy(make_sample_pdf(), "health_policy.pdf")

    # Search for term present on page 1
    hits_ped = service.search_policy_text(policy, "pre-existing")
    assert len(hits_ped) >= 1
    assert hits_ped[0].page_number == 1
    assert "pre-existing" in hits_ped[0].snippet.lower()

    # Search for term present on page 2
    hits_cataract = service.search_policy_text(policy, "cataract")
    assert len(hits_cataract) >= 1
    assert hits_cataract[0].page_number == 2
    assert "cataract" in hits_cataract[0].snippet.lower()

    # Search for non-existent term
    assert service.search_policy_text(policy, "space travel") == []
    # Empty query
    assert service.search_policy_text(policy, "   ") == []


def test_policy_service_detect_headings():
    service = PolicyService()
    headings_1 = service.detect_headings(POLICY_TEXT_PAGE_1)
    assert any("SECTION 1: DEFINITIONS" in h for h in headings_1)

    headings_2 = service.detect_headings(POLICY_TEXT_PAGE_2)
    assert any("SECTION 4: EXCLUSIONS" in h for h in headings_2)


def test_policy_service_get_page():
    service = PolicyService()
    policy = service.prepare_policy(make_sample_pdf(), "health_policy.pdf")

    p1 = service.get_page(policy, 1)
    assert p1 is not None
    assert p1.page_number == 1
    assert "SECTION 1" in p1.text

    p2 = service.get_page(policy, 2)
    assert p2 is not None
    assert p2.page_number == 2

    # Out of bounds
    assert service.get_page(policy, 99) is None
    assert service.get_page(policy, 0) is None


def test_policy_service_preserves_citation_verification_safety():
    service = PolicyService()
    policy = service.prepare_policy(make_sample_pdf(), "health_policy.pdf")

    # Client returns fabricated quote
    bad_client = FakeStructuredClient({
        "verdict": "covered",
        "answer": "Everything is unconditionally covered.",
        "citations": [{"chunk_id": policy.chunks[0].chunk_id, "quote": "Completely made up text"}],
        "confidence": "high",
        "caveats": [],
    })

    result = service.ask_question(policy, "Is PED covered?", client=bad_client)
    assert result.manual_review_required is True
    assert result.citations_valid is False
    assert result.verdict == "depends"  # downgraded from covered
    assert result.confidence == "low"


def test_policy_service_custom_parameters_respected():
    service = PolicyService()
    # Test that max_extracted_chars threshold is strictly applied
    with pytest.raises(PolicyProcessingError):
        service.prepare_policy(make_sample_pdf(), "health_policy.pdf", max_extracted_chars=10)
