from pathlib import Path

import pymupdf
import pytest

from scripts.ask_policy import main


def make_pdf(path: Path, text: str | None) -> Path:
    document = pymupdf.open()
    page = document.new_page()
    if text:
        page.insert_text((72, 72), text)
    path.write_bytes(document.tobytes())
    document.close()
    return path


def test_missing_arguments_exit_with_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_missing_question_exits_with_usage_error():
    with pytest.raises(SystemExit) as exc:
        main(["policy.pdf"])
    assert exc.value.code == 2


def test_blank_question_exits_with_usage_error():
    with pytest.raises(SystemExit) as exc:
        main(["policy.pdf", "   "])
    assert exc.value.code == 2


def test_missing_file_returns_nonzero(tmp_path, capsys):
    result = main([str(tmp_path / "missing.pdf"), "Is it covered?"])
    assert result == 2
    assert "PDF not found" in capsys.readouterr().out


def test_unusable_pdf_is_rejected_before_any_model_call(tmp_path, capsys):
    pdf = make_pdf(tmp_path / "blank.pdf", None)
    result = main([str(pdf), "Is it covered?"])
    assert result == 1
    output = capsys.readouterr().out
    assert "rejected" in output.lower()


def test_missing_api_key_returns_configuration_error(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    pdf = make_pdf(
        tmp_path / "policy.pdf",
        "Hospitalization expenses are covered subject to the policy terms.",
    )

    result = main([str(pdf), "Is hospitalization covered?"])

    assert result == 2
    assert "GROQ_API_KEY" in capsys.readouterr().out
