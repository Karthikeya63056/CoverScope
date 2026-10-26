"""Centralized session-state management for the CoverScope Streamlit frontend."""
from __future__ import annotations

import math
import time
from typing import Any

import streamlit as st

from backend.config import settings
import backend.llm.groq_client as groq_client_module
from backend.qa.workflow import (
    PolicyProcessingError,
    ProcessedPolicy,
    ask_policy_question,
    fingerprint,
    prepare_policy,
)
from frontend.components.brand_intro import render_real_time_status
from frontend.messages import describe_llm_error

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
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def clear_document(*, clear_uploader: bool = False) -> None:
    """Clear the active document and all dependent questions and results."""
    version = st.session_state.get(UPLOADER_VERSION_KEY, 0)
    if clear_uploader:
        st.session_state.pop(f"policy_upload_{version}", None)
    for key in (
        DOC_KEY,
        DOC_FP_KEY,
        DOC_ERROR_KEY,
        RESULT_KEY,
        LAST_Q_KEY,
        ERROR_KEY,
        COOLDOWN_KEY,
        QUESTION_KEY,
        AUTO_ASK_KEY,
        JUST_PROCESSED_KEY,
    ):
        st.session_state.pop(key, None)
    if clear_uploader:
        st.session_state[UPLOADER_VERSION_KEY] = version + 1


def reset_app() -> None:
    """Start-over callback; clears the document and increments uploader version."""
    clear_document(clear_uploader=True)


def use_suggestion(text: str) -> None:
    """Suggestion callback; triggers automatic ask on explicit click."""
    st.session_state[QUESTION_KEY] = text
    st.session_state[AUTO_ASK_KEY] = True


def cooldown_remaining() -> int:
    """Seconds remaining on the provider rate-limit cooldown."""
    until = st.session_state.get(COOLDOWN_KEY, 0.0)
    return max(0, int(math.ceil(until - time.time())))


def ensure_processed(uploaded: Any) -> None:
    """Process a newly selected PDF once and reuse it across reruns."""
    data = uploaded.getvalue()
    current_fingerprint = fingerprint(data, uploaded.name)
    if st.session_state.get(DOC_FP_KEY) == current_fingerprint:
        return

    st.session_state[DOC_KEY] = None
    st.session_state[RESULT_KEY] = None
    st.session_state[LAST_Q_KEY] = None
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
        policy = prepare_policy(
            data,
            uploaded.name,
            max_upload_bytes=settings.max_upload_bytes,
            max_extracted_chars=settings.max_extracted_chars,
            min_page_chars=settings.min_page_chars,
            chunk_chars=settings.chunk_chars,
        )
    except PolicyProcessingError as exc:
        status_slot.empty()
        st.session_state[DOC_ERROR_KEY] = {
            "message": str(exc),
            "errors": exc.errors,
            "warnings": exc.warnings,
        }
        st.session_state[DOC_FP_KEY] = current_fingerprint
    except Exception:
        status_slot.empty()
        # Never render a raw traceback in the interface or log document text.
        st.session_state[DOC_ERROR_KEY] = {
            "message": "The PDF could not be processed. It may be damaged or unsupported.",
            "errors": (),
            "warnings": (),
        }
        st.session_state[DOC_FP_KEY] = current_fingerprint
    else:
        status_slot.empty()
        st.session_state[DOC_KEY] = policy
        st.session_state.pop(DOC_ERROR_KEY, None)
        st.session_state[DOC_FP_KEY] = current_fingerprint
        st.session_state[JUST_PROCESSED_KEY] = True


def run_question(policy: ProcessedPolicy, question: str) -> None:
    """Make one provider request for one explicit user action."""
    status_slot = st.empty()
    try:
        with status_slot.container():
            render_real_time_status(
                "Analyzing relevant clauses",
                "Retrieving evidence and verifying citations in Python…",
            )
        client = groq_client_module.GroqClient(
            model=settings.groq_model,
            timeout=settings.groq_timeout_seconds,
            max_completion_tokens=settings.groq_max_completion_tokens,
        )
        result = ask_policy_question(question, policy, client)
    except Exception as exc:
        status_slot.empty()
        friendly = describe_llm_error(exc)
        st.session_state[ERROR_KEY] = friendly.message
        if friendly.retry_after_seconds:
            st.session_state[COOLDOWN_KEY] = time.time() + friendly.retry_after_seconds
    else:
        status_slot.empty()
        st.session_state[RESULT_KEY] = result
        st.session_state[LAST_Q_KEY] = question
        st.session_state.pop(ERROR_KEY, None)
        st.session_state[COOLDOWN_KEY] = 0.0
