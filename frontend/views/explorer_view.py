"""Policy Explorer workspace view for CoverScope."""
from __future__ import annotations

import streamlit as st

from backend.domain.enums import FactValidationStatus
from backend.qa.workflow import ProcessedPolicy
from backend.services.policy_service import PolicyService
from frontend.components.icons import (
    icon_alert_triangle,
    icon_file_text,
    icon_search,
    icon_shield,
)
from frontend.state import (
    VIEW_ASK,
    VIEW_LIBRARY,
    get_active_policy,
    policy_service,
    set_active_view,
)
from frontend.utils.formatters import clean_html, escape_md


def render_explorer_view() -> None:
    """Render the Policy Explorer clause and page inspection workspace."""
    policy: ProcessedPolicy | None = get_active_policy()

    st.markdown("## Policy Explorer")
    st.caption("Verbatim Clause & Document Browser — Inspect the exact text extracted from your policy.")

    # First-time buyer educational callout
    buyer_guidance_html = """
    <div class="cs-card" style="margin-bottom: 1.25rem; border-left: 3px solid #0f766e; background:#f0fdfa;">
      <div style="font-size:0.875rem; color:#0a2233; font-weight:600; margin-bottom:0.25rem;">
        First-Time Buyer Insight: Read the actual clauses
      </div>
      <div style="font-size:0.82rem; color:#334155; line-height:1.5;">
        Health insurance brochures highlight benefits, but the binding legal contract is in the policy wording.
        Use Policy Explorer to inspect the verbatim definitions, waiting periods, and exclusions before relying on
        summary claims. (Note: CoverScope is an informational reading tool; always verify details against your official policy schedule).
      </div>
    </div>
    """
    st.markdown(clean_html(buyer_guidance_html), unsafe_allow_html=True)

    if policy is None:
        _render_empty_explorer()
        return

    _render_active_explorer(policy)


def _render_empty_explorer() -> None:
    """Render guidance when no policy document is currently loaded."""
    search_icon = icon_file_text(size=24, color="#0f766e")
    empty_html = f"""
    <div class="cs-card" style="text-align:center; padding: 3rem 1.5rem; border-style:dashed;">
      <div style="display:inline-flex; margin-bottom:0.75rem;">{search_icon}</div>
      <h3 style="color:#0a2233; margin:0 0 0.5rem 0;">No active policy selected</h3>
      <p style="color:#64748b; font-size:0.9rem; max-width:480px; margin:0 auto 1.5rem auto; line-height:1.5;">
        Upload a health insurance policy wording in <strong>Ask My Policy</strong> or select an existing document from your <strong>Document Library</strong> to browse its verbatim pages and clauses.
      </p>
    </div>
    """
    st.markdown(clean_html(empty_html), unsafe_allow_html=True)

    cols = st.columns([1, 1, 2])
    with cols[0]:
        if st.button("Go to Ask My Policy", use_container_width=True, key="exp_to_ask"):
            set_active_view(VIEW_ASK)
            st.rerun()
    with cols[1]:
        if st.button("Open Document Library", use_container_width=True, key="exp_to_lib"):
            set_active_view(VIEW_LIBRARY)
            st.rerun()


