"""Unicode normalization for retrieval and citation comparison.

Extracted page text and chunk text are kept exactly as PyMuPDF produced them;
normalization is applied only when searching or comparing. Displayed quotations
therefore keep the original characters from the PDF.
"""
import re
import unicodedata

# A hyphen at the end of a line is usually a layout artifact. Keep the hyphen
# (so "pre-\nexisting" becomes "pre-existing") and let normalize_for_match()
# remove hyphens when checking a quotation.
_LINE_BREAK_HYPHEN = re.compile(r"(?<=\w)-\s*\n\s*(?=\w)")
_WHITESPACE = re.compile(r"\s+")
_MATCH_IGNORED = re.compile(r"[\s\-\u00ad]+")
# Models frequently emit typographic hyphens/dashes where the PDF has "-".
_DASH_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",  # hyphen
        "\u2011": "-",  # non-breaking hyphen
        "\u2012": "-",  # figure dash
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2015": "-",  # horizontal bar
        "\u2212": "-",  # minus sign
    }
)


def normalize_text(text: str) -> str:
    """Return NFKC-normalized text with line-break artifacts collapsed.

    Ligatures such as U+FB01 (fi), U+FB00 (ff), and U+FB03 (ffi) are expanded
    by NFKC. Whitespace runs (including newlines) become a single space.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\u00ad", "")  # soft hyphen
    normalized = normalized.translate(_DASH_TRANSLATION)
    normalized = _LINE_BREAK_HYPHEN.sub("-", normalized)
    normalized = _WHITESPACE.sub(" ", normalized)
    return normalized.strip()


def normalize_for_match(text: str) -> str:
    """Casefold and remove whitespace/hyphens for tolerant quote matching.

    Two renderings of the same clause must compare equal even when one has a
    line-break hyphen, a soft hyphen, or different spacing.
    """
    return _MATCH_IGNORED.sub("", normalize_text(text).casefold())


def search_text(text: str) -> str:
    """Lowercase, NFKC-normalized text prepared for token/phrase search.

    Hyphens become spaces so "pre-existing" and "pre existing" tokenize the
    same way. A few common insurance spellings are expanded for the same
    reason; this is a fixed, explainable list, not a learned synonym model.
    """
    normalized = normalize_text(text).casefold()
    normalized = normalized.replace("outpatient", "out patient")
    normalized = normalized.replace("inpatient", "in patient")
    normalized = normalized.replace("copayment", "co payment")
    normalized = normalized.replace("copay", "co payment")
    normalized = normalized.replace("sublimit", "sub limit")
    return normalized.replace("-", " ")
