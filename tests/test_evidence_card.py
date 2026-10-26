"""Focused tests for the Stage F Evidence & Citation Card component."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from frontend.components.evidence_card import render_evidence_card, render_evidence_section


def test_verified_citation_renders_metadata_and_quote():
    citation = SimpleNamespace(
        chunk_id="P2-C1",
        page_number=2,
        quote="Expenses incurred for cataract surgery are subject to a sublimit.",
        verified=True,
        warning=None,
    )

    with patch("streamlit.markdown") as mock_markdown, patch("streamlit.container"):
        render_evidence_card(citation)

        rendered_markdown = [call.args[0] for call in mock_markdown.call_args_list if call.args]
        joined = " ".join(rendered_markdown)

        assert "Page 2" in joined
        assert "P2-C1" in joined
        assert "Verified" in joined
        assert "cataract surgery" in joined


def test_unverified_or_failed_citation_not_styled_as_verified():
    failed_citation = SimpleNamespace(
        chunk_id="P5-C3",
        page_number=5,
        quote="Unverified claim text that failed Python matching.",
        verified=False,
        warning="Quotation does not match source text.",
    )

    with patch("streamlit.markdown") as mock_markdown, patch("streamlit.caption") as mock_caption, patch("streamlit.container"):
        render_evidence_card(failed_citation)

        rendered_markdown = [call.args[0] for call in mock_markdown.call_args_list if call.args]
        joined = " ".join(rendered_markdown)

        assert "Unverified" in joined
        assert "cs-chip-warn" in joined
        # Must never have the success chip
        assert "cs-chip-ok" not in joined

        caption_calls = [call.args[0] for call in mock_caption.call_args_list if call.args]
        assert any("Quotation does not match source text." in cap for cap in caption_calls)


def test_missing_evidence_renders_useful_empty_state():
    with patch("streamlit.caption") as mock_caption, patch("streamlit.markdown") as mock_markdown:
        render_evidence_section([])

        caption_calls = [call.args[0] for call in mock_caption.call_args_list if call.args]
        assert any("No verified quotations were returned" in cap for cap in caption_calls)


def test_missing_page_number_or_chunk_id_avoids_fabrication():
    sparse_citation = SimpleNamespace(
        chunk_id="",
        page_number=None,
        quote="Some quote with missing page number and chunk id.",
        verified=True,
        warning=None,
    )

    with patch("streamlit.markdown") as mock_markdown, patch("streamlit.container"):
        render_evidence_card(sparse_citation)

        rendered = " ".join(call.args[0] for call in mock_markdown.call_args_list if call.args)

        # Must not fabricate "Page 1"
        assert "Page 1" not in rendered
        assert "Page unlisted" in rendered
        assert "Source chunk unlisted" in rendered


def test_quote_containing_html_rendered_as_plain_markdown():
    xss_quote = '<script>alert("xss")</script><b>Bold policy term</b>'
    citation = SimpleNamespace(
        chunk_id="P1-C1",
        page_number=1,
        quote=xss_quote,
        verified=True,
        warning=None,
    )

    with patch("streamlit.markdown") as mock_markdown, patch("streamlit.container"):
        render_evidence_card(citation)

        # Quotes are rendered with markdown blockquote
        markdown_calls = [call.args[0] for call in mock_markdown.call_args_list if call.args]
        quote_render_call = [call for call in mock_markdown.call_args_list if xss_quote in str(call)]
        assert quote_render_call, "The quote was not passed to markdown"
        # Must NOT be rendered with unsafe_allow_html=True
        for call in quote_render_call:
            kwargs = call.kwargs
            assert not kwargs.get("unsafe_allow_html", False)


def test_multiple_citations_render_independently_in_order():
    citations = [
        SimpleNamespace(chunk_id="P1-C1", page_number=1, quote="First quote", verified=True, warning=None),
        SimpleNamespace(chunk_id="P2-C2", page_number=2, quote="Second quote", verified=True, warning=None),
        SimpleNamespace(chunk_id="P3-C3", page_number=3, quote="Third quote", verified=False, warning=None),
    ]

    with patch("streamlit.markdown") as mock_markdown, patch("streamlit.container"):
        render_evidence_section(citations)

        rendered = " ".join(call.args[0] for call in mock_markdown.call_args_list if call.args)
        pos1 = rendered.find("P1-C1")
        pos2 = rendered.find("P2-C2")
        pos3 = rendered.find("P3-C3")

        assert pos1 != -1 and pos2 != -1 and pos3 != -1
        assert pos1 < pos2 < pos3


def test_render_evidence_card_none_handled_safely():
    # Calling with None does not crash
    render_evidence_card(None)