def _render_active_explorer(policy: ProcessedPolicy) -> None:
    """Render the active document page inspector and text search interface."""
    escaped_name = escape_md(policy.filename)

    # Document Header Strip
    header_html = f"""
    <div class="cs-card" style="padding: 0.85rem 1.25rem; margin-bottom: 1rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
        <div style="display:flex; align-items:center; gap:0.6rem;">
          <span class="cs-doc-icon-badge" style="width:32px; height:32px;">{icon_file_text(size=18, color="#0f766e")}</span>
          <div>
            <div style="font-weight:700; color:#0a2233; font-size:1.05rem;">{escaped_name}</div>
            <div style="font-size:0.78rem; color:#64748b;">
              {policy.page_count:,} pages &bull; {policy.extracted_characters:,} characters &bull; {len(policy.chunks):,} searchable chunks
            </div>
          </div>
        </div>
        <span class="cs-chip cs-chip-ok">Extracted in Memory</span>
      </div>
    </div>
    """
    st.markdown(clean_html(header_html), unsafe_allow_html=True)

    # Extraction Quality Notices
    quality = getattr(policy, "quality", None)
    text_poor = tuple(getattr(quality, "text_poor_pages", ()) or ())
    table_pages = tuple(getattr(quality, "table_review_pages", ()) or ())

    if text_poor or table_pages:
        warn_cols = st.columns(2)
        if text_poor:
            warn_cols[0].warning(
                f"Low-text pages: {', '.join(map(str, text_poor))}. "
                "These pages contain little selectable text and may be images or blank.",
                icon="📄",
            )
        if table_pages:
            warn_cols[1].warning(
                f"Possible table pages: {', '.join(map(str, table_pages))}. "
                "Text extraction does not guarantee table column alignment; check tables manually.",
                icon="📊",
            )

    # Evidence-Linked Structured Facts (Phase 1.3)
    facts = policy_service.extract_facts(policy)
    with st.expander(f"Evidence-Linked Candidate Facts ({len(facts)})", expanded=bool(facts and len(facts) <= 6)):
        if facts:
            st.caption(
                "Grounded candidate facts deterministically identified from extracted wording. "
                "Quotation verification confirms the presence of the wording, not an unconditional coverage confirmation."
            )
            for f in facts[:10]:
                category_label = f.category.value.replace("_", " ").upper()
                ev = f.evidence_references[0] if f.evidence_references else None
                page_info = f"Page {ev.page_number}" if ev else "Page ?"
                quote_info = f' — *"{escape_md(ev.exact_text[:90])}"*' if ev else ""

                if f.validation_status == FactValidationStatus.NEEDS_REVIEW:
                    status_badge = '<span class="cs-chip cs-chip-warn" style="font-size:0.72rem; padding:0.12rem 0.4rem;">Requires Review</span>'
                elif f.is_evidence_grounded:
                    status_badge = '<span class="cs-chip cs-chip-ok" style="font-size:0.72rem; padding:0.12rem 0.4rem;">Source Quotation Verified</span>'
                else:
                    status_badge = '<span class="cs-chip" style="font-size:0.72rem; padding:0.12rem 0.4rem;">Candidate Extraction</span>'

                st.markdown(
                    f"- <span class=\"cs-chip\" style=\"font-size:0.72rem; padding:0.12rem 0.4rem;\">{category_label}</span> "
                    f"{status_badge} "
                    f"**{page_info}**: {escape_md(f.proposition)}{quote_info}",
                    unsafe_allow_html=True,
                )
                if f.review_reasons:
                    st.caption("  ⚠️ " + "; ".join(f.review_reasons))
            if len(facts) > 10:
                st.caption(f"Showing first 10 of {len(facts)} candidate facts.")
        else:
            st.caption(
                "No candidate facts automatically identified on this document. "
                "Browse verbatim pages below or ask targeted questions in Ask My Policy."
            )

    # Search & Filter Bar
    st.markdown("### Search Extracted Text")
    search_query = st.text_input(
        "Search policy wording",
        placeholder="Enter keyword (e.g., pre-existing, waiting period, cataract, room rent, exclusion)",
        label_visibility="collapsed",
        key="explorer_search_query",
    )

    if search_query and search_query.strip():
        hits = policy_service.search_policy_text(policy, search_query.strip())
        if hits:
            pages_hit = sorted({hit.page_number for hit in hits})
            st.success(
                f"Found {len(hits)} occurrences across {len(pages_hit)} pages: "
                f"Page(s) {', '.join(map(str, pages_hit))}"
            )
            with st.expander("Search Matches & Snippets", expanded=True):
                for hit in hits[:15]:
                    flags = []
                    if hit.is_table_review:
                        flags.append("Possible Table")
                    if hit.is_text_poor:
                        flags.append("Low Text")
                    flag_str = f" ({', '.join(flags)})" if flags else ""
                    st.markdown(
                        f"**Page {hit.page_number}**{flag_str} — *\"{hit.snippet}\"*"
                    )
                if len(hits) > 15:
                    st.caption(f"Showing first 15 of {len(hits)} occurrences.")
        else:
            st.info(f"No occurrences of '{search_query.strip()}' found in the extracted text.")

    st.divider()

    # Page-by-Page Browser
    st.markdown("### Page Browser")
    if not policy.pages:
        st.warning("Page-level breakdown is not cached for this document. Re-upload to enable page browsing.")
        return

    pages = list(policy.pages)
    selected_page_num = st.selectbox(
        "Select page",
        options=[p.page_number for p in pages],
        format_func=lambda p: f"Page {p} ({next(x.char_count for x in pages if x.page_number == p):,} characters)",
        key="explorer_page_selector",
    )

    current_page = next((p for p in pages if p.page_number == selected_page_num), None)
    if current_page:
        col_meta, col_diag = st.columns([3, 1])
        with col_meta:
            st.markdown(
                f"**Page {current_page.page_number} of {policy.page_count}** &middot; "
                f"`{current_page.char_count:,}` characters &middot; "
                f"`{current_page.text_block_count}` text blocks &middot; "
                f"`{current_page.image_count}` images"
            )
        with col_diag:
            if current_page.page_number in table_pages:
                st.caption("⚠️ Flagged for table review")
            elif current_page.page_number in text_poor:
                st.caption("⚠️ Low text page")
            else:
                st.caption("✓ Readability verified")

        headings = policy_service.detect_headings(current_page.text)
        if headings:
            st.markdown(
                "**Detected clause / section markers on this page:** "
                + " &bull; ".join(f"`{h[:45]}`" for h in headings[:5])
            )

        st.caption("Raw extracted wording (verbatim text from PDF):")
        with st.container(border=True):
            st.text(current_page.text)
