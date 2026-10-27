"""Offline evaluation harness for evidence-grounded policy facts.

Compares extracted candidate facts against the manually reviewed gold dataset
in evaluation/gold_facts.json. Computes citation grounding rate, extraction recall,
category match, structured-value exact match, and review/abstention alignment without live API calls.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.document_processing.normalization import normalize_for_match
from backend.domain.adapter import extract_candidate_facts
from backend.domain.enums import FactCategory, FactValidationStatus
from backend.domain.models import PolicyFact
from backend.qa.workflow import prepare_policy

DEFAULT_GOLD_PATH = ROOT_DIR / "evaluation" / "gold_facts.json"


def load_gold_facts(path: Path) -> list[dict[str, Any]]:
    """Load gold evaluation facts from JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _match_candidate_to_gold(
    candidates: list[PolicyFact],
    gold_quote: str,
    gold_cat: str,
    gold_val: dict[str, Any] | None,
) -> PolicyFact | None:
    """Find candidate fact matching gold item by quote overlap or value + scope.

    Never falls back to an arbitrary fact on the same page.
    """
    norm_gold = normalize_for_match(gold_quote)
    gold_tokens = set(norm_gold.split())

    # Strategy 1: Quotation containment or high token overlap
    for cand in candidates:
        ev_quote = cand.evidence_references[0].exact_text if cand.evidence_references else ""
        norm_ev = normalize_for_match(ev_quote)
        if norm_gold in norm_ev or norm_ev in norm_gold:
            return cand

        cand_tokens = set(norm_ev.split())
        common = gold_tokens & cand_tokens
        if len(common) >= 3 and (len(common) / max(1, len(cand_tokens))) >= 0.35:
            return cand

    # Strategy 2: Exact value match with topical scope keyword overlap
    if gold_val is not None:
        gold_amt = gold_val.get("amount")
        gold_pct = gold_val.get("percentage")
        for cand in candidates:
            sv = cand.structured_value
            if sv is None:
                continue
            cand_amt = getattr(sv, "amount", None)
            cand_pct = getattr(sv, "percentage", None)

            val_matches = False
            if gold_amt is not None and cand_amt == gold_amt:
                val_matches = True
            elif gold_pct is not None and cand_pct is not None and abs(cand_pct - gold_pct) < 0.01:
                val_matches = True

            if val_matches:
                cand_prop = cand.proposition.lower()
                # Check at least one relevant keyword overlaps
                keywords = ("pre-existing", "ped", "waiting", "exclusion", "sublimit", "copay", "bariatric", "initial")
                if any(kw in cand_prop for kw in keywords if kw in norm_gold):
                    return cand

    return None


