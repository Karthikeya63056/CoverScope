"""Verdict card component for CoverScope."""
from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.components.icons import (
    icon_alert_triangle,
    icon_check_circle,
    icon_help_circle,
    icon_x_circle,
)
from frontend.utils.view_models import VerdictViewModel


def _verdict_icon(verdict_key: str) -> str:
    if verdict_key == "covered":
        return icon_check_circle(size=16, color="#15803d")
    if verdict_key == "excluded":
        return icon_x_circle(size=16, color="#b91c1c")
    if verdict_key == "depends":
        return icon_alert_triangle(size=16, color="#b45309")
    return icon_help_circle(size=16, color="#475569")


def render_verdict_card(
    verdict: str | VerdictViewModel,
    *,
    manual_review_required: bool = False,
    citations_valid: bool = True,
) -> None:
    """Render the primary coverage verdict badge, verification status, and explanation.

    Parameters
    ----------
    verdict : str or VerdictViewModel
        The verdict key ('covered', 'excluded', 'depends', 'not_stated') or a VerdictViewModel.
    manual_review_required : bool
        Whether human review is required due to unverified citations or unreliable text.
    citations_valid : bool
        Whether all citations matched source policy chunks.
    """
    if isinstance(verdict, VerdictViewModel):
        vm = verdict
    else:
        vm = VerdictViewModel.from_verdict(str(verdict or "not_stated"))

    needs_manual_review = manual_review_required or not citations_valid
    icon_svg = _verdict_icon(vm.verdict_key)

    badge_html = (
        f'<span class="cs-badge {vm.badge_class}">'
        f'<span style="display:inline-flex; align-items:center;">{icon_svg}</span>'
        f"<span>{vm.display_label}</span>"
        f"</span>"
    )

    if needs_manual_review:
        status_chip = (
            '<span class="cs-chip cs-chip-warn">'
            '<span style="display:inline-flex; align-items:center;">'
            f'{icon_alert_triangle(size=12, color="#b45309")}</span>'
            '<span>Manual review</span></span>'
        )
    else:
        status_chip = (
            '<span class="cs-chip cs-chip-ok">'
            '<span style="display:inline-flex; align-items:center;">'
            f'{icon_check_circle(size=12, color="#15803d")}</span>'
            '<span>Citations verified</span></span>'
        )

    st.markdown(
        f'<div class="cs-answer-head">{badge_html}{status_chip}</div>',
        unsafe_allow_html=True,
    )

    if vm.summary_text:
        st.caption(vm.summary_text)
