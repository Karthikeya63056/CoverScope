"""CoverScope Streamlit app.

Run locally from the repository root:

    streamlit run frontend/app.py
"""
from __future__ import annotations

import math
from pathlib import Path
import sys
import time

import streamlit as st

# Streamlit adds the script directory to sys.path; add the repository root so
# the existing backend package is importable exactly as it is from the CLI.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.llm.groq_client import GroqClient
from backend.qa.answer import AnswerResult
from backend.qa.workflow import (
    PolicyProcessingError,
    ProcessedPolicy,
    ask_policy_question,
    fingerprint,
    prepare_policy,
)
from frontend.messages import (
    CONFIDENCE_LABELS,
    MANUAL_REVIEW_MESSAGE,
    MAX_QUESTION_CHARS,
    NOT_STATED_MESSAGE,
    SUGGESTED_QUESTIONS,
    VERDICT_LABELS,
    VERDICT_SUMMARIES,
    describe_llm_error,
)

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

PAGE_TITLE = "CoverScope"
TAGLINE = "Your policy. Made clear."

CSS = """
<style>
:root {
  --cs-ink: #0b1f2a;
  --cs-body: #243b4a;
  --cs-muted: #5b6b77;
  --cs-line: #dbe4e2;
  --cs-paper: #f6f4ef;
  --cs-card: #ffffff;
  --cs-brand: #0f5c55;
  --cs-brand-dark: #0b4742;
  --cs-green: #1f7a5a;
  --cs-green-soft: #e7f4ee;
  --cs-red: #b42318;
  --cs-red-soft: #fdecea;
  --cs-amber: #8a5200;
  --cs-amber-soft: #fdf3e2;
  --cs-slate: #475467;
  --cs-slate-soft: #eef1f4;
}
.stApp {
  background:
    radial-gradient(1100px 480px at 12% -10%, #e8f1ee 0%, rgba(232,241,238,0) 62%),
    var(--cs-paper);
  color: var(--cs-body);
}
[data-testid="stHeader"] { background: transparent; }
.block-container {
  max-width: 1120px;
  padding-top: 2rem;
  padding-bottom: 4rem;
}
html, body, p, li, label, button, input, textarea {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
h1, h2, h3, h4 { color: var(--cs-ink); letter-spacing: -0.02em; }
p, li { color: var(--cs-body); }
a { color: var(--cs-brand); }

.cs-hero { padding: 1.1rem 0 1.5rem; }
.cs-kicker {
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  color: var(--cs-brand);
  font-weight: 700;
  text-transform: uppercase;
}
.cs-title {
  font-size: clamp(2.6rem, 6vw, 4rem);
  line-height: 1.03;
  margin: 0.35rem 0 0;
  color: var(--cs-ink);
  font-weight: 800;
}
.cs-tagline {
  font-size: clamp(1.15rem, 2.4vw, 1.5rem);
  color: var(--cs-brand);
  font-weight: 600;
  margin-top: 0.35rem;
}
.cs-lede {
  max-width: 47rem;
  font-size: 1.02rem;
  line-height: 1.65;
  color: var(--cs-muted);
  margin-top: 0.8rem;
}
.cs-card {
  background: var(--cs-card);
  border: 1px solid var(--cs-line);
  border-radius: 16px;
  padding: 1.05rem 1.15rem;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
  height: 100%;
}
.cs-card h3 { font-size: 1rem; margin: 0.1rem 0 0.35rem; }
.cs-card p { font-size: 0.9rem; color: var(--cs-muted); margin: 0; line-height: 1.55; }
.cs-step {
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  color: var(--cs-brand);
  font-weight: 700;
}
.cs-badge {
  display: inline-block;
  padding: 0.3rem 0.75rem;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.cs-badge-covered {
  background: var(--cs-green-soft);
  color: var(--cs-green);
  border: 1px solid #bfe0d0;
}
.cs-badge-excluded {
  background: var(--cs-red-soft);
  color: var(--cs-red);
  border: 1px solid #f3c7c2;
}
.cs-badge-depends {
  background: var(--cs-amber-soft);
  color: var(--cs-amber);
  border: 1px solid #efd3a2;
}
.cs-badge-not-stated {
  background: var(--cs-slate-soft);
  color: var(--cs-slate);
  border: 1px solid #d3dae1;
}
.cs-chip {
  display: inline-block;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 700;
}
.cs-chip-ok { background: var(--cs-green-soft); color: var(--cs-green); }
.cs-chip-warn { background: var(--cs-amber-soft); color: var(--cs-amber); }
.cs-answer-head {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  flex-wrap: wrap;
  margin: 0.2rem 0 0.6rem;
}
.cs-cite-meta {
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--cs-brand);
  font-weight: 700;
}
div[data-testid="stMetric"] {
  background: var(--cs-card);
  border: 1px solid var(--cs-line);
  border-radius: 14px;
  padding: 0.7rem 0.9rem;
}
div[data-testid="stMetricLabel"] p { color: var(--cs-muted) !important; font-size: 0.8rem; }
div[data-testid="stMetricValue"] { color: var(--cs-ink); }
.stButton > button { border-radius: 10px; font-weight: 600; }
.stButton > button[kind="primary"] {
  background: var(--cs-brand);
  border-color: var(--cs-brand);
}
.stButton > button[kind="primary"]:hover {
  background: var(--cs-brand-dark);
  border-color: var(--cs-brand-dark);
}
[data-testid="stFileUploader"] section {
  border: 1.5px dashed #bfd0cc;
  border-radius: 14px;
  background: #fbfdfc;
}
div[data-testid="stExpander"] details { border-radius: 12px; }
.cs-footer { color: var(--cs-muted); font-size: 0.82rem; line-height: 1.6; }
@media (max-width: 640px) {
  .block-container { padding-top: 1.1rem; }
  .cs-title { font-size: 2.4rem; }
}
</style>
"""


