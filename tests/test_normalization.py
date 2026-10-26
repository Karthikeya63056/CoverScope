import pytest

from backend.document_processing.normalization import (
    normalize_for_match,
    normalize_text,
    search_text,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("de\ufb01nition", "definition"),
        ("o\ufb00er", "offer"),
        ("e\ufb03cient", "efficient"),
        ("\ufb02oor", "floor"),
    ],
)
def test_nfkc_expands_common_ligatures(raw, expected):
    assert normalize_text(raw) == expected


def test_line_break_hyphenation_and_whitespace_are_collapsed():
    assert normalize_text("pre-\nexisting\r\n\r\ndisease") == "pre-existing disease"
    assert normalize_text("covered   until\n\nmonth 20") == "covered until month 20"


def test_soft_hyphen_is_removed():
    assert normalize_text("insur\u00adance") == "insurance"


def test_match_normalization_tolerates_hyphen_and_spacing_variants():
    expected = normalize_for_match("pre-existing disease")
    assert normalize_for_match("pre-\nexisting   disease") == expected
    assert normalize_for_match("preexisting disease") == expected
    assert normalize_for_match("PRE-EXISTING DISEASE") == expected


def test_match_normalization_expands_ligatures():
    assert normalize_for_match("de\ufb01ned") == normalize_for_match("defined")


def test_typographic_hyphens_compare_like_ascii_hyphens():
    assert normalize_for_match("pre\u2011existing") == normalize_for_match(
        "pre-existing"
    )
    assert normalize_for_match("pre\u2013existing") == normalize_for_match(
        "preexisting"
    )


def test_search_text_handles_common_insurance_spellings():
    assert search_text("Out-patient co-payment sublimit") == (
        "out patient co payment sub limit"
    )
    assert search_text("Outpatient") == "out patient"
