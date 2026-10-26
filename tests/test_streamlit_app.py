from pathlib import Path

import pymupdf
from streamlit.testing.v1 import AppTest

from backend.qa.answer import AnswerResult, VerifiedCitation
from backend.qa.workflow import prepare_policy
from frontend.app import (
    DOC_KEY,
    LAST_Q_KEY,
    RESULT_KEY,
    _blockquote,
    _escape_md,
    confidence_label,
    format_bytes,
    verdict_label,
)

APP_PATH = Path(__file__).resolve().parents[1] / "frontend" / "app.py"

POLICY_TEXT = (
    "Expenses related to the treatment of a pre-existing disease are excluded "
    "until the expiry of 36 months of continuous coverage. Hospitalization "
    "expenses are covered subject to the policy terms."
)


def make_pdf_bytes() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), POLICY_TEXT)
    data = document.tobytes()
    document.close()
    return data


def make_policy():
    return prepare_policy(make_pdf_bytes(), "demo-policy.pdf")


def new_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=30)


def test_format_helpers():
    assert format_bytes(512) == "512 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(2 * 1024 * 1024) == "2.0 MB"
    assert verdict_label("not_stated") == "Not stated"
    assert confidence_label("high") == "High"
    assert _blockquote("first line\nsecond line") == "> first line\n> second line"
    assert _escape_md("*policy*") == "\\*policy\\*"


def test_landing_page_renders_upload_only():
    at = new_app()
    at.run()

    assert not list(at.exception)
    assert len(at.file_uploader) == 1
    assert not at.text_area
    assert any("CoverScope" in item.value for item in at.markdown)
    assert any("Your policy. Made clear." in item.value for item in at.markdown)


def test_processed_policy_renders_without_a_provider_call():
    at = new_app()
    at.session_state[DOC_KEY] = make_policy()
    at.run()

    assert not list(at.exception)
    assert at.text_area[0].label == "Your question"
    assert any(button.label == "Ask CoverScope" for button in at.button)
    assert any(metric.label == "Pages" for metric in at.metric)


def test_changing_the_question_does_not_issue_a_request(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    at = new_app()
    at.session_state[DOC_KEY] = make_policy()
    at.run()

    at.text_area[0].set_value("Is a pre-existing disease covered?").run()

    assert not list(at.exception)
    assert not at.error
    assert at.session_state[RESULT_KEY] is None


def test_manual_review_is_prominent_and_not_a_definitive_verdict():
    at = new_app()
    at.session_state[DOC_KEY] = make_policy()
    at.session_state[RESULT_KEY] = AnswerResult(
        verdict="depends",
        answer=(
            "CoverScope could not verify the model's citations against the "
            "policy text. Please review the cited pages manually."
        ),
        citations=(
            VerifiedCitation(
                chunk_id="P1-C1",
                page_number=1,
                quote=POLICY_TEXT[:80],
                verified=True,
            ),
        ),
        confidence="low",
        caveats=("The model's answer is unverified.",),
        citations_valid=False,
        manual_review_required=True,
        warnings=(
            "Quotation for P1-C1 does not match the source text.",
        ),
        unverified_answer="The model claimed the disease is covered.",
    )
    at.session_state[LAST_Q_KEY] = "Is a pre-existing disease covered in month 20?"
    at.run()

    assert not list(at.exception)
    assert any(
        "could not verify every quotation" in warning.value.lower()
        for warning in at.warning
    )
    assert any(
        item.label == "Unverified model answer — not a coverage decision"
        for item in at.expander
    )
    rendered = " ".join(item.value for item in at.markdown)
    assert "Manual review" in rendered
    assert "Depends" in rendered
    assert "does not match the source text" in rendered


def test_not_stated_explains_that_it_is_not_an_exclusion():
    at = new_app()
    at.session_state[DOC_KEY] = make_policy()
    at.session_state[RESULT_KEY] = AnswerResult(
        verdict="not_stated",
        answer="No relevant provision was found in the retrieved evidence.",
        citations=(),
        confidence="low",
        caveats=(),
        citations_valid=True,
        manual_review_required=False,
        warnings=(),
    )
    at.run()

    assert not list(at.exception)
    assert any(
        "does not mean the benefit is excluded" in item.value.lower()
        for item in at.info
    )


def test_upload_processes_the_pdf_and_reuses_it_on_rerun():
    at = new_app()
    at.run()

    at.file_uploader[0].upload(
        "demo-policy.pdf",
        make_pdf_bytes(),
        "application/pdf",
    ).run()

    assert not list(at.exception)
    assert at.text_area[0].label == "Your question"
    assert at.session_state[DOC_KEY] is not None
    first_policy = at.session_state[DOC_KEY]
    assert any("demo-policy.pdf" in item.value for item in at.markdown)

    at.text_area[0].set_value("Is a pre-existing disease covered?").run()

    assert not list(at.exception)
    assert at.session_state[DOC_KEY] is first_policy


def test_invalid_upload_shows_a_safe_error_and_no_question_area():
    at = new_app()
    at.run()

    at.file_uploader[0].upload(
        "not-a-policy.pdf",
        b"this is not a PDF",
        "application/pdf",
    ).run()

    assert not list(at.exception)
    assert any("valid pdf" in item.value.lower() for item in at.error)
    assert not at.text_area


def test_suggestion_click_makes_exactly_one_answer_request(monkeypatch):
    policy = make_policy()
    calls = {"count": 0}
    payload = {
        "verdict": "excluded",
        "answer": "A pre-existing disease is excluded for the first 36 months.",
        "citations": [
            {
                "chunk_id": policy.chunks[0].chunk_id,
                "quote": policy.chunks[0].text[:80],
            }
        ],
        "confidence": "high",
        "caveats": [],
    }

    class FakeGroqClient:
        def __init__(self, **kwargs):
            pass

        def complete_json(self, *, system_prompt, user_prompt, schema=None):
            calls["count"] += 1
            return payload

    import backend.llm.groq_client as groq_module

    monkeypatch.setattr(groq_module, "GroqClient", FakeGroqClient)

    at = new_app()
    at.session_state[DOC_KEY] = policy
    at.run()
    at.button[0].click().run()

    assert not list(at.exception)
    assert calls["count"] == 1
    assert not at.error
    assert at.session_state[RESULT_KEY].verdict == "excluded"
    rendered = " ".join(item.value for item in at.markdown)
    assert "Citations verified" in rendered
    assert "Page 1" in rendered
