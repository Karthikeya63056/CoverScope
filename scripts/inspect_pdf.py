from pathlib import Path
import argparse
import sys

# Allows running this script from the repository root without installing a package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.document_processing.pdf_loader import open_pdf_bytes
from backend.document_processing.text_extractor import extract_pages
from backend.document_processing.quality_checks import assess_quality
from backend.document_processing.inspection import format_inspection


def main() -> int:
    # Policy PDFs commonly contain ligatures (e.g. "fi") that the default
    # Windows console encoding (cp1252) cannot print.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Inspect a policy PDF's extraction quality.")
    parser.add_argument("pdf", help="Path to a public or non-sensitive PDF")
    args = parser.parse_args()
    path = Path(args.pdf)

    try:
        opened = open_pdf_bytes(path.read_bytes(), path.name)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    try:
        pages = extract_pages(opened.document)
        report = assess_quality(
            pages,
            min_page_chars=settings.min_page_chars,
            max_extracted_chars=settings.max_extracted_chars,
        )
        print(format_inspection(pages, report))
        sample_page = next((page for page in pages if page.text.strip()), None)
        if sample_page is not None:
            print(
                f"\nSample extracted text (page {sample_page.page_number}, "
                "first 1,000 chars):"
            )
            print(sample_page.text[:1000])
        return 0 if report.is_usable else 1
    finally:
        opened.document.close()


if __name__ == "__main__":
    raise SystemExit(main())
