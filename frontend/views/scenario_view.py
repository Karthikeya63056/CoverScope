"""Scenario Analyzer workspace view for CoverScope.

Provides interactive, deterministic scenario evaluations grounded in extracted
policy facts, explicit mathematical rules, and verbatim source citations.
"""
from __future__ import annotations

from datetime import date
from typing import Any
import streamlit as st

from backend.domain.enums import ScenarioType, ScenarioVerdict
from backend.domain.scenario import ScenarioEvaluator, ScenarioInput, ScenarioResult
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
    SCENARIO_INPUT_KEY,
    SCENARIO_RESULT_KEY,
    VIEW_ASK,
    get_active_policy,
    get_policy_schedule,
    get_registry,
    policy_service,
    set_active_policy,
    set_active_view,
)
from frontend.utils.formatters import clean_html, escape_md

SCENARIO_LABELS: dict[ScenarioType, str] = {
    ScenarioType.PRE_EXISTING_CONDITION: "Pre-Existing Disease (PED) Waiting Period",
    ScenarioType.INITIAL_WAITING_PERIOD: "Initial 30-Day Illness Waiting Period",
    ScenarioType.CONDITIONAL_EXCLUSION: "Conditional Exclusion & Exception Check",
    ScenarioType.ENTRY_AGE_COPAYMENT: "Entry-Age Co-Payment & Claim Share",
}

LABEL_TO_SCENARIO: dict[str, ScenarioType] = {v: k for k, v in SCENARIO_LABELS.items()}


def _verdict_chip_html(verdict: ScenarioVerdict) -> str:
    """Return colored status badge matching CoverScope design system."""
    if verdict == ScenarioVerdict.WAITING_PERIOD_SATISFIED:
        return '<span class="cs-chip cs-chip-ok" style="font-size:0.85rem; padding:0.25rem 0.6rem;">WAITING PERIOD SATISFIED</span>'
    elif verdict == ScenarioVerdict.WAITING_PERIOD_ACTIVE:
        return '<span class="cs-chip cs-chip-warn" style="font-size:0.85rem; padding:0.25rem 0.6rem;">WAITING PERIOD ACTIVE</span>'
    elif verdict == ScenarioVerdict.CONDITIONAL_REVIEW:
        return '<span class="cs-chip" style="font-size:0.85rem; padding:0.25rem 0.6rem; background:rgba(14,165,233,0.15); border-color:#0284c7; color:#0284c7;">REQUIRES REVIEW</span>'
    elif verdict == ScenarioVerdict.EXCLUSION_IDENTIFIED:
        return '<span class="cs-chip cs-chip-warn" style="font-size:0.85rem; padding:0.25rem 0.6rem; background:rgba(225,29,72,0.12); border-color:#e11d48; color:#e11d48;">EXCLUSION IDENTIFIED</span>'
    elif verdict == ScenarioVerdict.INSUFFICIENT_EVIDENCE:
        return '<span class="cs-chip" style="font-size:0.85rem; padding:0.25rem 0.6rem; opacity:0.8;">INSUFFICIENT EVIDENCE</span>'
    else:
        return '<span class="cs-chip" style="font-size:0.85rem; padding:0.25rem 0.6rem; opacity:0.8;">UNSUPPORTED SCENARIO</span>'


