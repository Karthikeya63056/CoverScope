"""Centralized session-state management and multi-policy registry for CoverScope."""
from __future__ import annotations

import math
import time
from typing import Any

import streamlit as st

from backend.config import settings
from backend.domain.schedule import PolicySchedule
from backend.qa.workflow import PolicyProcessingError, ProcessedPolicy, fingerprint
from backend.services.policy_service import PolicyService
from frontend.components.brand_intro import render_real_time_status
from frontend.messages import describe_llm_error

# Singleton headless policy service
policy_service = PolicyService(settings=settings)

# Session state keys
DOC_KEY = "cs_document"
DOC_FP_KEY = "cs_document_fingerprint"
DOC_ERROR_KEY = "cs_document_error"
RESULT_KEY = "cs_result"
LAST_Q_KEY = "cs_last_question"
ERROR_KEY = "cs_answer_error"
COOLDOWN_KEY = "cs_rate_limit_until"
AUTO_ASK_KEY = "cs_auto_ask"
QUESTION_KEY = "cs_question"
UPLOADER_VERSION_KEY = "cs_uploader_version"
JUST_PROCESSED_KEY = "cs_just_processed"

# Multi-policy registry & navigation keys
REGISTRY_KEY = "cs_policy_registry"
ACTIVE_FP_KEY = "cs_active_fingerprint"
ACTIVE_VIEW_KEY = "cs_active_view"
NAV_CHOICE_KEY = "cs_nav_choice"

VIEW_ASK = "ask"
VIEW_EXPLORER = "explorer"
VIEW_SCENARIO = "scenario"
VIEW_COMPARISON = "comparison"
VIEW_LIBRARY = "library"

SCENARIO_INPUT_KEY = "cs_scenario_input"
SCENARIO_RESULT_KEY = "cs_scenario_result"

COMPARISON_POLICY_A_KEY = "cs_comparison_policy_a"
COMPARISON_POLICY_B_KEY = "cs_comparison_policy_b"
COMPARISON_RESULT_KEY = "cs_comparison_result"
COMPARISON_ASSUMPTIONS_KEY = "cs_comparison_assumptions"