def format_bytes(size: int) -> str:
    """Human-readable byte size for document metadata."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def verdict_label(verdict: str) -> str:
    """Display label for one of the four backend verdicts."""
    return VERDICT_LABELS.get(verdict, verdict.replace("_", " ").title())


def confidence_label(confidence: str) -> str:
    """Display label for the model-reported confidence level."""
    return CONFIDENCE_LABELS.get(confidence, confidence.title())


def _escape_md(text: str) -> str:
    for char in "\\`*_{}[]<>#|":
        text = text.replace(char, "\\" + char)
    return text


def _blockquote(text: str) -> str:
    lines = text.strip().splitlines() or [""]
    return "\n".join("> " + line if line.strip() else ">" for line in lines)


def _init_state() -> None:
    defaults = {
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


def _clear_document(*, clear_uploader: bool = False) -> None:
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


def _reset_app() -> None:
    """Start-over callback; runs before the next script execution."""
    _clear_document(clear_uploader=True)


def _use_suggestion(text: str) -> None:
    """Suggestion callback; asks only after an explicit click."""
    st.session_state[QUESTION_KEY] = text
    st.session_state[AUTO_ASK_KEY] = True


def _cooldown_remaining() -> int:
    until = st.session_state.get(COOLDOWN_KEY, 0.0)
    return max(0, int(math.ceil(until - time.time())))


def _ensure_processed(uploaded) -> None:
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

    try:
        with st.spinner("Reading the PDF, checking extraction quality, and preparing evidence…"):
            policy = prepare_policy(
                data,
                uploaded.name,
                max_upload_bytes=settings.max_upload_bytes,
                max_extracted_chars=settings.max_extracted_chars,
                min_page_chars=settings.min_page_chars,
                chunk_chars=settings.chunk_chars,
            )
    except PolicyProcessingError as exc:
        st.session_state[DOC_ERROR_KEY] = {
            "message": str(exc),
            "errors": exc.errors,
            "warnings": exc.warnings,
        }
        st.session_state[DOC_FP_KEY] = current_fingerprint
    except Exception:
        # Never render a raw traceback in the interface or log document text.
        st.session_state[DOC_ERROR_KEY] = {
            "message": "The PDF could not be processed. It may be damaged or unsupported.",
            "errors": (),
            "warnings": (),
        }
        st.session_state[DOC_FP_KEY] = current_fingerprint
    else:
        st.session_state[DOC_KEY] = policy
        st.session_state.pop(DOC_ERROR_KEY, None)
        st.session_state[DOC_FP_KEY] = current_fingerprint
        st.session_state[JUST_PROCESSED_KEY] = True


def _run_question(policy: ProcessedPolicy, question: str) -> None:
    """Make one provider request for one explicit user action."""
    try:
        client = GroqClient(
            model=settings.groq_model,
            timeout=settings.groq_timeout_seconds,
            max_completion_tokens=settings.groq_max_completion_tokens,
        )
        with st.spinner("Retrieving policy evidence and checking every citation…"):
            result = ask_policy_question(question, policy, client)
    except Exception as exc:
        friendly = describe_llm_error(exc)
        st.session_state[ERROR_KEY] = friendly.message
        if friendly.retry_after_seconds:
            st.session_state[COOLDOWN_KEY] = time.time() + friendly.retry_after_seconds
    else:
        st.session_state[RESULT_KEY] = result
        st.session_state[LAST_Q_KEY] = question
        st.session_state.pop(ERROR_KEY, None)
        st.session_state[COOLDOWN_KEY] = 0.0


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🛡️ CoverScope")
        st.caption(TAGLINE)
        st.divider()
        st.markdown("**How it works**")
        st.markdown(
            "1. Upload a text-based policy PDF\n"
            "2. Ask a coverage question\n"
            "3. Review the verdict, quotation, and page"
        )
        st.divider()
        st.caption(f"Model: `{settings.groq_model}`")
        st.caption(f"Evidence window: top {settings.retrieval_top_k} retrieved chunks")
        if st.session_state.get(DOC_KEY) is not None:
            st.button(
                "Start a new document",
                on_click=_reset_app,
                width="stretch",
                key="start_over",
            )
        st.divider()
        st.caption(
            "CoverScope is an informational tool, not insurance advice or a claim "
            "decision. Always verify against the policy schedule and your insurer."
        )


def _render_hero() -> None:
    st.markdown(
        """
        <div class="cs-hero">
          <div class="cs-kicker">Evidence-grounded policy Q&amp;A</div>
          <h1 class="cs-title">CoverScope</h1>
          <div class="cs-tagline">Your policy. Made clear.</div>
          <p class="cs-lede">
            Upload a health insurance policy and ask a question. CoverScope answers
            only from the policy wording, shows the exact quotation and page behind
            each verdict, and flags anything it cannot verify.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_promise(step: str, title: str, body: str) -> None:
    st.markdown(
        f'<div class="cs-card"><div class="cs-step">{step}</div>'
        f"<h3>{title}</h3><p>{body}</p></div>",
        unsafe_allow_html=True,
    )


