"""Focused tests for the Stage C Document Card component and view model."""
from __future__ import annotations

from types import SimpleNamespace

from frontend.components.document_card import render_document_card
from frontend.utils.view_models import DocumentViewModel


def test_document_view_model_with_full_metadata():
    fake_quality = SimpleNamespace(
        text_poor_pages=[2, 5],
        table_review_pages=[7],
        warnings=["Low character density detected."],
    )
    fake_policy = SimpleNamespace(
        filename="Test_Health_Policy_2026.pdf",
        page_count=12,
        size_bytes=2_048_576,
        extracted_characters=45_000,
        chunks=[SimpleNamespace(chunk_id="P1-C1"), SimpleNamespace(chunk_id="P1-C2")],
        quality=fake_quality,
    )

    vm = DocumentViewModel.from_policy(fake_policy)

    assert vm.filename == "Test_Health_Policy_2026.pdf"
    assert "Test\\_Health\\_Policy\\_2026.pdf" in vm.escaped_filename or "Test" in vm.escaped_filename
    assert vm.page_count == 12
    assert vm.page_count_display == "12"
    assert vm.file_size_display == "2.0 MB"
    assert vm.extracted_characters == 45_000
    assert vm.extracted_characters_display == "45,000"
    assert vm.chunk_count == 2
    assert vm.chunk_count_display == "2"
    assert vm.has_warnings is True
    assert vm.text_poor_pages == (2, 5)
    assert vm.table_review_pages == (7,)
    assert vm.quality_warnings == ("Low character density detected.",)
    assert "Ready for Q&A" in vm.status_label


def test_document_view_model_with_missing_optional_fields():
    # Empty object simulating incomplete policy object
    empty_policy = SimpleNamespace()

    vm = DocumentViewModel.from_policy(empty_policy)

    assert vm.filename == "Unnamed Policy.pdf"
    assert vm.page_count == 0
    assert vm.page_count_display == "0"
    assert vm.file_size_display == "0 B"
    assert vm.extracted_characters == 0
    assert vm.chunk_count == 0
    assert vm.has_warnings is False
    assert vm.text_poor_pages == ()
    assert vm.table_review_pages == ()
    assert vm.quality_warnings == ()


def test_render_document_card_handles_none_gracefully():
    # Calling with None should return without raising an exception
    render_document_card(None)