def evaluate_policy_facts(
    gold_facts: list[dict[str, Any]],
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Evaluate candidate fact extraction against gold facts with explicit metrics."""
    # Cache prepared policies by file path
    prepared_policies: dict[str, Any] = {}
    extracted_facts_by_doc: dict[str, list[PolicyFact]] = {}

    for item in gold_facts:
        rel_path = item["document_file"]
        if rel_path not in prepared_policies:
            full_path = ROOT_DIR / rel_path
            if not full_path.exists():
                raise FileNotFoundError(f"Policy PDF not found: {full_path}")
            with open(full_path, "rb") as f:
                data = f.read()
            policy = prepare_policy(data, full_path.name)
            prepared_policies[rel_path] = policy
            extracted_facts_by_doc[rel_path] = extract_candidate_facts(policy)

    total_gold = len(gold_facts)
    active_gold_facts = len([g for g in gold_facts if g.get("expected_status") != "rejected"])
    negative_gold_facts = total_gold - active_gold_facts

    citation_grounded_count = 0
    extraction_recalled_count = 0
    category_match_count = 0
    value_match_count = 0
    value_applicable_count = 0
    review_alignment_count = 0

    per_category: dict[str, dict[str, int]] = {}
    details: list[dict[str, Any]] = []
    matched_candidate_ids: set[str] = set()

    for item in gold_facts:
        gold_id = item["id"]
        rel_path = item["document_file"]
        page_num = item["page_number"]
        gold_quote = item["quote"]
        gold_cat = item["category"]
        gold_val = item.get("expected_value")
        gold_status = item.get("expected_status", "evidence_grounded")

        cat_stats = per_category.setdefault(gold_cat, {"gold": 0, "grounded": 0, "extracted": 0, "cat_match": 0, "val_match": 0})
        cat_stats["gold"] += 1

        policy = prepared_policies[rel_path]
        extracted = extracted_facts_by_doc[rel_path]

        # Check if gold quote actually exists on the cited page
        page_obj = next((p for p in policy.pages if p.page_number == page_num), None)
        quote_on_page = False
        if page_obj:
            quote_on_page = normalize_for_match(gold_quote) in normalize_for_match(page_obj.text)

        # Look for matching extracted fact on same page
        page_candidates = [
            f for f in extracted
            if any(ev.page_number == page_num for ev in f.evidence_references)
        ]

        best_fact = _match_candidate_to_gold(page_candidates, gold_quote, gold_cat, gold_val)
        if best_fact is not None:
            matched_candidate_ids.add(best_fact.fact_id)

        # Negative test case (expected_status == "rejected")
        if gold_status == "rejected":
            # Pass if quote is absent or no verified candidate was emitted
            is_correctly_rejected = (not quote_on_page) and (best_fact is None or best_fact.validation_status == FactValidationStatus.NEEDS_REVIEW)
            if is_correctly_rejected:
                review_alignment_count += 1

            details.append({
                "id": gold_id,
                "document": Path(rel_path).name,
                "page": page_num,
                "category_expected": gold_cat,
                "category_predicted": best_fact.category.value if best_fact else None,
                "value_expected": None,
                "value_predicted": None,
                "grounded": quote_on_page,
                "review_aligned": is_correctly_rejected,
                "status": "PASS (Correctly rejected/unverified)" if is_correctly_rejected else "FAIL (Unexpectedly accepted)",
                "failure_reason": None if is_correctly_rejected else "Negative test case unexpectedly matched an accepted fact",
                "note": item.get("notes", ""),
            })
            continue

        # Positive assertions
        if quote_on_page:
            citation_grounded_count += 1
            cat_stats["grounded"] += 1

        if gold_val is not None:
            value_applicable_count += 1

        cat_matches = False
        val_matches = False
        review_aligned = False
        failure_reasons: list[str] = []

        pred_val_str = None
        if best_fact is not None:
            extraction_recalled_count += 1
            cat_stats["extracted"] += 1

            cat_matches = (best_fact.category.value == gold_cat)
            if cat_matches:
                category_match_count += 1
                cat_stats["cat_match"] += 1
            else:
                failure_reasons.append(f"Category mismatch: expected {gold_cat!r}, got {best_fact.category.value!r}")

            sv = best_fact.structured_value
            if sv is not None:
                if hasattr(sv, "amount") and hasattr(sv, "unit"):
                    pred_val_str = f"{sv.amount} {sv.unit.value}"
                elif hasattr(sv, "percentage"):
                    pred_val_str = f"{sv.percentage:g}%"
                elif hasattr(sv, "amount"):
                    pred_val_str = f"Rs {sv.amount:g}"

            if gold_val is not None and sv is not None:
                if gold_val.get("type") == "duration" and hasattr(sv, "amount") and hasattr(sv, "unit"):
                    if sv.amount == gold_val["amount"] and sv.unit.value == gold_val["unit"]:
                        val_matches = True
                elif gold_val.get("type") == "percentage" and hasattr(sv, "percentage"):
                    if abs(sv.percentage - gold_val["percentage"]) < 0.01:
                        val_matches = True
                elif gold_val.get("type") == "monetary" and hasattr(sv, "amount"):
                    if abs(sv.amount - gold_val["amount"]) < 1.0:
                        val_matches = True

                if val_matches:
                    value_match_count += 1
                    cat_stats["val_match"] += 1
                else:
                    failure_reasons.append(f"Value mismatch: expected {gold_val}, got {pred_val_str}")
            elif gold_val is not None and sv is None:
                failure_reasons.append("Missing structured value in prediction")

            # Check review alignment
            if gold_status == "needs_review":
                review_aligned = (
                    best_fact.validation_status == FactValidationStatus.NEEDS_REVIEW
                    or bool(best_fact.review_reasons)
                    or bool(best_fact.conditions)
                    or bool(best_fact.exceptions)
                )
                if not review_aligned:
                    failure_reasons.append("Expected needs_review status but fact was accepted unconditionally")
            else:
                review_aligned = (best_fact.validation_status != FactValidationStatus.REJECTED)

            if review_aligned:
                review_alignment_count += 1

            if not quote_on_page:
                failure_reasons.append("Source quote not found verbatim on cited page")

            if not failure_reasons:
                status_label = "PASS"
            elif gold_status == "needs_review" and cat_matches and (val_matches or gold_val is None):
                status_label = "PASS (Flagged for Review)"
            else:
                status_label = "FAIL"
        else:
            status_label = "MISS (Not extracted)"
            failure_reasons.append("Clause was not extracted by candidate pipeline")

        exp_val_str = None
        if gold_val:
            exp_val_str = (
                f"{gold_val['amount']} {gold_val.get('unit', '')}".strip()
                if "amount" in gold_val
                else f"{gold_val.get('percentage')}%"
            )

        details.append({
            "id": gold_id,
            "document": Path(rel_path).name,
            "page": page_num,
            "category_expected": gold_cat,
            "category_predicted": best_fact.category.value if best_fact else None,
            "value_expected": exp_val_str,
            "value_predicted": pred_val_str,
            "grounded": quote_on_page,
            "review_aligned": review_aligned,
            "status": status_label,
            "failure_reason": "; ".join(failure_reasons) if failure_reasons else None,
            "note": item.get("notes", ""),
        })

    # Extractor precision/redundancy diagnostics
    all_extracted_facts = [f for facts in extracted_facts_by_doc.values() for f in facts]
    total_candidates = len(all_extracted_facts)
    unmatched_candidates = total_candidates - len(matched_candidate_ids)

    grounding_rate = (citation_grounded_count / active_gold_facts) * 100.0 if active_gold_facts else 0.0
    recall_rate = (extraction_recalled_count / active_gold_facts) * 100.0 if active_gold_facts else 0.0
    category_acc = (category_match_count / active_gold_facts) * 100.0 if active_gold_facts else 0.0
    val_acc = (value_match_count / value_applicable_count) * 100.0 if value_applicable_count else 0.0
    review_align_rate = (review_alignment_count / total_gold) * 100.0 if total_gold else 0.0

    return {
        "total_gold_facts": total_gold,
        "active_gold_facts": active_gold_facts,
        "negative_gold_facts": negative_gold_facts,
        "metrics": {
            "citation_grounding": {
                "numerator": citation_grounded_count,
                "denominator": active_gold_facts,
                "percentage": grounding_rate,
            },
            "extraction_recall": {
                "numerator": extraction_recalled_count,
                "denominator": active_gold_facts,
                "percentage": recall_rate,
            },
            "category_match_accuracy": {
                "numerator": category_match_count,
                "denominator": active_gold_facts,
                "percentage": category_acc,
            },
            "value_match_accuracy": {
                "numerator": value_match_count,
                "denominator": value_applicable_count,
                "percentage": val_acc,
            },
            "review_alignment_rate": {
                "numerator": review_alignment_count,
                "denominator": total_gold,
                "percentage": review_align_rate,
            },
        },
        "candidate_diagnostics": {
            "total_candidates_extracted": total_candidates,
            "matched_candidates_count": len(matched_candidate_ids),
            "unmatched_candidates_count": unmatched_candidates,
        },
        "per_category": per_category,
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate evidence-grounded policy facts offline.")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD_PATH, help="Path to gold facts JSON")
    parser.add_argument("--output", type=Path, default=None, help="Optional output JSON report path")
    parser.add_argument("--verbose", action="store_true", help="Print detailed per-fact diagnostics")
    args = parser.parse_args()

    if not args.gold.exists():
        print(f"Error: Gold dataset not found at {args.gold}", file=sys.stderr)
        sys.exit(1)

    print("======================================================================")
    print("CoverScope Offline Policy Fact Quality & Semantic Evaluation Harness")
    print("======================================================================")
    print(f"Loading gold dataset: {args.gold}")

    gold_facts = load_gold_facts(args.gold)
    results = evaluate_policy_facts(gold_facts, verbose=args.verbose)
    m = results["metrics"]
    diag = results["candidate_diagnostics"]

    print(f"\nEvaluated {results['total_gold_facts']} gold items ({results['active_gold_facts']} active, {results['negative_gold_facts']} negative) across 3 public policy wordings.\n")
    print("Aggregate Benchmark Metrics (with explicit denominators):")
    print(f"  - Citation Grounding Rate:       {m['citation_grounding']['numerator']}/{m['citation_grounding']['denominator']} ({m['citation_grounding']['percentage']:.1f}%)")
    print(f"  - Extraction Recall:             {m['extraction_recall']['numerator']}/{m['extraction_recall']['denominator']} ({m['extraction_recall']['percentage']:.1f}%)")
    print(f"  - Category Match Rate:           {m['category_match_accuracy']['numerator']}/{m['category_match_accuracy']['denominator']} ({m['category_match_accuracy']['percentage']:.1f}%)")
    print(f"  - Structured Value Exact Match:  {m['value_match_accuracy']['numerator']}/{m['value_match_accuracy']['denominator']} ({m['value_match_accuracy']['percentage']:.1f}%)")
    print(f"  - Review/Abstention Alignment:   {m['review_alignment_rate']['numerator']}/{m['review_alignment_rate']['denominator']} ({m['review_alignment_rate']['percentage']:.1f}%)")

    print(f"\nCandidate Diagnostics: {diag['total_candidates_extracted']} total candidates, {diag['matched_candidates_count']} matched to gold, {diag['unmatched_candidates_count']} unmatched/unlabeled.")

    print("\nPer-Category Breakdown:")
    print(f"{'Category':<24} | {'Gold':<5} | {'Grounded':<8} | {'Extracted':<9} | {'Cat Match':<10} | {'Val Match':<10}")
    print("-" * 75)
    for cat, stats in results["per_category"].items():
        print(f"{cat:<24} | {stats['gold']:<5} | {stats['grounded']:<8} | {stats['extracted']:<9} | {stats['cat_match']:<10} | {stats['val_match']:<10}")

    print("\nPer-Fact Evaluation Diagnostics:")
    for d in results["details"]:
        exp_v = d["value_expected"] or "None"
        pred_v = d["value_predicted"] or "None"
        status_info = d["status"]
        fail_note = f" -> {d['failure_reason']}" if d["failure_reason"] else ""
        print(f"  [{d['id']}] p.{d['page']:<2} {d['category_expected']:<18} | exp_val: {exp_v:<8} | pred_val: {pred_v:<8} | {status_info}{fail_note}")

    print("\n" + "=" * 70)
    print("AUDIT NOTICE: Gold dataset is a micro-benchmark (15 items across 3 documents)")
    print("designed for regression testing and gate verification. These metrics measure")
    print("extractor conformity on sample provisions, NOT production accuracy on unseen wordings.")
    print("=" * 70)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved report to {args.output}")

    print("\nEvaluation successfully completed without external provider calls.")


if __name__ == "__main__":
    main()
