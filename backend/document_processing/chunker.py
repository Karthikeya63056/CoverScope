"""Stable page-based chunks with no overlap in model context."""
from dataclasses import dataclass
from .text_extractor import ExtractedPage


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str
    page_number: int
    text: str


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    chunk_chars: int = 1_800,
) -> list[PolicyChunk]:
    if chunk_chars <= 0:
        raise ValueError("chunk_chars must be greater than zero")

    chunks: list[PolicyChunk] = []
    for page in pages:
        text = page.text.strip()
        if not text:
            continue

        # No overlap: context is not duplicated. Prefer a nearby whitespace
        # boundary to avoid splitting words, while guaranteeing forward progress.
        pieces: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_chars, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + int(chunk_chars * 0.75), end)
                if boundary > start:
                    end = boundary
            piece = text[start:end].strip()
            if piece:
                pieces.append(piece)
            start = end
            while start < len(text) and text[start].isspace():
                start += 1

        for piece_index, piece in enumerate(pieces, start=1):
            chunks.append(
                PolicyChunk(
                    chunk_id=f"P{page.page_number}-C{piece_index}",
                    page_number=page.page_number,
                    text=piece,
                )
            )
    return chunks
