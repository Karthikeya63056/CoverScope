"""Document Library workspace view for CoverScope."""
from __future__ import annotations

import streamlit as st

from backend.domain.enums import DocumentAssociationStatus, ScheduleFieldStatus
from backend.domain.schedule import PolicySchedule
from backend.qa.workflow import ProcessedPolicy
from frontend.components.icons import (
    icon_alert_triangle,
    icon_bookmark,
    icon_check_circle,
    icon_file_text,
    icon_lock,
    icon_upload,
)
from frontend.state import (
    VIEW_ASK,
    VIEW_EXPLORER,
    VIEW_COMPARISON,
    ensure_processed,
    get_active_fingerprint,
    get_policy_schedule,
    get_registry,
    policy_service,
    remove_policy,
    set_active_policy,
    set_active_view,
    set_policy_schedule,
)
from frontend.utils.formatters import clean_html, escape_md, format_bytes


def render_library_view() -> None:
    """Render the Document Library session management workspace."""
    st.markdown("## Document Library")
    st.caption("Manage your loaded health insurance policies for this session.")

    # In-memory privacy disclosure
    privacy_html = """
    <div class="cs-card" style="margin-bottom: 1.25rem; border-left: 3px solid #0f766e; background:#f0fdfa;">
      <div style="font-size:0.875rem; color:#0a2233; font-weight:600; margin-bottom:0.25rem;">
        In-Memory Session Storage
      </div>
      <div style="font-size:0.82rem; color:#334155; line-height:1.5;">
        All loaded policies and their question histories reside strictly in your current browser session's RAM.
        CoverScope does not write policy text to any database, file storage, or local disk. Closing the browser
        or restarting the application completely purges this session library.
      </div>
    </div>
    """
    st.markdown(clean_html(privacy_html), unsafe_allow_html=True)

    # Uploader to add another document to session
    with st.expander("Upload another policy document to this session", expanded=False):
        uploaded_file = st.file_uploader(
            "Add a PDF document to library",
            type=["pdf"],
            key="lib_add_uploader",
            help="Upload an additional Indian health insurance policy PDF into your session.",
        )
        if uploaded_file is not None:
            ensure_processed(uploaded_file)
            st.rerun()

    reg = get_registry()
    active_fp = get_active_fingerprint()

    if not reg:
        _render_empty_library()
        return

    if len(reg) >= 2:
        c_strip1, c_strip2 = st.columns([4, 2])
        with c_strip1:
            st.markdown("<p style='margin:0.3rem 0; font-size:0.9rem; color:#0f766e;'>💡 Multiple policies loaded. You can run side-by-side comparison and protection gap analysis.</p>", unsafe_allow_html=True)
        with c_strip2:
            if st.button("Compare Policies Side-by-Side", type="primary", use_container_width=True, key="lib_compare_btn"):
                set_active_view(VIEW_COMPARISON)
                st.rerun()

    st.markdown(f"### Loaded Policies ({len(reg)})")

    for fp, record in list(reg.items()):
        policy: ProcessedPolicy = record["policy"]
        is_active = (fp == active_fp)
        escaped_name = escape_md(policy.filename)
        history = record.get("history", [])
        q_count = len(history)

        with st.container(border=True):
            head_col, status_col = st.columns([4, 2])
            with head_col:
                st.markdown(f"#### {escaped_name}")
                st.caption(
                    f"{policy.page_count:,} pages &bull; "
                    f"{policy.extracted_characters:,} characters &bull; "
                    f"{len(policy.chunks):,} searchable chunks &bull; "
                    f"File size: {format_bytes(policy.size_bytes)}"
                )
            with status_col:
                if is_active:
                    st.markdown(
                        '<span class="cs-chip cs-chip-ok">'
                        '<span style="display:inline-flex; align-items:center;">●</span>'
                        '<span>Active Document</span></span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<span class="cs-chip" style="background:#f1f5f9; color:#475569;">'
                        '<span>Loaded in Session</span></span>',
                        unsafe_allow_html=True,
                    )

            # Metadata and History Count
            st.caption(f"Questions asked about this policy in this session: **{q_count}**")

            # Quality notes
            quality = getattr(policy, "quality", None)
            warnings = tuple(getattr(quality, "warnings", ()) or ())
            if warnings:
                with st.expander("Extraction notes"):
                    for w in warnings:
                        st.markdown(f"- {w}")

            # Policy Schedule Attachment Section
            schedule = record.get("schedule")
            if schedule is None:
                with st.expander("📄 Attach Policy Schedule / Certificate", expanded=False):
                    st.caption("Upload your issued Policy Schedule or Certificate of Insurance to personalize waiting periods, deductibles, and family members:")
                    sch_file = st.file_uploader(
                        f"Upload Schedule for {escaped_name}",
                        type=["pdf"],
                        key=f"_lib_sch_upload_{fp}",
                        label_visibility="collapsed",
                    )
                    if sch_file is not None:
                        parsed_sch = policy_service.prepare_schedule(sch_file.getvalue(), sch_file.name)
                        assoc_sch = policy_service.associate_schedule(parsed_sch, policy)
                        if assoc_sch.association_status == DocumentAssociationStatus.CONFLICT_DETECTED:
                            st.warning(f"⚠️ Document Conflict Detected: {assoc_sch.conflicts[0]}")
                            if st.button("Confirm Association Anyway", key=f"_force_assoc_{fp}"):
                                confirmed_sch = policy_service.associate_schedule(parsed_sch, policy, user_confirmed=True)
                                set_policy_schedule(fp, confirmed_sch)
                                st.rerun()
                        else:
                            set_policy_schedule(fp, assoc_sch)
                            st.rerun()
            else:
                assoc_label = "Confirmed Association" if schedule.association_status == DocumentAssociationStatus.USER_CONFIRMED else "Suggested Match"
                st.markdown(
                    f"""
                    <div style="background:#f0fdfa; border:1px solid #ccfbf1; border-radius:6px; padding:0.6rem 0.85rem; margin:0.6rem 0;">
                      <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:0.85rem; font-weight:700; color:#0f766e;">✓ Policy Schedule Attached: {escape_md(schedule.filename)}</span>
                        <span class="cs-chip cs-chip-ok" style="font-size:0.7rem; padding:0.15rem 0.45rem;">{assoc_label}</span>
                      </div>
                      <div style="font-size:0.8rem; color:#334155; margin-top:0.25rem;">
                        <strong>Policy Period:</strong> {schedule.inception_date or 'N/A'} to {schedule.expiry_date or 'N/A'} &bull;
                        <strong>Sum Insured:</strong> {f'₹{schedule.sum_insured:,.0f}' if schedule.sum_insured else 'Not stated'} &bull;
                        <strong>Members:</strong> {len(schedule.members)} named &bull;
                        <strong>Active Riders:</strong> {len(schedule.optional_riders)}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander(f"Inspect Schedule Details & Members ({schedule.filename})", expanded=False):
                    if schedule.policy_number_masked:
                        st.markdown(f"- **Policy Number:** `{schedule.policy_number_masked}`")
                    if schedule.insurer_name:
                        st.markdown(f"- **Issuing Insurer:** {escape_md(schedule.insurer_name)}")
                    if schedule.product_name:
                        st.markdown(f"- **Product Name:** {escape_md(schedule.product_name)}")
                    if schedule.members:
                        st.markdown("**Insured Members:**")
                        for m in schedule.members:
                            st.markdown(f"  - **{escape_md(m.name)}** &bull; Age: {m.age if m.age is not None else 'N/A'} &bull; Relation: {escape_md(m.relation or 'Self')}")
                    if schedule.optional_riders:
                        st.markdown("**Active Optional Riders:**")
                        for r in schedule.optional_riders:
                            st.markdown(f"  - ✓ {escape_md(r)}")

                    if st.button("Detach / Remove Schedule", key=f"_detach_sch_{fp}"):
                        set_policy_schedule(fp, None)
                        st.rerun()

            # Actions Row
            act_cols = st.columns([2, 2, 2, 2])
            with act_cols[0]:
                if not is_active:
                    if st.button("Set as Active", key=f"set_active_{fp}", use_container_width=True):
                        set_active_policy(fp)
                        st.rerun()
                else:
                    st.button("Active", key=f"active_btn_{fp}", disabled=True, use_container_width=True)

            with act_cols[1]:
                if st.button("Ask Questions", key=f"ask_nav_{fp}", use_container_width=True):
                    set_active_policy(fp)
                    set_active_view(VIEW_ASK)
                    st.rerun()

            with act_cols[2]:
                if st.button("Explore Clauses", key=f"exp_nav_{fp}", use_container_width=True):
                    set_active_policy(fp)
                    set_active_view(VIEW_EXPLORER)
                    st.rerun()

            with act_cols[3]:
                if st.button("Remove", key=f"rem_{fp}", use_container_width=True):
                    remove_policy(fp)
                    st.rerun()


def _render_empty_library() -> None:
    """Render empty state when no documents have been loaded into the library."""
    empty_html = """
    <div class="cs-card" style="text-align:center; padding: 3rem 1.5rem; border-style:dashed;">
      <h3 style="color:#0a2233; margin:0 0 0.5rem 0;">No documents in your session library</h3>
      <p style="color:#64748b; font-size:0.9rem; max-width:480px; margin:0 auto 1.5rem auto; line-height:1.5;">
        Upload a health insurance policy PDF to start analyzing coverage, browsing clauses, and building your session portfolio.
      </p>
    </div>
    """
    st.markdown(clean_html(empty_html), unsafe_allow_html=True)

    if st.button("Upload Your First Policy in Ask My Policy", key="lib_first_upload"):
        set_active_view(VIEW_ASK)
        st.rerun()
