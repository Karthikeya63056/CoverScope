"""Confidence and citation verification component for CoverScope."""
from __future__ import annotations

from typing import Sequence

import streamlit as st

from frontend.utils.formatters import confidence_label


def render_confidence_metrics(
    confidence: str,
    *,
    citations_valid: bool,
    cited_pages: Sequence[int] | str,
) -> None:
    """Render model-reported confidence and Python citation verification metrics.

    Parameters
    ----------
    confidence : str
        The confidence level ('high', 'medium', 'low') reported by the LLM.
    citations_valid : bool
        Whether Python-side verbatim matching succeeded for all citations.
    cited_pages : Sequence[int] or str
        The unique page numbers referenced in the answer citations.
    """
    conf_display = confidence_label(confidence or "low")
    cite_check_display = "Verified" if citations_valid else "Failed"

    if isinstance(cited_pages, str):
        pages_display = cited_pages
    elif cited_pages:
        pages_display = ", ".join(map(str, cited_pages))
    else:
        pages_display = "None"

    metric_columns = st.columns(3)
    metric_columns[0].metric(
        "Model-reported confidence",
        conf_display,
        help="Reported by the model. This is not a guarantee that the verdict is correct.",
    )
    metric_columns[1].metric(
        "Citation check",
        cite_check_display,
        help="Every quotation is verified in Python against the retrieved policy text.",
    )
    metric_columns[2].metric(
        "Cited pages",
        pages_display,
    )

    st.caption(
        "Confidence is reported by the model and is not a guarantee of correctness. "
        "A valid quotation confirms the wording, not the coverage decision."
    )