def _render_landing() -> None:
    cols = st.columns(3)
    with cols[0]:
        _render_promise(
            "01 · CITED",
            "Cited, not guessed",
            "A coverage verdict must point to a verified quotation and page from your policy.",
        )
    with cols[1]:
        _render_promise(
            "02 · SAFE",
            "Safe by default",
            "If a citation cannot be verified, CoverScope returns a manual-review outcome, not a definitive verdict.",
        )
    with cols[2]:
        _render_promise(
            "03 · GROUNDED",
            "Real policy wording",
            "Waiting periods, exclusions, sublimits, and plan-dependent conditions are treated as conditions.",
        )
    st.write("")
    st.caption(
        "Public sample wordings are bundled in the repository under `pdfs/`. "
        "Do not upload a policy you are not permitted to share."
    )


def _render_uploader() -> None:
    doc = st.session_state.get(DOC_KEY)
    with st.expander(
        "Upload a policy PDF" if doc is None else "Upload a different policy",
        expanded=doc is None,
    ):
        uploaded = st.file_uploader(
            "Choose a text-based health insurance policy",
            type=["pdf"],
            key=f"policy_upload_{st.session_state[UPLOADER_VERSION_KEY]}",
            max_upload_size=max(1, settings.max_upload_bytes // 1_000_000),
            help=(
                "PDF only. Scanned or image-only PDFs are rejected because OCR is "
                "not supported. Oversized documents are rejected, never truncated."
            ),
        )
        st.caption(
            f"PDF only · up to {format_bytes(settings.max_upload_bytes)} and "
            f"{settings.max_extracted_chars:,} extracted characters."
        )
        st.info(
            "Privacy: your PDF is processed in memory and is not written to disk by "
            "CoverScope. The policy sections retrieved for your question are sent to "
            "the configured LLM provider (Groq) for analysis. Do not upload documents "
            "you are not permitted to share.",
            icon="🔒",
        )
    return uploaded


def _render_document_error() -> None:
    error = st.session_state.get(DOC_ERROR_KEY)
    if not error:
        return
    st.error(error["message"], title="This PDF could not be used")
    if error.get("errors"):
        st.markdown("**What to check**")
        for item in error["errors"]:
            st.markdown(f"- {item}")
    st.caption(
        "The document was rejected, not truncated. Try a text-based PDF within the "
        "size and extracted-text limits."
    )


def _render_document_summary(policy: ProcessedPolicy) -> None:
    with st.container(border=True):
        title_col, status_col = st.columns([5, 1])
        with title_col:
            st.markdown(f"### {_escape_md(policy.filename)}")
            st.caption("Policy loaded · extracted and chunked in memory")
        with status_col:
            st.markdown(
                '<span class="cs-chip cs-chip-ok">Ready</span>',
                unsafe_allow_html=True,
            )

        columns = st.columns(4)
        columns[0].metric("Pages", f"{policy.page_count:,}")
        columns[1].metric(
            "Extracted text",
            f"{policy.extracted_characters:,}",
            help="Characters of selectable text. Documents above the limit are rejected, never truncated.",
        )
        columns[2].metric("Searchable chunks", f"{len(policy.chunks):,}")
        columns[3].metric("File size", format_bytes(policy.size_bytes))

        if policy.quality.text_poor_pages:
            st.caption(
                "Low-text pages: "
                + ", ".join(map(str, policy.quality.text_poor_pages))
                + ". Review these pages if they are relevant to your question."
            )
        if policy.quality.table_review_pages:
            st.caption(
                "Possible table / multi-column pages for manual review: "
                + ", ".join(map(str, policy.quality.table_review_pages))
                + ". Text extraction does not guarantee table row/column order."
            )
        if policy.quality.warnings:
            with st.expander("Extraction notes"):
                for warning in policy.quality.warnings:
                    st.markdown(f"- {warning}")


def _render_question_area(policy: ProcessedPolicy) -> None:
    st.markdown("## Ask about this policy")
    st.caption("Suggested questions")
    suggestion_columns = st.columns(2)
    for index, suggestion in enumerate(SUGGESTED_QUESTIONS):
        suggestion_columns[index % 2].button(
            suggestion,
            key=f"suggestion_{index}",
            on_click=_use_suggestion,
            args=(suggestion,),
            width="stretch",
        )

    question = st.text_area(
        "Your question",
        key=QUESTION_KEY,
        height=96,
        max_chars=MAX_QUESTION_CHARS,
        placeholder="e.g. Is a pre-existing disease covered in month 20?",
    )

    cooldown = _cooldown_remaining()
    if cooldown > 0:
        st.info(
            f"The AI provider rate limit was reached. Try again in about "
            f"{cooldown} seconds; CoverScope will not retry automatically."
        )

    ask_clicked = st.button(
        "Ask CoverScope",
        type="primary",
        key="ask_button",
    )
    auto_ask = bool(st.session_state.pop(AUTO_ASK_KEY, False))

    if ask_clicked or auto_ask:
        if cooldown > 0:
            st.warning("Please wait for the rate-limit cooldown before asking again.")
        elif not question or not question.strip():
            st.warning("Enter a question first.")
        else:
            _run_question(policy, question.strip())


def _render_answer(result: AnswerResult, question: str | None = None) -> None:
    manual_review = result.manual_review_required or not result.citations_valid
    if manual_review:
        st.warning(MANUAL_REVIEW_MESSAGE, title="Manual review required", icon="⚠️")

    verdict = result.verdict
    badge = (
        f'<span class="cs-badge cs-badge-{verdict.replace("_", "-")}">'
        f"{verdict_label(verdict)}</span>"
    )
    chip = (
        '<span class="cs-chip cs-chip-warn">Manual review</span>'
        if manual_review
        else '<span class="cs-chip cs-chip-ok">Citations verified</span>'
    )
    st.markdown(
        f'<div class="cs-answer-head">{badge}{chip}</div>',
        unsafe_allow_html=True,
    )
    st.caption(VERDICT_SUMMARIES.get(verdict, ""))

    if question:
        st.caption(f"Question: {question}")
    st.markdown("#### Answer")
    st.markdown(result.answer)

    if verdict == "not_stated":
        st.info(NOT_STATED_MESSAGE)

    metric_columns = st.columns(3)
    metric_columns[0].metric(
        "Model-reported confidence",
        confidence_label(result.confidence),
        help="Reported by the model. This is not a guarantee that the verdict is correct.",
    )
    metric_columns[1].metric(
        "Citation check",
        "Verified" if result.citations_valid else "Failed",
        help="Every quotation is matched against the retrieved policy text.",
    )
    metric_columns[2].metric(
        "Cited pages",
        ", ".join(map(str, result.cited_pages)) or "None",
    )
    st.caption(
        "Confidence is reported by the model and is not a guarantee of correctness. "
        "A valid quotation confirms the wording, not the coverage decision."
    )

    if result.citations:
        st.markdown("#### Cited evidence")
        for citation in result.citations:
            with st.container(border=True):
                st.markdown(
                    f'<span class="cs-cite-meta">Page {citation.page_number} · '
                    f"{citation.chunk_id}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(_blockquote(citation.quote))
    else:
        st.caption("No verified quotations were returned for this answer.")

    caveats = [item for item in result.caveats if item not in result.warnings]
    if result.warnings:
        st.markdown("#### Verification warnings")
        for warning in result.warnings:
            st.markdown(f"- {warning}")
    if caveats:
        st.markdown("#### Policy caveats")
        for caveat in caveats:
            st.markdown(f"- {caveat}")

    if result.unverified_answer:
        with st.expander("Unverified model answer — not a coverage decision"):
            st.write(result.unverified_answer)


def _render_answer_zone() -> None:
    error = st.session_state.get(ERROR_KEY)
    result = st.session_state.get(RESULT_KEY)

    if error:
        st.error(error, title="Could not answer")
    if result:
        if error:
            st.markdown("#### Previous answer")
            st.caption(
                "This is the last verified result and may not answer your latest question."
            )
        _render_answer(result, st.session_state.get(LAST_Q_KEY))
    elif not error:
        st.caption("Ask a question to see a verdict with cited evidence.")


def main() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    _init_state()
    _render_sidebar()
    _render_hero()

    uploaded = _render_uploader()

    if uploaded is None:
        if st.session_state.get(DOC_FP_KEY):
            _clear_document()
    else:
        _ensure_processed(uploaded)

    if st.session_state.pop(JUST_PROCESSED_KEY, False):
        st.success("Policy processed. You can ask a question now.")

    policy = st.session_state.get(DOC_KEY)
    if policy is None:
        _render_document_error()
        if not st.session_state.get(DOC_ERROR_KEY):
            _render_landing()
    else:
        _render_document_summary(policy)
        st.write("")
        _render_question_area(policy)
        st.divider()
        _render_answer_zone()

    st.divider()
    st.markdown(
        '<div class="cs-footer">CoverScope is an informational tool, not insurance '
        "advice or a claim decision. Verdicts reflect the retrieved wording and may "
        "omit conditions elsewhere in the policy. Always verify against the policy "
        "schedule and your insurer.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
