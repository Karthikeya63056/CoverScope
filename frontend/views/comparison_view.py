"""Policy Comparison and Protection Gaps workspace view for CoverScope.

Provides interactive, side-by-side policy clause comparisons grounded in verbatim text,
alongside conservative protection gap analysis and scenario-based cost sharing illustrations.
"""
from __future__ import annotations

from typing import Any
import streamlit as st

from backend.domain.comparison import (
    ComparisonAssumptions,
    DimensionComparison,
    PolicyComparisonEngine,
    PolicyComparisonResult,
    PolicyDimensionValue,
    ProtectionGap,
)
from backend.domain.enums import ComparisonDimensionKey, ComparisonStatus, ProtectionGapSeverity
from backend.qa.workflow import ProcessedPolicy
from frontend.components.icons import (
    icon_alert_triangle,
    icon_check_circle,
    icon_file_text,
    icon_help_circle,
    icon_shield,
    icon_x_circle,
)
from frontend.state import (
    ACTIVE_FP_KEY,
    COMPARISON_ASSUMPTIONS_KEY,
    COMPARISON_POLICY_A_KEY,
    COMPARISON_POLICY_B_KEY,
    COMPARISON_RESULT_KEY,
    VIEW_ASK,
    VIEW_EXPLORER,
    VIEW_LIBRARY,
    get_policy_schedule,
    get_registry,
    policy_service,
    set_active_policy,
    set_active_view,
)
from frontend.utils.formatters import clean_html, escape_md


def _comparison_status_chip(status: ComparisonStatus) -> str:
    """Return colored status badge matching CoverScope design system."""
    if status == ComparisonStatus.COMPARABLE:
        return '<span class="cs-chip cs-chip-ok" style="font-size:0.8rem; padding:0.2rem 0.55rem;">COMPARABLE</span>'
    elif status == ComparisonStatus.CONDITION_DEPENDENT:
        return '<span class="cs-chip" style="font-size:0.8rem; padding:0.2rem 0.55rem; background:rgba(245,158,11,0.15); border-color:#f59e0b; color:#b45309;">CONDITION-DEPENDENT</span>'
    elif status == ComparisonStatus.MISSING_FROM_DOCUMENTS:
        return '<span class="cs-chip" style="font-size:0.8rem; padding:0.2rem 0.55rem; background:rgba(100,116,139,0.12); border-color:#94a3b8; color:#475569;">NOT FOUND IN DOCS</span>'
    elif status == ComparisonStatus.NEEDS_REVIEW:
        return '<span class="cs-chip" style="font-size:0.8rem; padding:0.2rem 0.55rem; background:rgba(14,165,233,0.15); border-color:#0284c7; color:#0284c7;">NEEDS REVIEW</span>'
    else:
        return '<span class="cs-chip" style="font-size:0.8rem; padding:0.2rem 0.55rem; opacity:0.8;">NOT APPLICABLE</span>'


def _gap_severity_badge(severity: ProtectionGapSeverity) -> str:
    """Return visual severity indicator for protection gaps."""
    if severity == ProtectionGapSeverity.CAUTION:
        return '<span class="cs-chip cs-chip-warn" style="font-size:0.8rem; padding:0.2rem 0.55rem;">ATTENTION REQUIRED</span>'
    elif severity == ProtectionGapSeverity.CONDITIONAL_GAP:
        return '<span class="cs-chip" style="font-size:0.8rem; padding:0.2rem 0.55rem; background:rgba(245,158,11,0.15); border-color:#f59e0b; color:#b45309;">CONDITIONAL GAP</span>'
    elif severity == ProtectionGapSeverity.UNVERIFIED_GAP:
        return '<span class="cs-chip" style="font-size:0.8rem; padding:0.2rem 0.55rem; background:rgba(100,116,139,0.12); border-color:#94a3b8; color:#475569;">UNVERIFIED DETAIL</span>'
    else:
        return '<span class="cs-chip" style="font-size:0.8rem; padding:0.2rem 0.55rem; background:rgba(14,165,233,0.12); border-color:#0284c7; color:#0369a1;">INFORMATIONAL</span>'


