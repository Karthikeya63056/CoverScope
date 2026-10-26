"""Ask a coverage question about a policy PDF using evidence-grounded Groq output.

Usage (from the repository root):
    python scripts/ask_policy.py "pdfs/policy.pdf" "Is a pre-existing disease covered in month 20?"
"""
from pathlib import Path
import argparse
import sys

# Allows running this script from the repository root without installing a package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.document_processing.chunker import chunk_pages
from backend.document_processing.pdf_loader import PDFValidationError, open_pdf_bytes
from backend.document_processing.quality_checks import assess_quality
from backend.document_processing.text_extractor import extract_pages
from backend.llm.errors import LLMConfigError, LLMError
from backend.llm.groq_client import GroqClient
from backend.qa.answer import AnswerResult, answer_question


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Answer a health-insurance policy question with cited evidence."
    )
    parser.add_argument("pdf", help="Path to a public or non-sensitive PDF")
    parser.add_argument("question", help="Coverage question to answer")
    return parser


def _print_result(result: AnswerResult) -> None:
    print(f"Verdict: {result.verdict}")
    print(f"Answer: {result.answer}")
    print(
        f"Confidence: {result.confidence} "
        f"(model confidence; citations verified: "
        f"{'yes' if result.citations_valid else 'no'})"
    )
    if result.manual_review_required:
        print("Manual review required: yes")
    cited_pages = ", ".join(map(str, result.cited_pages)) or "none"
    print(f"Cited pages: {cited_pages}")

    if result.citations:
        print("\nCitations:")
        for citation in result.citations:
            quote = citation.quote
            if len(quote) > 400:
                quote = quote[:397] + "..."
            print(f"  [{citation.chunk_id} | page {citation.page_number}]")
            print(f'    "{quote}"')

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.caveats:
        print("\nCaveats:")
        for caveat in result.caveats:
            print(f"  - {caveat}")

    if result.unverified_answer:
        print("\nUnverified model answer (do not rely on this):")
        print(f"  {result.unverified_answer}")


def main(argv: list[str] | None = None) -> int:
    # Policy PDFs commonly contain ligatures that cp1252 cannot print.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args(argv)
    question = args.question.strip()
    if not question:
        parser.error("question must not be empty")

    path = Path(args.pdf)
    if not path.is_file():
        print(f"ERROR: PDF not found: {path}")
        return 2

    try:
        opened = open_pdf_bytes(path.read_bytes(), path.name)
    except (OSError, ValueError, PDFValidationError) as exc:
        print(f"ERROR: {exc}")
        return 2

    try:
        pages = extract_pages(opened.document)
        report = assess_quality(
            pages,
            min_page_chars=settings.min_page_chars,
            max_extracted_chars=settings.max_extracted_chars,
        )
        if not report.is_usable:
            print("ERROR: The document was rejected:")
            for error in report.errors:
                print(f"  - {error}")
            print(
                "No policy text was truncated. Reduce the document size or "
                "choose a supported text-based PDF."
            )
            return 1

        chunks = chunk_pages(pages, chunk_chars=settings.chunk_chars)
        if not chunks:
            print("ERROR: The document produced no usable text chunks.")
            return 1

        try:
            client = GroqClient(
                model=settings.groq_model,
                timeout=settings.groq_timeout_seconds,
                max_completion_tokens=settings.groq_max_completion_tokens,
            )
        except LLMConfigError as exc:
            print(f"ERROR: {exc}")
            return 2

        try:
            result = answer_question(
                question,
                chunks,
                client,
                top_k=settings.retrieval_top_k,
                unreliable_pages=settings.unreliable_pages,
                quality_report=report,
            )
        except LLMError as exc:
            print(f"ERROR: {exc}")
            return 1

        _print_result(result)
        return 0
    finally:
        opened.document.close()


if __name__ == "__main__":
    raise SystemExit(main())
