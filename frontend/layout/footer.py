"""Footer and legal disclaimer layout for CoverScope."""
from __future__ import annotations

import streamlit as st


def render_footer() -> None:
    """Render the standardized bottom disclaimer and provenance note."""
    st.divider()
    st.markdown(
        """
        <div class="cs-footer">
          <strong>CoverScope</strong> is an evidence-grounded policy interpretation tool.
          Verdicts reflect the retrieved wording of the uploaded document and may omit
          exclusions or conditions stated elsewhere in the complete policy schedule or endorsement.
          This tool does not constitute legal or insurance advice and does not bind any insurer.
          Always verify coverage details against your official policy schedule with your insurance provider.
        </div>
        """,
        unsafe_allow_html=True,
    )
