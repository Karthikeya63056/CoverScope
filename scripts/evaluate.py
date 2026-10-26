"""Run the manually verified CoverScope evaluation set.

This script makes live Groq calls. It is not part of the automated test suite.
Use --dry-run to validate the question file without a key or network access.
"""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.document_processing.chunker import chunk_pages
from backend.document_processing.pdf_loader import open_pdf_bytes
from backend.document_processing.quality_checks import assess_quality
from backend.document_processing.text_extractor import extract_pages
from backend.llm.errors import LLMConfigError, LLMError
from backend.llm.groq_client import GroqClient
from backend.qa.answer import AnswerResult, answer_question

DEFAULT_QUESTIONS = ROOT / "evaluation" / "questions.json"


def load_questions(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Question file must contain a non-empty JSON array.")
    required = {"policy", "question", "expected_verdict", "expected_pages"}
    for index, item in enumerate(data, start=1):
        missing = required - set(item)
        if missing:
            raise ValueError(
                f"Question {index} is missing required fields: {sorted(missing)}"
            )
    return data


def load_policy(path: Path):
    opened = open_pdf_bytes(path.read_bytes(), path.name)
    try:
        pages = extract_pages(opened.document)
        report = assess_quality(
            pages,
            min_page_chars=settings.min_page_chars,
            max_extracted_chars=settings.max_extracted_chars,
        )
        if not report.is_usable:
            raise ValueError(
                f"{path.name} was rejected: " + "; ".join(report.errors)
            )
        chunks = chunk_pages(pages, chunk_chars=settings.chunk_chars)
    finally:
        opened.document.close()
    return chunks, report


def evaluate(item: dict, client: GroqClient | None, cache: dict) -> dict:
    policy = Path(item["policy"])
    if not policy.is_file():
        return {**item, "error": f"Missing policy file: {policy}"}

    if str(policy) not in cache:
        cache[str(policy)] = load_policy(policy)
    chunks, report = cache[str(policy)]

    if client is None:
        return {**item, "dry_run": True}

    unreliable_pages = tuple(item.get("unreliable_pages", settings.unreliable_pages))
    try:
        result: AnswerResult = answer_question(
            item["question"],
            chunks,
            client,
            top_k=settings.retrieval_top_k,
            unreliable_pages=unreliable_pages,
            quality_report=report,
        )
    except LLMError as exc:
        return {**item, "error": str(exc)}

    expected_manual = bool(item.get("expect_manual_review", False))
    verdict_match = result.verdict == item["expected_verdict"]
    expected_pages = set(item.get("expected_pages") or ())
    page_match = bool(expected_pages & set(result.cited_pages))
    safe_manual = (
        not expected_manual
        or (
            result.manual_review_required
            and result.verdict not in {"covered", "excluded"}
        )
    )
    unsupported = (
        result.verdict in {"covered", "excluded"} and not result.citations_valid
    )
    return {
        **item,
        "verdict": result.verdict,
        "verdict_match": verdict_match,
        "citation_valid": result.citations_valid,
        "page_match": page_match,
        "manual_review": result.manual_review_required,
        "safe_manual_outcome": safe_manual,
        "unsupported": unsupported,
        "confidence": result.confidence,
        "cited_pages": list(result.cited_pages),
        "expected_manual_review": expected_manual,
        "caveats": list(result.caveats),
    }


def print_report(results: list[dict]) -> None:
    print(
        f"{'#':>2}  {'EXPECTED':<12} {'ACTUAL':<12} {'PAGES':<8} "
        f"{'CIT':<5} {'PG':<4} {'MANUAL':<6} RESULT"
    )
    for index, item in enumerate(results, start=1):
        if "error" in item:
            print(f"{index:>2}  ERROR: {item['error']}")
            continue
        if item.get("dry_run"):
            print(
                f"{index:>2}  {item['expected_verdict']:<12} {'-':<12} "
                f"{item['expected_pages']!s:<8} {'-':<5} {'-':<4} {'-':<6} "
                f"{item['question']}"
            )
            continue
        print(
            f"{index:>2}  {item['expected_verdict']:<12} {item['verdict']:<12} "
            f"{item['cited_pages']!s:<8} "
            f"{'yes' if item['citation_valid'] else 'no':<5} "
            f"{'yes' if item['page_match'] else 'no':<4} "
            f"{'yes' if item['manual_review'] else 'no':<6} "
            f"{item['question']}"
        )


def summarise(results: list[dict]) -> None:
    completed = [
        item for item in results if "error" not in item and not item.get("dry_run")
    ]
    if not completed:
        print("\nNo live results to summarise.")
        return

    scored = [
        item for item in completed if not item.get("expected_manual_review")
    ]
    manual = [
        item for item in completed if item.get("expected_manual_review")
    ]
    verdict_accuracy = (
        sum(1 for item in scored if item["verdict_match"]) / len(scored)
        if scored
        else 0.0
    )
    citation_rate = (
        sum(1 for item in completed if item["citation_valid"]) / len(completed)
    )
    unsupported_rate = sum(1 for item in completed if item["unsupported"]) / len(
        completed
    )
    page_match_rate = (
        sum(1 for item in scored if item["page_match"]) / len(scored)
        if scored
        else 0.0
    )
    manual_safe_rate = (
        sum(1 for item in manual if item["safe_manual_outcome"]) / len(manual)
        if manual
        else 1.0
    )
    print("\nSummary")
    print(f"  Questions completed:       {len(completed)}")
    print(f"  Verdict accuracy:          {verdict_accuracy:.0%} ({len(scored)} scored)")
    print(f"  Expected-page match:       {page_match_rate:.0%} ({len(scored)} scored)")
    print(f"  Citation validity:         {citation_rate:.0%}")
    print(f"  Unsupported answer rate:   {unsupported_rate:.0%}")
    print(f"  Manual-review safe rate:   {manual_safe_rate:.0%}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run CoverScope's live evaluation set.")
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTIONS,
        help="Path to the evaluation JSON file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N questions",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Seconds between live requests (default: 5)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path for JSON results",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the questions without calling Groq",
    )
    args = parser.parse_args(argv)

    try:
        questions = load_questions(args.questions)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2

    if args.limit is not None:
        if args.limit <= 0:
            print("ERROR: --limit must be greater than zero")
            return 2
        questions = questions[: args.limit]

    client: GroqClient | None = None
    if not args.dry_run:
        try:
            client = GroqClient(
                model=settings.groq_model,
                timeout=settings.groq_timeout_seconds,
                max_completion_tokens=settings.groq_max_completion_tokens,
            )
        except LLMConfigError as exc:
            print(f"ERROR: {exc}")
            return 2

    cache: dict = {}
    results: list[dict] = []
    for index, item in enumerate(questions):
        results.append(evaluate(item, client, cache))
        if client is not None and index < len(questions) - 1:
            time.sleep(max(args.delay, 0.0))

    print_report(results)
    summarise(results)

    if args.output is not None:
        args.output.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nResults written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