def render_comparison_view() -> None:
    """Render the Policy Comparison and Protection Gaps workspace."""
    reg = get_registry()

    st.markdown(
        """
        <div style="margin-bottom:1.25rem;">
          <h2 style="margin:0 0 0.35rem 0; font-size:1.6rem; font-weight:700; color:#0f172a;">Policy Comparison & Protection Gaps</h2>
          <p style="margin:0; font-size:0.95rem; color:#475569;">
            Compare two health insurance policies side-by-side using verified document clauses.
            Identify documented differences, condition-dependent terms, and potential protection gaps.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # First-time buyer educational card
    with st.expander("📘 First-Time Buyer's Guide: How to Compare Two Health Policies", expanded=False):
        st.markdown(
            """
            - **Look Beyond Marketing Highlights:** Brochures often state 'Comprehensive Coverage', but binding contract conditions differ substantially in waiting periods, exclusions, and co-pays.
            - **Distinguish 'Missing' from 'Excluded':** If a clause is not found in the uploaded text, CoverScope marks it as *Not Found*. Never assume missing information means an exclusion or denial.
            - **Conditions Matter:** Reduced waiting periods or bariatric surgery coverage frequently require optional schedule endorsements or strict clinical thresholds (e.g. BMI ≥ 40).
            - **No 'Overall Winner':** The best policy depends on your personal health circumstances, age, pre-existing conditions, and whether you prefer lower premiums or zero co-payment.
            """
        )

    if not reg:
        _render_empty_comparison(0)
        return

    if len(reg) == 1:
        _render_single_policy_notice(next(iter(reg.values()))["policy"])

    # Policy Selectors
    st.markdown("<p style='font-size:0.85rem; font-weight:600; color:#334155; margin-bottom:0.25rem;'>SELECT TWO POLICIES TO COMPARE</p>", unsafe_allow_html=True)
    doc_keys = list(reg.keys())
    doc_options = {fp: rec["policy"].filename for fp, rec in reg.items()}

    col_a, col_b = st.columns(2)
    default_a = st.session_state.get(COMPARISON_POLICY_A_KEY) or doc_keys[0]
    default_b = st.session_state.get(COMPARISON_POLICY_B_KEY) or (doc_keys[1] if len(doc_keys) > 1 else doc_keys[0])

    if default_a not in doc_options:
        default_a = doc_keys[0]
    if default_b not in doc_options:
        default_b = doc_keys[1] if len(doc_keys) > 1 else doc_keys[0]

    with col_a:
        idx_a = doc_keys.index(default_a) if default_a in doc_keys else 0
        chosen_fp_a = st.selectbox(
            "Policy A (Primary)",
            options=doc_keys,
            format_func=lambda k: f"Policy A: {doc_options.get(k, k)}",
            index=idx_a,
            key="_cmp_sel_a",
        )
    with col_b:
        idx_b = doc_keys.index(default_b) if default_b in doc_keys else 0
        chosen_fp_b = st.selectbox(
            "Policy B (Comparison)",
            options=doc_keys,
            format_func=lambda k: f"Policy B: {doc_options.get(k, k)}",
            index=idx_b,
            key="_cmp_sel_b",
        )

    # Invalidate cached comparison if selections change
    if chosen_fp_a != default_a or chosen_fp_b != default_b:
        st.session_state[COMPARISON_POLICY_A_KEY] = chosen_fp_a
        st.session_state[COMPARISON_POLICY_B_KEY] = chosen_fp_b
        st.session_state.pop(COMPARISON_RESULT_KEY, None)

    policy_a = reg[chosen_fp_a]["policy"]
    policy_b = reg[chosen_fp_b]["policy"]

    if chosen_fp_a == chosen_fp_b:
        st.info("💡 Note: You have selected the same policy for both slots. This displays the policy's self-baseline comparison.")

    # Optional Assumptions Expander
    with st.expander("⚙️ Optional Scenario Assumptions for Gap Analysis", expanded=False):
        st.caption("Provide hypothetical member assumptions to evaluate active waiting periods and cost sharing:")
        ass_c1, ass_c2, ass_c3 = st.columns(3)
        with ass_c1:
            ass_age = st.number_input("Member Entry Age (Years)", min_value=0, max_value=100, value=65, key="_cmp_ass_age")
        with ass_c2:
            ass_months = st.number_input("Continuous Coverage Elapsed (Months)", min_value=0, max_value=120, value=20, key="_cmp_ass_months")
        with ass_c3:
            ass_claim = st.number_input("Hypothetical Claim Amount (INR)", min_value=0, value=100000, step=25000, key="_cmp_ass_claim")

    # Run Comparison Button
    run_clicked = st.button("Compare Policies & Analyze Protection Gaps", type="primary", key="_btn_run_comparison")
    schedule_a = get_policy_schedule(policy_a.fingerprint)
    schedule_b = get_policy_schedule(policy_b.fingerprint)

    if run_clicked or (st.session_state.get(COMPARISON_RESULT_KEY) is None):
        assumptions = ComparisonAssumptions(
            member_entry_age=int(ass_age),
            elapsed_months=int(ass_months),
            claim_amount=float(ass_claim) if ass_claim > 0 else None,
        )
        st.session_state[COMPARISON_ASSUMPTIONS_KEY] = assumptions
        result = policy_service.compare_policies(
            policy_a,
            policy_b,
            assumptions=assumptions,
            schedule_a=schedule_a,
            schedule_b=schedule_b,
        )
        st.session_state[COMPARISON_RESULT_KEY] = result

    # Render Result
    result: PolicyComparisonResult | None = st.session_state.get(COMPARISON_RESULT_KEY)
    if result is not None:
        # Defensive check: ensure result belongs to the currently selected policies
        if result.policy_a_fingerprint != policy_a.fingerprint or result.policy_b_fingerprint != policy_b.fingerprint:
            st.session_state.pop(COMPARISON_RESULT_KEY, None)
            return

        _render_comparison_result(result, policy_a, policy_b)


def _render_empty_comparison(doc_count: int) -> None:
    """Render guidance when insufficient policies are available for comparison."""
    st.markdown(
        """
        <div class="cs-card" style="text-align:center; padding:3rem 1.5rem; border-style:dashed;">
          <h3 style="color:#0a2233; margin:0 0 0.5rem 0;">No policies loaded for comparison</h3>
          <p style="color:#64748b; font-size:0.9rem; max-width:480px; margin:0 auto 1.5rem auto; line-height:1.5;">
            To compare policies side-by-side and evaluate protection gaps, upload at least two health insurance policy wordings in <strong>Ask My Policy</strong>.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Go to Ask My Policy", use_container_width=True, key="_cmp_to_ask"):
            set_active_view(VIEW_ASK)
            st.rerun()
    with c2:
        if st.button("Open Document Library", use_container_width=True, key="_cmp_to_lib"):
            set_active_view(VIEW_LIBRARY)
            st.rerun()


def _render_single_policy_notice(policy: ProcessedPolicy) -> None:
    """Render helpful callout when only 1 policy is in registry."""
    st.markdown(
        f"""
        <div class="cs-card" style="background:#f8fafc; border-left:3px solid #0284c7; margin-bottom:1rem; padding:0.85rem 1.15rem;">
          <strong style="color:#0369a1; font-size:0.9rem;">You have 1 policy loaded: {escape_md(policy.filename)}</strong>
          <p style="margin:0.25rem 0 0 0; font-size:0.83rem; color:#475569;">
            Upload a second policy in <strong>Ask My Policy</strong> or <strong>Document Library</strong> to compare it.
            You can also compare this document against itself to review its baseline clauses and protection gaps.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_comparison_result(
    result: PolicyComparisonResult,
    policy_a: ProcessedPolicy,
    policy_b: ProcessedPolicy,
) -> None:
    """Render the side-by-side comparison tables, evidence quotes, and protection gaps."""
    st.markdown("---")

    # Header summary strip
    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; flex-wrap:wrap; gap:0.5rem;">
          <h3 style="font-size:1.25rem; font-weight:700; color:#0f172a; margin:0;">Side-by-Side Dimension Comparison</h3>
          <span style="font-size:0.8rem; color:#64748b;">Grounded in {policy_a.page_count} pages (A) and {policy_b.page_count} pages (B)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render Dimension Comparison Cards
    for dim in result.dimensions:
        chip = _comparison_status_chip(dim.status)
        st.markdown(
            f"""
            <div class="cs-card" style="margin-bottom:1rem; padding:1rem 1.25rem;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                <span style="font-size:0.95rem; font-weight:700; color:#0f172a;">{escape_md(dim.dimension_label)}</span>
                {chip}
              </div>
              <div style="background:#f8fafc; border-radius:6px; padding:0.55rem 0.85rem; margin-bottom:0.75rem; font-size:0.86rem; color:#334155; border-left:3px solid #0284c7;">
                <strong>Comparison Takeaway:</strong> {escape_md(dim.summary_difference)}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Side by side columns for Policy A and Policy B
        val_col_a, val_col_b = st.columns(2)
        with val_col_a:
            _render_policy_value_card("Policy A", policy_a.filename, dim.policy_a_value)
        with val_col_b:
            _render_policy_value_card("Policy B", policy_b.filename, dim.policy_b_value)

        # Show evidence expander if either policy has evidence
        if dim.policy_a_value.evidence_quote or dim.policy_b_value.evidence_quote:
            with st.expander(f"Verbatim Document Clauses: {dim.dimension_label}", expanded=False):
                ev_c1, ev_c2 = st.columns(2)
                with ev_c1:
                    _render_evidence_quote("Policy A", policy_a.filename, dim.policy_a_value)
                with ev_c2:
                    _render_evidence_quote("Policy B", policy_b.filename, dim.policy_b_value)

        st.markdown("<div style='margin-bottom:1.25rem;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # Conservative Protection Gaps Section
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.markdown(
        """
        <div style="margin-bottom:1rem;">
          <h3 style="font-size:1.25rem; font-weight:700; color:#0f172a; margin:0 0 0.35rem 0;">Conservative Protection Gaps & Important Limitations</h3>
          <p style="margin:0; font-size:0.88rem; color:#475569;">
            Identified contractual limitations, active waiting periods, out-of-pocket co-payments, and unverified details.
            These are boundaries to be aware of, not necessarily defects of the insurance plan.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not result.protection_gaps:
        st.success("No active protection gaps or mandatory co-payment liabilities were identified under the current scenario assumptions.")
    else:
        for gap in result.protection_gaps:
            badge = _gap_severity_badge(gap.severity)
            st.markdown(
                f"""
                <div class="cs-verdict-box" style="margin-bottom:1rem; border-left-color:{'#e11d48' if gap.severity == ProtectionGapSeverity.CAUTION else '#0284c7'};">
                  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                    <span style="font-size:0.75rem; font-weight:700; color:#64748b; letter-spacing:0.04em;">APPLIES TO: {escape_md(gap.policy_filename)}</span>
                    {badge}
                  </div>
                  <h4 style="margin:0 0 0.4rem 0; font-size:1.05rem; font-weight:700; color:#0f172a;">{escape_md(gap.title)}</h4>
                  <p style="margin:0 0 0.5rem 0; font-size:0.88rem; line-height:1.5; color:#334155;">{escape_md(gap.description)}</p>
                  <div style="font-size:0.8rem; color:#0f766e; background:#f0fdfa; padding:0.45rem 0.75rem; border-radius:4px;">
                    <strong>Next Step:</strong> {escape_md(gap.resolution_guidance)}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if gap.evidence_quote:
                with st.expander(f"Supporting Clause in {gap.policy_filename} (Page {gap.source_page or '?'})", expanded=False):
                    st.markdown(
                        f"""
                        <blockquote style="margin:0; padding-left:0.75rem; border-left:3px solid #0f766e; font-style:italic; font-size:0.85rem; color:#334155;">
                          "{escape_md(gap.evidence_quote)}"
                        </blockquote>
                        """,
                        unsafe_allow_html=True,
                    )

    # -------------------------------------------------------------------------
    # Mandatory Regulatory Safeguards & Limitations
    # -------------------------------------------------------------------------
    with st.expander("Mandatory Policy & Regulatory Safeguards", expanded=True):
        st.caption("CoverScope maintains strict informational boundaries to protect consumers:")
        for lim in result.general_limitations:
            st.markdown(f"- <span style='font-size:0.84rem; color:#475569;'>{escape_md(lim)}</span>", unsafe_allow_html=True)

    # Direct Navigation back to individual policies
    st.markdown("<div style='margin-top:1.25rem;'></div>", unsafe_allow_html=True)
    c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1])
    with c_btn1:
        if st.button(f"Ask Questions on {escape_md(policy_a.filename[:18])}…", key="_cmp_ask_a"):
            set_active_policy(policy_a.fingerprint)
            set_active_view(VIEW_ASK)
            st.rerun()
    with c_btn2:
        if st.button(f"Ask Questions on {escape_md(policy_b.filename[:18])}…", key="_cmp_ask_b"):
            set_active_policy(policy_b.fingerprint)
            set_active_view(VIEW_ASK)
            st.rerun()
    with c_btn3:
        if st.button("Explore in Policy Explorer", key="_cmp_to_exp"):
            set_active_policy(policy_a.fingerprint)
            set_active_view(VIEW_EXPLORER)
            st.rerun()


def _render_policy_value_card(slot_label: str, filename: str, val: PolicyDimensionValue) -> None:
    """Render a clean card displaying a single policy's dimension value."""
    color = "#0f172a" if val.is_available else "#94a3b8"
    icon = icon_check_circle(size=14, color="#0f766e") if val.is_available else icon_x_circle(size=14, color="#94a3b8")
    page_hint = f"Page {val.source_page}" if val.source_page else "Not cited"

    st.markdown(
        f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:0.75rem 0.9rem;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
            <span style="font-size:0.75rem; font-weight:700; color:#64748b;">{slot_label}: {escape_md(filename)}</span>
            <span style="font-size:0.72rem; color:#0f766e; background:#f0fdfa; padding:0.15rem 0.4rem; border-radius:4px;">{page_hint}</span>
          </div>
          <div style="display:flex; align-items:center; gap:0.4rem; font-size:0.92rem; font-weight:600; color:{color};">
            {icon}
            <span>{escape_md(val.display_value)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_evidence_quote(slot_label: str, filename: str, val: PolicyDimensionValue) -> None:
    """Render verbatim evidence quotation block."""
    if not val.evidence_quote:
        st.caption(f"No verbatim quote extracted for {slot_label} ({escape_md(filename)}).")
        return

    st.markdown(
        f"""
        <div style="font-size:0.75rem; font-weight:600; color:#0f766e; margin-bottom:0.25rem;">
          {slot_label} ({escape_md(filename)}) — Page {val.source_page or '?'}
        </div>
        <blockquote style="margin:0 0 0.5rem 0; padding-left:0.65rem; border-left:3px solid #0f766e; font-style:italic; font-size:0.84rem; color:#334155;">
          "{escape_md(val.evidence_quote)}"
        </blockquote>
        """,
        unsafe_allow_html=True,
    )
