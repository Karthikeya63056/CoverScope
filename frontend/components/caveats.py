"""Caveats, policy conditions, and manual review warnings component for CoverScope."""
from __future__ import annotations

from typing import Sequence

import streamlit as st

from frontend.messages import MANUAL_REVIEW_MESSAGE


def render_manual_review_banner(
    manual_review_required: bool = False,
    citations_valid: bool = True,
) -> None:
    """Render prominent alert when manual review is required."""
    if manual_review_required or not citations_valid:
        st.warning(MANUAL_REVIEW_MESSAGE, title="Manual review required", icon="⚠️")


def render_caveats_and_warnings(
    *,
    warnings: Sequence[str] = (),
    caveats: Sequence[str] = (),
    unverified_answer: str | None = None,
) -> None:
    """Render verification warnings, policy caveats, and unverified model answers.

    Parameters
    ----------
    warnings : Sequence[str]
        System verification warnings (e.g., citation quotation mismatches).
    caveats : Sequence[str]
        Policy limitations, plan-dependent conditions, or missing information notes.
    unverified_answer : str, optional
        The unverified raw model text when citation validation failed.
    """
    distinct_caveats = [item for item in caveats if item not in warnings]

    if warnings:
        st.markdown("#### Verification warnings")
        for warning in warnings:
            st.markdown(f"- {warning}")

    if distinct_caveats:
        st.markdown("#### Policy caveats")
        for caveat in distinct_caveats:
            st.markdown(f"- {caveat}")

    if unverified_answer and unverified_answer.strip():
        with st.expander("Unverified model answer — not a coverage decision"):
            st.write(unverified_answer)
