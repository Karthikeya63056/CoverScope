"""Focused unit tests for Stage H1 Brand Intro and Loading Experience."""
from __future__ import annotations

from unittest.mock import patch

from frontend.components.brand_intro import (
    HEADLINE,
    PAGE_TITLE,
    SUBTITLE,
    TAGLINE,
    TRUST_LINE,
    render_brand_intro,
    render_cinematic_intro,
    render_real_time_status,
)



def test_brand_intro_constants():
    assert PAGE_TITLE == "CoverScope"
    assert TAGLINE == "Your policy. Made clear."
    assert HEADLINE == "Clarity in every clause."
    assert "easier to understand" in SUBTITLE
    assert "Evidence-led" in TRUST_LINE


def test_render_brand_intro_full_and_compact():
    with patch("streamlit.markdown") as mock_markdown:
        render_brand_intro(compact=False)
        rendered_full = " ".join(call.args[0] for call in mock_markdown.call_args_list if call.args)

        assert PAGE_TITLE in rendered_full
        assert TAGLINE in rendered_full
        assert HEADLINE in rendered_full
        assert SUBTITLE in rendered_full
        assert TRUST_LINE in rendered_full
        assert "cs-intro-shimmer-bar" in rendered_full

    with patch("streamlit.markdown") as mock_markdown:
        render_brand_intro(compact=True)
        rendered_compact = " ".join(call.args[0] for call in mock_markdown.call_args_list if call.args)

        assert PAGE_TITLE in rendered_compact
        assert TAGLINE in rendered_compact
        assert "cs-brand-intro-compact" in rendered_compact


def test_render_real_time_status_card():
    with patch("streamlit.markdown") as mock_markdown:
        render_real_time_status(
            stage_title="Reading your policy document",
            stage_description="Extracting selectable clauses in memory.",
        )
        rendered = " ".join(call.args[0] for call in mock_markdown.call_args_list if call.args)

        assert "Reading your policy document" in rendered
        assert "Extracting selectable clauses" in rendered
        assert "cs-active-pulse-orb" in rendered


def test_render_cinematic_intro_lifecycle():
    import streamlit as st

    # Reset intro state
    st.session_state.pop("cs_intro_played", None)

    with patch("streamlit.markdown") as mock_markdown:
        # First play
        render_cinematic_intro(force_play=False)
        assert mock_markdown.called
        rendered = " ".join(call.args[0] for call in mock_markdown.call_args_list if call.args)

        # Check all scenes and controls
        assert "cs-cinematic-intro" in rendered
        assert "cs-intro-skip-btn" in rendered
        assert "Skip Intro" in rendered
        assert "cs-scene-doc-layer" in rendered
        assert "cs-scene-scanline" in rendered
        assert "cs-scene-clause-hud" in rendered
        assert "cs-scene-shield-layer" in rendered
        assert "Verified Policy Intelligence" in rendered
        assert PAGE_TITLE in rendered
        assert TAGLINE in rendered
        assert st.session_state["cs_intro_played"] is True

    with patch("streamlit.markdown") as mock_markdown2:
        # Second call without force_play should NOT render again
        render_cinematic_intro(force_play=False)
        assert not mock_markdown2.called

    with patch("streamlit.markdown") as mock_markdown3:
        # Forced replay should render again
        render_cinematic_intro(force_play=True)
        assert mock_markdown3.called
        rendered_replay = " ".join(call.args[0] for call in mock_markdown3.call_args_list if call.args)
        assert "cs-cinematic-intro" in rendered_replay
