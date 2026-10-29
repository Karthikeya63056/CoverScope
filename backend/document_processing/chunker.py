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

    orphan_threshold = min(250, int(chunk_chars * 0.15))

    chunks: list[PolicyChunk] = []
    for page in pages:
        text = page.text.strip()
        if not text:
            continue

        # No overlap: context is not duplicated. Prefer a nearby whitespace
        # boundary to avoid splitting words, while avoiding orphan sentence fragments.
        pieces: list[str] = []
        start = 0
        while start < len(text):
            remainder = len(text) - start
            if pieces and remainder <= orphan_threshold:
                pieces[-1] = pieces[-1] + " " + text[start:].strip()
                break

            end = min(start + chunk_chars, len(text))
            if end < len(text):
                if len(text) - end <= orphan_threshold:
                    end = len(text)
                else:
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
