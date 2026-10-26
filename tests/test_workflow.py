import pymupdf
import pytest

from backend.qa.workflow import (
    PolicyProcessingError,
    ask_policy_question,
    fingerprint,
    prepare_policy,
)


def make_pdf(text: str, *, pages: int = 1) -> bytes:
    document = pymupdf.open()
    for _ in range(pages):
        page = document.new_page()
        page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


POLICY_TEXT = (
    "Expenses related to the treatment of a pre-existing disease are excluded "
    "until the expiry of 36 months of continuous coverage. Hospitalization "
    "expenses are covered subject to the policy terms."
)


class FakeClient:
    def __init__(self, payload=None):
        self.payload = payload
        self.calls = 0

    def complete_json(self, *, system_prompt, user_prompt, schema=None):
        self.calls += 1
        return self.payload


def test_prepare_policy_uses_the_existing_pipeline():
    policy = prepare_policy(make_pdf(POLICY_TEXT), "policy.pdf")

    assert policy.filename == "policy.pdf"
    assert policy.page_count == 1
    assert policy.extracted_characters > 0
    assert policy.chunks
    assert policy.chunks[0].chunk_id == "P1-C1"
    assert "pre-existing disease" in policy.chunks[0].text
    assert policy.quality.is_usable
    assert policy.size_bytes > 0


def test_prepare_policy_preserves_page_numbers():
    policy = prepare_policy(make_pdf(POLICY_TEXT, pages=2), "policy.pdf")
    assert policy.page_count == 2
    assert {chunk.page_number for chunk in policy.chunks} == {1, 2}


def test_fingerprint_is_stable_and_changes_with_content_or_name():
    data = make_pdf(POLICY_TEXT)
    assert fingerprint(data, "a.pdf") == fingerprint(data, "a.pdf")
    assert fingerprint(data, "a.pdf") != fingerprint(data, "b.pdf")
    assert fingerprint(data, "a.pdf") != fingerprint(data + b" ", "a.pdf")


def test_invalid_pdf_is_rejected_with_a_safe_message():
    with pytest.raises(PolicyProcessingError) as exc:
        prepare_policy(b"not a pdf", "policy.pdf")

    assert "valid PDF" in str(exc.value)


def test_blank_pdf_is_rejected_before_answering():
    document = pymupdf.open()
    document.new_page()
    data = document.tobytes()
    document.close()

    with pytest.raises(PolicyProcessingError) as exc:
        prepare_policy(data, "blank.pdf")

    assert exc.value.errors
    assert any("selectable text" in error for error in exc.value.errors)


def test_oversized_extracted_text_is_rejected_not_truncated():
    with pytest.raises(PolicyProcessingError) as exc:
        prepare_policy(
            make_pdf(POLICY_TEXT),
            "policy.pdf",
            max_extracted_chars=20,
        )

    assert any("exceeding" in error for error in exc.value.errors)
    assert any("20" in error for error in exc.value.errors)


def test_upload_size_limit_is_enforced_before_opening():
    with pytest.raises(PolicyProcessingError) as exc:
        prepare_policy(make_pdf(POLICY_TEXT), "policy.pdf", max_upload_bytes=10)

    assert "upload limit" in str(exc.value)
    assert "not truncated" in str(exc.value)


def test_ask_policy_question_returns_verified_citations():
    policy = prepare_policy(make_pdf(POLICY_TEXT), "policy.pdf")
    chunk = policy.chunks[0]
    client = FakeClient(
        {
            "verdict": "excluded",
            "answer": "A pre-existing disease is excluded for 36 months.",
            "citations": [{"chunk_id": chunk.chunk_id, "quote": chunk.text[:80]}],
            "confidence": "high",
            "caveats": [],
        }
    )

    result = ask_policy_question(
        "Is a pre-existing disease covered in month 20?",
        policy,
        client,
    )

    assert client.calls == 1
    assert result.verdict == "excluded"
    assert result.citations_valid
    assert result.citations[0].page_number == 1


def test_ask_policy_question_rejects_an_empty_question():
    policy = prepare_policy(make_pdf(POLICY_TEXT), "policy.pdf")
    with pytest.raises(ValueError):
        ask_policy_question("   ", policy, FakeClient())


def test_irrelevant_question_returns_not_stated_without_calling_provider():
    policy = prepare_policy(make_pdf(POLICY_TEXT), "policy.pdf")
    client = FakeClient(payload={"verdict": "covered"})

    result = ask_policy_question("Is car theft covered?", policy, client)

    assert client.calls == 0
    assert result.verdict == "not_stated"
    assert result.citations_valid
