"""Document-level and page-level extraction quality checks."""
from dataclasses import dataclass
from .text_extractor import ExtractedPage


@dataclass(frozen=True)
class QualityReport:
    total_pages: int
    extracted_characters: int
    text_poor_pages: list[int]
    image_heavy_pages: list[int]
    table_review_pages: list[int]
    warnings: list[str]
    errors: list[str]

    @property
    def is_usable(self) -> bool:
        return not self.errors


def assess_quality(
    pages: list[ExtractedPage],
    *,
    min_page_chars: int = 40,
    max_extracted_chars: int = 250_000,
) -> QualityReport:
    warnings: list[str] = []
    errors: list[str] = []
    total_chars = sum(page.char_count for page in pages)

    text_poor = [
        page.page_number for page in pages
        if page.char_count < min_page_chars
    ]
    image_heavy = [
        page.page_number for page in pages
        if page.image_count > 0 and page.char_count < min_page_chars * 3
    ]
    # Heuristic only: pages with many text blocks can be tables or multi-column pages.
    table_review = [
        page.page_number for page in pages
        if page.text_block_count >= 25
    ]

    if not pages:
        errors.append("No pages were extracted.")
    if total_chars == 0:
        errors.append(
            "No selectable text was extracted. This may be a scanned PDF; OCR is not supported."
        )
    elif len(text_poor) == len(pages):
        errors.append(
            "Very little selectable text was found. This may be a scanned or unsupported PDF."
        )
    elif text_poor:
        warnings.append(
            "Some pages contain little text: "
            + ", ".join(map(str, text_poor))
            + ". Check whether these are image-only pages or intentionally blank pages."
        )

    if image_heavy:
        warnings.append(
            "Image-heavy pages with little text detected: "
            + ", ".join(map(str, image_heavy))
            + ". Confirm these pages do not contain essential policy wording or tables."
        )
    if table_review:
        warnings.append(
            "Review possible table/multi-column pages manually: "
            + ", ".join(map(str, table_review))
            + ". Text extraction does not guarantee correct table row/column order."
        )
    if total_chars > max_extracted_chars:
        errors.append(
            f"Extracted text is {total_chars:,} characters, exceeding the "
            f"configured limit of {max_extracted_chars:,}. The document was not "
            "truncated. Choose a smaller policy PDF or raise the limit if "
            "appropriate."
        )

    return QualityReport(
        total_pages=len(pages),
        extracted_characters=total_chars,
        text_poor_pages=text_poor,
        image_heavy_pages=image_heavy,
        table_review_pages=table_review,
        warnings=warnings,
        errors=errors,
    )
