"""Text, byte, and markdown formatting utilities for CoverScope."""
from __future__ import annotations

from frontend.messages import CONFIDENCE_LABELS, VERDICT_LABELS


def format_bytes(size: int) -> str:
    """Return human-readable byte size for document metadata."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def verdict_label(verdict: str) -> str:
    """Return display label for one of the four backend verdicts."""
    return VERDICT_LABELS.get(verdict, verdict.replace("_", " ").title())


def confidence_label(confidence: str) -> str:
    """Return display label for the model-reported confidence level."""
    return CONFIDENCE_LABELS.get(confidence, confidence.title())


def escape_md(text: str) -> str:
    """Escape markdown special characters to prevent broken formatting."""
    for char in "\\`*_{}[]<>#|":
        text = text.replace(char, "\\" + char)
    return text


def blockquote(text: str) -> str:
    """Format multiline text as a markdown blockquote."""
    lines = text.strip().splitlines() or [""]
    return "\n".join("> " + line if line.strip() else ">" for line in lines)


def clean_html(html: str) -> str:
    """Format multiline HTML for safe st.markdown rendering without CommonMark code block pitfalls.

    Strips all leading and trailing whitespace from every line, eliminating 4-space
    indented code block interpretation and removing empty lines.
    """
    lines = [line.strip() for line in html.strip().splitlines() if line.strip()]
    return "\n".join(lines)


# Private aliases for backwards compatibility with tests
_escape_md = escape_md
_blockquote = blockquote
