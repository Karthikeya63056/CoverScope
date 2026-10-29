import json
import os
import sys
import time
import hashlib
from typing import Any, Dict, List

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath("."))

from backend.config import settings
from backend.services.policy_service import PolicyService
from backend.qa.workflow import prepare_policy
from backend.qa.retrieval import retrieve_chunks

ARTIFACT_DIR = r"C:\Users\Lenovo\.gemini\antigravity\brain\d05457e4-f653-4909-a545-212d3b0d9ce6"
PDF_PATH = r"pdfs\Brochure_Star_Comprehensive_Insurance_Policy_V_15_Web_633bcfcaaf.pdf"

with open(PDF_PATH, "rb") as f:
    pdf_bytes = f.read()
pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

print("="*60)
print("COVERSCOPE STAGE 2 INTENT-AWARE SYNTHESIS & RELEVANCE EVALUATION")
print("="*60)
print(f"Target PDF: {PDF_PATH}")
print(f"PDF SHA256: {pdf_sha256}")
print(f"Model ID: {settings.groq_model}")
print(f"Retrieval Top-K: {settings.retrieval_top_k}")
print("="*60)

policy_service = PolicyService()
processed_policy = prepare_policy(pdf_bytes, os.path.basename(PDF_PATH))
print(f"Policy Processed: {processed_policy.page_count} pages, {len(processed_policy.chunks)} chunks.")

BENCHMARK_CASES = [
    {
        "id": "TC-1",
        "category": "FM-1: Lexical Miss / Medical Synonym",
        "question": "Is keyhole surgery for joint pain covered?",
        "governing_pages": [4, 12],
        "expected_verdict": "depends",
        "target_provisions": "Page 4 (Day Care Treatment covered up to Sum Insured); Page 12 (Specified Disease/Procedure Waiting Period 24m)"
    },
    {
        "id": "TC-2",
        "category": "FM-1: Lexical Miss / Layperson Phrasing",
        "question": "Will the policy pay if I get admitted for food poisoning in the first 2 weeks?",
        "governing_pages": [12],
        "expected_verdict": "excluded",
        "target_provisions": "Page 12 (Initial Waiting Period: 30 days)"
    },
    {
        "id": "TC-3",
        "category": "FM-2: Multi-Clause Synthesis",
        "question": "Will the policy cover bariatric surgery for my 62-year-old father in month 20?",
        "governing_pages": [4, 9, 12],
        "expected_verdict": "excluded",
        "target_provisions": "Page 9 & 12 (Bariatric Surgery: 36 months waiting period, ₹2.5L/₹5L sublimit); Page 4 (10% co-payment for entry age 61+)"
    },
    {
        "id": "TC-4",
        "category": "FM-2: Multi-Clause Synthesis (Benefit vs Cosmetic Exclusion)",
        "question": "Can I claim expenses for bariatric surgery done for weight loss?",
        "governing_pages": [9, 12, 13],
        "expected_verdict": "depends",
        "target_provisions": "Page 9 & 12 (Bariatric Surgery covered with 36m waiting & sub-limit) vs Page 13 (Cosmetic Surgery excluded)"
    },
    {
        "id": "TC-5",
        "category": "FM-3: Citation Verification on Formatted Text",
        "question": "What is the waiting period for pre-existing diseases and can it be reduced?",
        "governing_pages": [12],
        "expected_verdict": "depends",
        "target_provisions": "Page 12 (PED Waiting Period: 36 months; Buy Back optional cover reduces to 12 months)"
    },
    {
        "id": "TC-6_Turn1",
        "category": "FM-4: Conversational Reference - Turn 1",
        "question": "Is bariatric surgery covered under this policy?",
        "governing_pages": [9, 12],
        "expected_verdict": "covered",
        "target_provisions": "Page 9 (Bariatric surgery hospitalization payable up to specified limits)"
    },
    {
        "id": "TC-6_Turn2",
        "category": "FM-4: Conversational Reference - Turn 2 (Follow-up)",
        "question": "What is the waiting period for that?",
        "governing_pages": [9, 12],
        "expected_verdict": "covered",
        "target_provisions": "Page 9 & 12 (Bariatric Surgery: 36 months waiting period)"
    },
    {
        "id": "TC-7",
        "category": "Negative Control: Out of Scope Abstention",
        "question": "Does this policy cover damage to my vehicle or car accident repairs?",
        "governing_pages": [],
        "expected_verdict": "not_stated",
        "target_provisions": "Health policy brochure does not contain motor damage provisions"
    },
    {
        "id": "TC-8",
        "category": "Simple Factual Parity Control",
        "question": "What is the room category permitted for normal hospital room rent?",
        "governing_pages": [4],
        "expected_verdict": "covered",
        "target_provisions": "Page 4 (Room Rent: Single Private A/C Room, covered up to Sum Insured)"
    }
]

results = []