def init_state() -> None:
    """Initialize default session-state entries if not present."""
    defaults: dict[str, Any] = {
        DOC_KEY: None,
        DOC_FP_KEY: None,
        DOC_ERROR_KEY: None,
        RESULT_KEY: None,
        LAST_Q_KEY: None,
        ERROR_KEY: None,
        COOLDOWN_KEY: 0.0,
        UPLOADER_VERSION_KEY: 0,
        REGISTRY_KEY: {},
        ACTIVE_FP_KEY: None,
        ACTIVE_VIEW_KEY: VIEW_ASK,
        SCENARIO_INPUT_KEY: None,
        SCENARIO_RESULT_KEY: None,
        COMPARISON_POLICY_A_KEY: None,
        COMPARISON_POLICY_B_KEY: None,
        COMPARISON_RESULT_KEY: None,
        COMPARISON_ASSUMPTIONS_KEY: None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    sync_external_state()


def sync_external_state() -> None:
    """Synchronize direct st.session_state mutations (e.g. from unit tests) into the registry."""
    doc: ProcessedPolicy | None = st.session_state.get(DOC_KEY)
    if doc is not None and isinstance(doc, ProcessedPolicy):
        fp = getattr(doc, "fingerprint", None) or f"doc_{id(doc)}"
        reg: dict[str, dict[str, Any]] = st.session_state.setdefault(REGISTRY_KEY, {})
        if fp not in reg:
            reg[fp] = {
                "policy": doc,
                "history": [],
                "last_result": st.session_state.get(RESULT_KEY),
                "last_question": st.session_state.get(LAST_Q_KEY),
                "error": st.session_state.get(ERROR_KEY),
                "scenario_input": st.session_state.get(SCENARIO_INPUT_KEY),
                "scenario_result": st.session_state.get(SCENARIO_RESULT_KEY),
                "schedule": None,
            }
        if st.session_state.get(ACTIVE_FP_KEY) != fp:
            st.session_state[ACTIVE_FP_KEY] = fp


def get_registry() -> dict[str, dict[str, Any]]:
    """Return the session's policy registry dictionary."""
    sync_external_state()
    return st.session_state.setdefault(REGISTRY_KEY, {})


def get_policy_schedule(fp: str | None = None) -> PolicySchedule | None:
    """Return the associated PolicySchedule for the active or specified policy."""
    reg = get_registry()
    target_fp = fp or get_active_fingerprint()
    if target_fp and target_fp in reg:
        return reg[target_fp].get("schedule")
    return None


def set_policy_schedule(fp: str, schedule: PolicySchedule | None) -> None:
    """Attach or detach a PolicySchedule for the specified policy fingerprint."""
    reg = get_registry()
    if fp in reg:
        reg[fp]["schedule"] = schedule


def get_active_fingerprint() -> str | None:
    """Return the fingerprint of the currently active document."""
    sync_external_state()
    return st.session_state.get(ACTIVE_FP_KEY)


def get_active_policy() -> ProcessedPolicy | None:
    """Return the active ProcessedPolicy object."""
    sync_external_state()
    return st.session_state.get(DOC_KEY)


def get_active_view() -> str:
    """Return the active workspace view ('ask', 'explorer', 'library')."""
    return st.session_state.get(ACTIVE_VIEW_KEY, VIEW_ASK)


def set_active_view(view: str) -> None:
    """Set the active workspace view."""
    st.session_state[ACTIVE_VIEW_KEY] = view
    view_labels = {
        VIEW_ASK: "Ask My Policy",
        VIEW_EXPLORER: "Policy Explorer",
        VIEW_SCENARIO: "Scenario Analyzer",
        VIEW_COMPARISON: "Policy Comparison",
        VIEW_LIBRARY: "Document Library",
    }
    if view in view_labels:
        target_label = view_labels[view]
        try:
            st.session_state[NAV_CHOICE_KEY] = target_label
        except Exception:
            # Widget key already instantiated on current run; defer sync to next run
            st.session_state["_pending_nav_choice"] = target_label


def set_active_policy(fp: str) -> bool:
    """Switch the active document to the one matching fp without destroying other documents."""
    reg = get_registry()
    if fp not in reg:
        return False

    curr_fp = st.session_state.get(ACTIVE_FP_KEY)
    if curr_fp and curr_fp in reg:
        reg[curr_fp]["last_result"] = st.session_state.get(RESULT_KEY)
        reg[curr_fp]["last_question"] = st.session_state.get(LAST_Q_KEY)
        reg[curr_fp]["error"] = st.session_state.get(ERROR_KEY)
        reg[curr_fp]["scenario_input"] = st.session_state.get(SCENARIO_INPUT_KEY)
        reg[curr_fp]["scenario_result"] = st.session_state.get(SCENARIO_RESULT_KEY)

    record = reg[fp]
    st.session_state[ACTIVE_FP_KEY] = fp
    st.session_state[DOC_KEY] = record["policy"]
    st.session_state[DOC_FP_KEY] = fp
    st.session_state[RESULT_KEY] = record.get("last_result")
    st.session_state[LAST_Q_KEY] = record.get("last_question")
    st.session_state[ERROR_KEY] = record.get("error")
    st.session_state[SCENARIO_INPUT_KEY] = record.get("scenario_input")
    st.session_state[SCENARIO_RESULT_KEY] = record.get("scenario_result")
    st.session_state.pop(QUESTION_KEY, None)
    st.session_state.pop(AUTO_ASK_KEY, None)
    return True


def register_policy(policy: ProcessedPolicy, *, set_active: bool = True) -> str:
    """Register a processed policy into the session registry."""
    reg = get_registry()
    fp = policy.fingerprint
    if fp not in reg:
        reg[fp] = {
            "policy": policy,
            "history": [],
            "last_result": None,
            "last_question": None,
            "error": None,
            "scenario_input": None,
            "scenario_result": None,
            "schedule": None,
        }
    if set_active:
        set_active_policy(fp)
    return fp


def remove_policy(fp: str) -> bool:
    """Remove a document from the session registry."""
    reg = get_registry()
    if fp not in reg:
        return False

    del reg[fp]
    if st.session_state.get(ACTIVE_FP_KEY) == fp:
        if reg:
            next_fp = next(iter(reg.keys()))
            set_active_policy(next_fp)
        else:
            clear_document(clear_uploader=False, remove_from_registry=False)
    return True


def clear_document(*, clear_uploader: bool = False, remove_from_registry: bool = True) -> None:
    """Clear the active document and its dependent session state."""
    version = st.session_state.get(UPLOADER_VERSION_KEY, 0)
    if clear_uploader:
        st.session_state.pop(f"policy_upload_{version}", None)

    active_fp = st.session_state.get(ACTIVE_FP_KEY)
    if remove_from_registry and active_fp:
        reg = st.session_state.get(REGISTRY_KEY, {})
        reg.pop(active_fp, None)

    for key in (
        DOC_KEY,
        DOC_FP_KEY,
        ACTIVE_FP_KEY,
        DOC_ERROR_KEY,
        RESULT_KEY,
        LAST_Q_KEY,
        ERROR_KEY,
        COOLDOWN_KEY,
        QUESTION_KEY,
        AUTO_ASK_KEY,
        JUST_PROCESSED_KEY,
        SCENARIO_INPUT_KEY,
        SCENARIO_RESULT_KEY,
        COMPARISON_RESULT_KEY,
    ):
        st.session_state.pop(key, None)

    if clear_uploader:
        st.session_state[UPLOADER_VERSION_KEY] = version + 1


def reset_app() -> None:
    """Start-over callback; clears the document registry and increments uploader version."""
    st.session_state[REGISTRY_KEY] = {}
    clear_document(clear_uploader=True, remove_from_registry=False)


def use_suggestion(text: str) -> None:
    """Suggestion callback; triggers automatic ask on explicit click."""
    st.session_state[QUESTION_KEY] = text
    st.session_state[AUTO_ASK_KEY] = True


def cooldown_remaining() -> int:
    """Seconds remaining on the provider rate-limit cooldown."""
    until = st.session_state.get(COOLDOWN_KEY, 0.0)
    return max(0, int(math.ceil(until - time.time())))


def ensure_processed(uploaded: Any) -> None:
    """Process a newly selected PDF once and reuse it across reruns and documents."""
    data = uploaded.getvalue()
    current_fingerprint = fingerprint(data, uploaded.name)

    reg = get_registry()
    if current_fingerprint in reg:
        if st.session_state.get(ACTIVE_FP_KEY) != current_fingerprint:
            set_active_policy(current_fingerprint)
        return

    # Preserve currently active policy's ephemeral state into its registry record before switching
    curr_fp = st.session_state.get(ACTIVE_FP_KEY)
    if curr_fp and curr_fp in reg:
        reg[curr_fp]["last_result"] = st.session_state.get(RESULT_KEY)
        reg[curr_fp]["last_question"] = st.session_state.get(LAST_Q_KEY)
        reg[curr_fp]["error"] = st.session_state.get(ERROR_KEY)
        reg[curr_fp]["scenario_input"] = st.session_state.get(SCENARIO_INPUT_KEY)
        reg[curr_fp]["scenario_result"] = st.session_state.get(SCENARIO_RESULT_KEY)

    st.session_state[ACTIVE_FP_KEY] = None
    st.session_state[DOC_KEY] = None
    st.session_state[RESULT_KEY] = None
    st.session_state[LAST_Q_KEY] = None
    st.session_state[SCENARIO_INPUT_KEY] = None
    st.session_state[SCENARIO_RESULT_KEY] = None
    st.session_state.pop(ERROR_KEY, None)
    st.session_state.pop(QUESTION_KEY, None)
    st.session_state.pop(AUTO_ASK_KEY, None)

    status_slot = st.empty()
    try:
        with status_slot.container():
            render_real_time_status(
                "Reading your policy document",
                "Extracting selectable clauses in memory and checking readability…",
            )
        policy = policy_service.prepare_policy(
            data,
            uploaded.name,
            max_upload_bytes=settings.max_upload_bytes,
            max_extracted_chars=settings.max_extracted_chars,
            min_page_chars=settings.min_page_chars,
            chunk_chars=settings.chunk_chars,
        )
    except PolicyProcessingError as exc:
        status_slot.empty()
        st.session_state.pop(ACTIVE_FP_KEY, None)
        st.session_state[DOC_ERROR_KEY] = {
            "message": str(exc),
            "errors": exc.errors,
            "warnings": exc.warnings,
        }
        st.session_state[DOC_FP_KEY] = current_fingerprint
    except Exception:
        status_slot.empty()
        st.session_state.pop(ACTIVE_FP_KEY, None)
        st.session_state[DOC_ERROR_KEY] = {
            "message": "The PDF could not be processed. It may be damaged or unsupported.",
            "errors": (),
            "warnings": (),
        }
        st.session_state[DOC_FP_KEY] = current_fingerprint
    else:
        status_slot.empty()
        register_policy(policy, set_active=True)
        st.session_state.pop(DOC_ERROR_KEY, None)
        st.session_state[JUST_PROCESSED_KEY] = True


def run_question(policy: ProcessedPolicy, question: str) -> None:
    """Make one provider request for one explicit user action via the policy service."""
    status_slot = st.empty()
    try:
        with status_slot.container():
            render_real_time_status(
                "Analyzing relevant clauses",
                "Retrieving evidence and verifying citations in Python…",
            )
        result = policy_service.ask_question(policy, question)
    except Exception as exc:
        status_slot.empty()
        friendly = describe_llm_error(exc)
        st.session_state[ERROR_KEY] = friendly.message
        if friendly.retry_after_seconds:
            st.session_state[COOLDOWN_KEY] = time.time() + friendly.retry_after_seconds

        reg = get_registry()
        fp = policy.fingerprint
        if fp in reg:
            reg[fp]["error"] = friendly.message
    else:
        status_slot.empty()
        st.session_state[RESULT_KEY] = result
        st.session_state[LAST_Q_KEY] = question
        st.session_state.pop(ERROR_KEY, None)
        st.session_state[COOLDOWN_KEY] = 0.0

        reg = get_registry()
        fp = policy.fingerprint
        if fp in reg:
            reg[fp]["last_result"] = result
            reg[fp]["last_question"] = question
            reg[fp]["error"] = None
            reg[fp]["history"].append({
                "question": question,
                "result": result,
                "timestamp": time.time(),
            })
