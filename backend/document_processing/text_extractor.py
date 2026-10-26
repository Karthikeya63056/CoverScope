"""Page-level text extraction with diagnostics; does not perform OCR."""
from dataclasses import dataclass
import pymupdf


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    char_count: int
    text_block_count: int
    image_count: int


def extract_pages(document: pymupdf.Document) -> list[ExtractedPage]:
    pages: list[ExtractedPage] = []
    for page_index, page in enumerate(document):
        # Sorting helps restore reading order for many PDFs, but is not a guarantee
        # that multi-column layouts or tables are reconstructed correctly.
        text = page.get_text("text", sort=True).strip()
        blocks = page.get_text("blocks", sort=True)
        image_count = len(page.get_images(full=True))

        # Diagnostic fallback only: if the default extraction is very sparse but
        # sorted text blocks contain usable text, rebuild from text blocks.
        if len(text) < 20:
            block_texts = []
            for block in blocks:
                # PyMuPDF text blocks usually have text at index 4; image blocks may not.
                if len(block) > 4 and isinstance(block[4], str) and block[4].strip():
                    block_texts.append(block[4].strip())
            block_text = "\n".join(block_texts).strip()
            if len(block_text) > len(text):
                text = block_text

        pages.append(
            ExtractedPage(
                page_number=page_index + 1,
                text=text,
                char_count=len(text),
                text_block_count=len(blocks),
                image_count=image_count,
            )
        )
    return pages
