"""Human-readable diagnostics for extracted PDFs."""
from .text_extractor import ExtractedPage
from .quality_checks import QualityReport


def format_inspection(pages: list[ExtractedPage], report: QualityReport) -> str:
    lines = [
        f"Pages: {report.total_pages}",
        f"Extracted characters: {report.extracted_characters:,}",
        "",
        "Per-page extraction:",
    ]
    for page in pages:
        lines.append(
            f"  Page {page.page_number:>3}: {page.char_count:>6,} chars; "
            f"{page.text_block_count:>3} blocks; {page.image_count:>2} images"
        )
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"  - {warning}" for warning in report.warnings)
    if report.errors:
        lines.extend(["", "Errors:"])
        lines.extend(f"  - {error}" for error in report.errors)
    lines.extend(
        [
            "",
            "TABLE CHECK: Open the extracted text for every flagged page and compare",
            "benefit tables against the rendered PDF. If rows/columns are garbled, try",
            "page.get_text('blocks', sort=True) and inspect block coordinates; if still",
            "unreliable, test pdfplumber on that page/table before accepting the document.",
        ]
    )
    return "\n".join(lines)