def render_scenario_view() -> None:
    """Render the deterministic Scenario Analysis workspace."""
    policy = get_active_policy()
    reg = get_registry()

    st.markdown(
        """
        <div style="margin-bottom:1.25rem;">
          <h2 style="margin:0 0 0.35rem 0; font-size:1.6rem; font-weight:700; color:#0f172a;">Scenario Analyzer</h2>
          <p style="margin:0; font-size:0.95rem; color:#475569;">
            Evaluate deterministic insurance scenarios against verified policy clauses.
            All verdicts are computed by strict mathematical rules and grounded in verbatim document evidence.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("📘 First-Time Buyer's Guide: Understanding Health Policy Rules", expanded=False):
        st.markdown(
            """
            - **Pre-Existing Disease (PED) Waiting Period:** A defined duration (e.g., 36 or 48 months in base plans; or shorter via optional buy-back riders) during which treatments related to pre-existing conditions are excluded. Coverage requires continuous policy renewal without lapse.
            - **Initial 30-Day Illness Waiting Period:** Under standard IRDAI guidelines (Code-Excl03), illness treatments are not covered in the first 30 days after policy commencement. **Emergency hospitalization necessitated solely by an accidental injury is legally exempt.**
            - **Specific Disease Waiting Periods:** Certain treatments (e.g., cataract, hernia, joint replacement, hysterectomy) typically have a mandatory 24-month waiting period regardless of pre-existing disease status.
            - **Entry-Age Co-Payment:** If an insured member enters the policy above a specified threshold age (commonly 61+ years), the insurer mandates that the member pay a fixed percentage (e.g., 10% or 20%) of each admissible claim.
            - **Admissibility & Limits:** Scenario calculations evaluate contractual rules based on policy text. Deductibles, room-rent sub-limits, non-payable medical consumables, and sum insured limits are evaluated separately by the claim administrator.
            """
        )

    # Policy Switcher if multiple documents in registry
    if len(reg) > 1:
        st.markdown("<p style='font-size:0.82rem; font-weight:600; color:#475569; margin-bottom:0.25rem;'>SELECTED POLICY</p>", unsafe_allow_html=True)
        doc_options = {fp: rec["policy"].filename for fp, rec in reg.items()}
        current_fp = st.session_state.get(ACTIVE_FP_KEY)
        chosen_fp = st.selectbox(
            "Select Policy to Analyze",
            options=list(doc_options.keys()),
            format_func=lambda k: doc_options.get(k, k),
            index=list(doc_options.keys()).index(current_fp) if current_fp in doc_options else 0,
            key="_scenario_policy_selector",
            label_visibility="collapsed",
        )
        if chosen_fp and chosen_fp != current_fp:
            set_active_policy(chosen_fp)
            policy = get_active_policy()

    if policy is None:
        st.info("No policy document is currently active. Upload a health insurance policy in Ask My Policy or Document Library to run scenarios.")
        return

    # Scenario Selection
    col_type, col_space = st.columns([2, 1])
    with col_type:
        st.markdown("<p style='font-size:0.85rem; font-weight:600; color:#334155; margin-bottom:0.25rem;'>SELECT SCENARIO TYPE</p>", unsafe_allow_html=True)
        selected_label = st.selectbox(
            "Scenario Type",
            options=list(SCENARIO_LABELS.values()),
            key="_scenario_type_selector",
            label_visibility="collapsed",
        )
        scenario_type = LABEL_TO_SCENARIO[selected_label]

    st.markdown("---")

    schedule = get_policy_schedule(policy.fingerprint)
    has_sched_ped_rider = False
    if schedule:
        has_sched_ped_rider = any("ped" in r.lower() or "pre-existing" in r.lower() for r in schedule.optional_riders)
        st.markdown(
            f"""
            <div style="background:#f0fdfa; border:1px solid #ccfbf1; border-radius:6px; padding:0.6rem 0.85rem; margin-bottom:1rem;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.85rem; font-weight:700; color:#0f766e;">📄 Attached Policy Schedule: {escape_md(schedule.filename)}</span>
                <span class="cs-chip cs-chip-ok" style="font-size:0.7rem; padding:0.15rem 0.45rem;">Schedule Grounded</span>
              </div>
              <div style="font-size:0.8rem; color:#334155; margin-top:0.25rem;">
                <strong>Policy Inception:</strong> {schedule.inception_date or 'N/A'} &bull;
                <strong>Sum Insured:</strong> {f'₹{schedule.sum_insured:,.0f}' if schedule.sum_insured else 'Not stated'} &bull;
                <strong>Members:</strong> {len(schedule.members)} loaded &bull;
                <strong>Active Riders:</strong> {len(schedule.optional_riders)}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Dynamic Inputs Form
    with st.container():
        st.markdown(f"<h3 style='font-size:1.1rem; font-weight:600; margin-bottom:0.75rem; color:#1e293b;'>Scenario Parameters: {selected_label}</h3>", unsafe_allow_html=True)

        scenario_input: ScenarioInput | None = None

        if scenario_type == ScenarioType.PRE_EXISTING_CONDITION:
            mode = st.radio(
                "Input Timing Mode",
                options=["Elapsed Months", "Exact Policy Dates"],
                horizontal=True,
                key="_ped_timing_mode",
            )
            elapsed_m: int | None = None
            incept_str: str | None = None
            incid_str: str | None = None

            if mode == "Elapsed Months":
                elapsed_m = st.number_input(
                    "Continuous Coverage Duration (Months)",
                    min_value=0,
                    max_value=120,
                    value=20,
                    help="Number of full months the insured has held this policy continuously without a break.",
                    key="_ped_elapsed_m",
                )
            else:
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    d_default = date.fromisoformat(schedule.inception_date) if (schedule and schedule.inception_date) else date(2024, 1, 15)
                    d_incept = st.date_input("First Policy Inception Date", value=d_default, key="_ped_d_incept")
                    incept_str = d_incept.isoformat() if d_incept else None
                with d_col2:
                    d_incid = st.date_input("Claim / Hospitalization Date", value=date(2025, 9, 15), key="_ped_d_incid")
                    incid_str = d_incid.isoformat() if d_incid else None

            buyback_label = "Insured purchased optional PED buy-back cover / waiting time reduction rider"
            if has_sched_ped_rider:
                buyback_label += " (✓ Confirmed on Policy Schedule)"

            has_buyback = st.checkbox(
                buyback_label,
                value=has_sched_ped_rider,
                help="Applies if policyholder elected an optional rider reducing waiting time (e.g. from 36 months to 12 months).",
                key="_ped_has_buyback",
            )

            if st.button("Analyze Pre-Existing Condition Scenario", type="primary", key="_ped_btn"):
                scenario_input = ScenarioInput(
                    scenario_type=ScenarioType.PRE_EXISTING_CONDITION,
                    elapsed_months=elapsed_m,
                    inception_date=incept_str,
                    incident_date=incid_str,
                    is_pre_existing=True,
                    has_buyback_rider=has_buyback,
                    has_schedule_endorsement=bool(has_buyback and has_sched_ped_rider),
                )

        elif scenario_type == ScenarioType.INITIAL_WAITING_PERIOD:
            mode = st.radio(
                "Input Timing Mode",
                options=["Days Elapsed", "Exact Policy Dates"],
                horizontal=True,
                key="_init_timing_mode",
            )
            elapsed_d: int | None = None
            incept_str: str | None = None
            incid_str: str | None = None

            if mode == "Days Elapsed":
                elapsed_d = st.number_input(
                    "Days Elapsed Since Policy Commencement",
                    min_value=0,
                    max_value=365,
                    value=15,
                    help="Days elapsed between policy inception and first symptom or hospitalization.",
                    key="_init_elapsed_d",
                )
            else:
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    d_incept = st.date_input("First Policy Commencement Date", value=date(2025, 1, 1), key="_init_d_incept")
                    incept_str = d_incept.isoformat() if d_incept else None
                with d_col2:
                    d_incid = st.date_input("Date of Illness / Admission", value=date(2025, 1, 16), key="_init_d_incid")
                    incid_str = d_incid.isoformat() if d_incid else None

            is_accident = st.checkbox(
                "Hospitalization was necessitated solely by an accidental injury",
                value=False,
                help="Accidental injuries are legally exempt from the 30-day initial waiting period under IRDAI guidelines.",
                key="_init_is_accident",
            )

            if st.button("Analyze Initial Waiting Period Scenario", type="primary", key="_init_btn"):
                scenario_input = ScenarioInput(
                    scenario_type=ScenarioType.INITIAL_WAITING_PERIOD,
                    elapsed_days=elapsed_d,
                    inception_date=incept_str,
                    incident_date=incid_str,
                    is_accidental_injury=is_accident,
                )

        elif scenario_type == ScenarioType.CONDITIONAL_EXCLUSION:
            cond_choice = st.selectbox(
                "Select Treatment / Condition Clause to Evaluate",
                options=[
                    "Obesity / Weight Control Surgery",
                    "Alcoholism & Substance Abuse",
                    "Admission Primarily for Diagnostics / Evaluation",
                    "Rest Cure & Respite Care",
                ],
                key="_excl_cond_choice",
            )

            st.caption("Evaluates whether the policy treats this provision as an absolute exclusion or permits conditional exceptions upon clinical review.")

            if st.button("Analyze Exclusion Clause", type="primary", key="_excl_btn"):
                scenario_input = ScenarioInput(
                    scenario_type=ScenarioType.CONDITIONAL_EXCLUSION,
                    condition_name=cond_choice,
                )

        elif scenario_type == ScenarioType.ENTRY_AGE_COPAYMENT:
            default_age = 65
            if schedule and schedule.members:
                st.markdown("<p style='font-size:0.82rem; font-weight:600; color:#475569; margin-bottom:0.25rem;'>SELECT INSURED MEMBER FROM SCHEDULE</p>", unsafe_allow_html=True)
                m_names = [f"{m.name} (Age: {m.age if m.age is not None else 'N/A'}, Relation: {m.relation or 'Self'})" for m in schedule.members]
                chosen_idx = st.selectbox(
                    "Insured Member",
                    options=range(len(schedule.members)),
                    format_func=lambda i: m_names[i],
                    key="_copay_member_idx",
                )
                m_obj = schedule.members[chosen_idx]
                if m_obj.age is not None:
                    default_age = m_obj.age
                    st.caption(f"💡 Pre-populated entry age **{m_obj.age}** from Policy Schedule for {m_obj.name}.")

            col_age, col_claim = st.columns(2)
            with col_age:
                entry_age = st.number_input(
                    "Insured Person Age at Entry (Years)",
                    min_value=0,
                    max_value=100,
                    value=int(default_age),
                    help="Age of the insured member when the policy was first issued.",
                    key="_copay_age",
                )
            with col_claim:
                claim_val = st.number_input(
                    "Proposed Admissible Claim Amount (INR, Optional)",
                    min_value=0,
                    value=100000,
                    step=10000,
                    help="Leave at 0 or enter hypothetical admissible claim to calculate patient/insurer cost sharing.",
                    key="_copay_claim",
                )

            if st.button("Analyze Co-Payment Scenario", type="primary", key="_copay_btn"):
                scenario_input = ScenarioInput(
                    scenario_type=ScenarioType.ENTRY_AGE_COPAYMENT,
                    member_age_at_entry=int(entry_age),
                    claim_amount=float(claim_val) if claim_val > 0 else None,
                )

    # Execute evaluation if triggered
    if scenario_input is not None:
        evaluator = ScenarioEvaluator()
        result = evaluator.evaluate(policy, scenario_input, schedule=schedule)
        st.session_state[SCENARIO_INPUT_KEY] = scenario_input
        st.session_state[SCENARIO_RESULT_KEY] = result

    # Display Result
    result: ScenarioResult | None = st.session_state.get(SCENARIO_RESULT_KEY)
    if result is not None:
        # Prevent cross-policy contamination and stale scenario type leakage
        matches_policy = (not getattr(result, "policy_fingerprint", "")) or (result.policy_fingerprint == policy.fingerprint)
        matches_type = (result.scenario_type == scenario_type)
        if matches_policy and matches_type:
            st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
            _render_scenario_result(result, policy)


def _render_scenario_result(result: ScenarioResult, policy: ProcessedPolicy) -> None:
    """Render structured scenario result card, evidence quotes, and limitations."""
    chip = _verdict_chip_html(result.verdict)

    support_tag = ""
    if result.evidentiary_support:
        support_tag = f"""
        <div style="font-size:0.75rem; font-weight:600; color:#0f766e; margin-top:0.35rem; display:flex; align-items:center; gap:0.3rem;">
          <span style="background:#ccfbf1; color:#0f766e; padding:0.15rem 0.5rem; border-radius:4px; font-weight:700;">EVIDENCE GROUNDING</span>
          {escape_md(result.evidentiary_support)}
        </div>
        """

    formula_html = ""
    if result.calculation_formula:
        formula_html = f"""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; padding:0.5rem 0.75rem; border-radius:6px; margin:0.6rem 0; font-family:monospace; font-size:0.83rem; color:#334155;">
          <strong>Rule / Formula:</strong> {escape_md(result.calculation_formula)}
        </div>
        """

    assumptions_html = ""
    if result.user_assumptions:
        assumptions_html = f"""
        <div style="margin:0.5rem 0; font-size:0.82rem; color:#64748b;">
          <strong>User Assumptions:</strong>
          <ul style="margin:0.2rem 0 0 1rem; padding:0;">
            {"".join(f"<li>{escape_md(a)}</li>" for a in result.user_assumptions)}
          </ul>
        </div>
        """

    st.markdown(
        f"""
        <div class="cs-verdict-box" style="margin-bottom:1.25rem;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
            <span style="font-size:0.8rem; font-weight:700; color:#64748b; letter-spacing:0.04em;">DETERMINISTIC EVALUATION VERDICT</span>
            {chip}
          </div>
          <h3 style="margin:0 0 0.5rem 0; font-size:1.25rem; font-weight:700; color:#0f172a;">{escape_md(result.headline)}</h3>
          <p style="margin:0; font-size:0.95rem; line-height:1.5; color:#334155;">{escape_md(result.explanation)}</p>
          {formula_html}
          {support_tag}
          {assumptions_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Quantitative Breakdown Metrics
    if result.calculated_copayment_amount is not None and result.calculated_insurer_portion is not None:
        st.markdown("<p style='font-size:0.82rem; font-weight:600; color:#475569; margin-bottom:0.35rem;'>SIMPLIFIED CLAIM SHARE ILLUSTRATION</p>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("Patient Co-Payment", f"₹{result.calculated_copayment_amount:,.0f}", f"{result.copayment_percentage:g}% Share")
        m2.metric("Calculated Insurer Portion", f"₹{result.calculated_insurer_portion:,.0f}", f"{100.0 - (result.copayment_percentage or 0.0):g}% Base")
        claim_tot = (result.calculated_copayment_amount or 0) + (result.calculated_insurer_portion or 0)
        m3.metric("Hypothetical Admissible Claim", f"₹{claim_tot:,.0f}")
        st.caption("💡 Note: This illustration calculates cost-sharing on admissible expenses. Deductibles, room rent limits, and non-medical exclusions apply separately.")
    elif result.applicable_duration_amount is not None and result.elapsed_duration_amount is not None:
        d1, d2, d3 = st.columns(3)
        unit = result.applicable_duration_unit or "months"
        d1.metric("Policy Waiting Period", f"{result.applicable_duration_amount} {unit}")
        d2.metric("Continuous Coverage", f"{result.elapsed_duration_amount} {unit}")
        rem = result.remaining_duration_amount or 0
        rem_label = "Satisfied" if rem == 0 else f"{rem} {unit} to go"
        d3.metric("Remaining Duration", f"{rem} {unit}", rem_label)

    # Supporting Evidence Section
    if result.source_references:
        st.markdown("<h4 style='font-size:1.0rem; font-weight:600; margin-top:1.2rem; color:#1e293b;'>Grounded Policy Document Evidence</h4>", unsafe_allow_html=True)
        for ref in result.source_references:
            page_no = ref.get("page_number", "?")
            doc_name = ref.get("document", policy.filename)
            quote = ref.get("quote", "")
            st.markdown(
                f"""
                <div class="cs-evidence-card" style="margin-bottom:0.75rem;">
                  <div style="font-size:0.75rem; font-weight:600; color:#0f766e; margin-bottom:0.3rem;">
                    Page {page_no} of {escape_md(doc_name)}
                  </div>
                  <blockquote style="margin:0; padding-left:0.75rem; border-left:3px solid #0f766e; font-style:italic; font-size:0.9rem; color:#334155;">
                    "{escape_md(quote)}"
                  </blockquote>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Unresolved Conditions & Clinical Protocols
    if result.unresolved_conditions:
        st.markdown(
            """
            <div style="background:#fffbeb; border:1px solid #fef3c7; border-left:4px solid #f59e0b; padding:0.75rem 1rem; border-radius:6px; margin-top:1rem;">
              <strong style="color:#b45309; font-size:0.88rem;">Unresolved Conditions & Verification Requirements:</strong>
              <ul style="margin:0.4rem 0 0 1.1rem; padding:0; color:#92400e; font-size:0.85rem;">
            """
            + "".join(f"<li>{escape_md(cond)}</li>" for cond in result.unresolved_conditions)
            + "</ul></div>",
            unsafe_allow_html=True,
        )

    # Limitations & Consumer Safeguards Callout
    if result.limitations:
        with st.expander("Mandatory Policy & Regulatory Safeguards", expanded=True):
            st.caption("To protect policyholders from misinterpretation, deterministic evaluations enforce these explicit boundaries:")
            for lim in result.limitations:
                st.markdown(f"- <span style='font-size:0.85rem; color:#475569;'>{escape_md(lim)}</span>", unsafe_allow_html=True)

    # Direct Fallback to Q&A Workspace
    st.markdown("<div style='margin-top:1.25rem;'></div>", unsafe_allow_html=True)
    f_col1, f_col2 = st.columns([3, 1])
    with f_col1:
        st.caption("Need contextual reasoning, clinical explanation, or customized question answering on this policy?")
    with f_col2:
        if st.button("Open in Ask My Policy", key="_scenario_ask_fallback"):
            set_active_view(VIEW_ASK)
            st.rerun()