for case in BENCHMARK_CASES:
    q = case["question"]
    print(f"\n--- Running {case['id']}: '{q}' ---")
    start_time = time.time()
    
    # 1. Retrieval Layer Check
    retrieval_start = time.time()
    retrieved = retrieve_chunks(q, processed_policy.chunks, top_k=settings.retrieval_top_k)
    retrieval_ms = int((time.time() - retrieval_start) * 1000)
    
    retrieved_pages = sorted(list({c.page_number for c in retrieved}))
    retrieved_chunk_ids = [c.chunk_id for c in retrieved]
    
    expected_pages = set(case["governing_pages"])
    retrieval_hit = bool(expected_pages.intersection(set(retrieved_pages))) if expected_pages else (len(retrieved) == 0)
    full_retrieval_hit = expected_pages.issubset(set(retrieved_pages)) if expected_pages else True
    
    model_invoked = False
    verdict = None
    confidence = None
    citations_valid = False
    manual_review = False
    answer_text = ""
    citations_info = []
    error = None
    model_ms = 0

    try:
        model_start = time.time()
        try:
            ans_result = policy_service.ask_question(processed_policy, q)
        except Exception as first_exc:
            if "rate limit" in str(first_exc).lower():
                print(" -> Rate limit hit, cooling down 10s and retrying...")
                time.sleep(10.0)
                ans_result = policy_service.ask_question(processed_policy, q)
            else:
                raise first_exc
        model_ms = int((time.time() - model_start) * 1000)
        total_latency_ms = int((time.time() - start_time) * 1000)
        
        model_invoked = len(retrieved) > 0
        verdict = str(ans_result.verdict)
        confidence = str(ans_result.confidence)
        citations_valid = bool(ans_result.citations_valid)
        manual_review = bool(ans_result.manual_review_required)
        answer_text = ans_result.answer
        citations_info = [
            {"chunk_id": c.chunk_id, "page": c.page_number, "quote": c.quote, "verified": c.verified}
            for c in ans_result.citations
        ]
        time.sleep(4.0)  # Rate limit cooldown
    except Exception as exc:
        total_latency_ms = int((time.time() - start_time) * 1000)
        error = str(exc)
        print(f"Execution Error: {exc}")

    citation_support_verified = citations_valid and len(citations_info) > 0 if verdict != "not_stated" else True

    res_entry = {
        "id": case["id"],
        "category": case["category"],
        "question": q,
        "governing_pages_expected": case["governing_pages"],
        "retrieved_pages": retrieved_pages,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "governing_clause_found": retrieval_hit,
        "all_governing_clauses_found": full_retrieval_hit,
        "model_invoked": model_invoked,
        "verdict": verdict,
        "expected_verdict": case["expected_verdict"],
        "verdict_match": (verdict == case["expected_verdict"]),
        "citations_valid": citations_valid,
        "citation_support_verified": citation_support_verified,
        "manual_review_required": manual_review,
        "citations": citations_info,
        "retrieval_ms": retrieval_ms,
        "model_ms": model_ms,
        "total_latency_ms": total_latency_ms,
        "answer_snippet": answer_text[:200] if answer_text else "",
        "full_answer": answer_text,
        "error": error
    }
    results.append(res_entry)
    print(f" -> Governing Clause Found: {retrieval_hit} (Pages: {retrieved_pages} vs Exp: {case['governing_pages']})")
    print(f" -> Multi-Clause Full Hit: {full_retrieval_hit}")
    print(f" -> Verdict: {verdict} (Expected: {case['expected_verdict']}) | Match: {verdict == case['expected_verdict']}")
    print(f" -> Citations Valid: {citations_valid} | Manual Review: {manual_review}")
    print(f" -> Retrieval Latency: {retrieval_ms}ms | Model Latency: {model_ms}ms | Total: {total_latency_ms}ms")

# Summary Analysis
total_cases = len(results)
retrieval_success_count = sum(1 for r in results if r["governing_clause_found"])
full_retrieval_success_count = sum(1 for r in results if r["all_governing_clauses_found"])
verdict_matches = sum(1 for r in results if r["verdict_match"])
citations_valid_count = sum(1 for r in results if r["citations_valid"])
manual_reviews_triggered = sum(1 for r in results if r["manual_review_required"])
avg_retrieval_ms = sum(r["retrieval_ms"] for r in results) // total_cases
avg_model_ms = sum(r["model_ms"] for r in results) // total_cases
avg_total_latency = sum(r["total_latency_ms"] for r in results) // total_cases

summary = {
    "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "stage": "Stage 2 — Intent-Aware Evidence Synthesis & Citation Relevance",
    "pdf_file": PDF_PATH,
    "pdf_sha256": pdf_sha256,
    "model": settings.groq_model,
    "top_k": settings.retrieval_top_k,
    "total_test_cases": total_cases,
    "governing_clause_retrieval_rate": f"{retrieval_success_count}/{total_cases} ({retrieval_success_count/total_cases*100:.1f}%)",
    "all_governing_clauses_retrieval_rate": f"{full_retrieval_success_count}/{total_cases} ({full_retrieval_success_count/total_cases*100:.1f}%)",
    "verdict_accuracy_rate": f"{verdict_matches}/{total_cases} ({verdict_matches/total_cases*100:.1f}%)",
    "citations_valid_rate": f"{citations_valid_count}/{total_cases} ({citations_valid_count/total_cases*100:.1f}%)",
    "manual_reviews_triggered": f"{manual_reviews_triggered}/{total_cases}",
    "average_retrieval_ms": avg_retrieval_ms,
    "average_model_ms": avg_model_ms,
    "average_total_latency_ms": avg_total_latency,
    "cases": results
}

output_path = os.path.join(ARTIFACT_DIR, "qa_stage2_evaluation_report.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\n" + "="*60)
print("STAGE 2 EVALUATION COMPLETED")
print(f"Results saved to: {output_path}")
print(f"Governing Clause Retrieval: {summary['governing_clause_retrieval_rate']}")
print(f"Multi-Clause Full Retrieval: {summary['all_governing_clauses_retrieval_rate']}")
print(f"Verdict Accuracy: {summary['verdict_accuracy_rate']}")
print(f"Citations Valid: {summary['citations_valid_rate']}")
print(f"Average Retrieval Time: {avg_retrieval_ms}ms")
print(f"Average Total Latency: {avg_total_latency}ms")
print("="*60)
