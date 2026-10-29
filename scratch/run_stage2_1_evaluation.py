import json
import os
import sys
import time
import hashlib
import numpy as np
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

print("="*70)
print("COVERSCOPE STAGE 2.1 — HELD-OUT RELIABILITY & CITATION AUDIT")
print("="*70)
print(f"Target PDF: {PDF_PATH}")
print(f"PDF SHA256: {pdf_sha256}")
print(f"Model ID: {settings.groq_model}")
print(f"Retrieval Top-K: {settings.retrieval_top_k}")
print("="*70)

policy_service = PolicyService()
processed_policy = prepare_policy(pdf_bytes, os.path.basename(PDF_PATH))
print(f"Policy Processed: {processed_policy.page_count} pages, {len(processed_policy.chunks)} chunks.")

# 1. ORIGINAL 9 BENCHMARK CASES
ORIGINAL_BENCHMARK = [
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

# 2. HELD-OUT CHALLENGE SET (10 UNSEEN SCENARIOS)
HELDOUT_CHALLENGE_SET = [
    {
        "id": "HT-1",
        "category": "Benefit Limit & Mandatory Precondition",
        "question": "Does the policy cover air ambulance charges and what is the maximum limit per hospitalization?",
        "governing_pages": [6],
        "expected_verdict": "covered",
        "target_provisions": "Page 6 (Air Ambulance up to ₹2,50,000 per hospitalization, subject to admissible hospitalization claim)"
    },
    {
        "id": "HT-2",
        "category": "Domiciliary Exclusion Interaction",
        "question": "Can I claim domiciliary hospitalization expenses if my father is treated at home for acute bronchitis?",
        "governing_pages": [6, 7],
        "expected_verdict": "excluded",
        "target_provisions": "Page 7 (Domiciliary Hospitalization explicitly excludes Bronchitis, Asthma, Arthritis, etc.)"
    },
    {
        "id": "HT-3",
        "category": "Benefit Tier / Conditional Prior Approval",
        "question": "Are treatments under Ayurveda and Yoga covered up to the sum insured?",
        "governing_pages": [4],
        "expected_verdict": "depends",
        "target_provisions": "Page 4 (AYUSH: Ayurveda payable up to Sum Insured; Yoga/Naturopathy subject to prior approval)"
    },
    {
        "id": "HT-4",
        "category": "Multi-Year Policy Block Prerequisite",
        "question": "Can I claim ₹10,000 for outpatient dental treatment in the very first month of taking the policy?",
        "governing_pages": [10],
        "expected_verdict": "depends",
        "target_provisions": "Page 10 (Dental & Ophthalmic limit applies for each block of 3 continuous years)"
    },
    {
        "id": "HT-5",
        "category": "Express Policy Exclusion",
        "question": "Does this policy pay for admission for rest cure or rehabilitation care?",
        "governing_pages": [13],
        "expected_verdict": "excluded",
        "target_provisions": "Page 13 (Key Exclusions: Rest Cure, rehabilitation, and respite care are excluded)"
    },
    {
        "id": "HT-6",
        "category": "Deductible / Minimum Stay Threshold",
        "question": "If I am hospitalized for 1 day, will I receive the hospital cash benefit?",
        "governing_pages": [10, 11],
        "expected_verdict": "excluded",
        "target_provisions": "Page 10 (Hospital Cash Benefit is subject to a 1 day Deductible; no cash payable for 1-day stay)"
    },
    {
        "id": "HT-7",
        "category": "Negative Control: Out of Scope Abstention",
        "question": "Does the policy cover medical and veterinary treatments for household pets?",
        "governing_pages": [],
        "expected_verdict": "not_stated",
        "target_provisions": "Brochure contains no provisions for veterinary or pet medical coverage"
    },
    {
        "id": "HT-8",
        "category": "Entry Age Boundary & Dual Route Eligibility",
        "question": "Can a 2-month-old newborn infant be covered under this policy as a dependent child?",
        "governing_pages": [3, 8],
        "expected_verdict": "depends",
        "target_provisions": "Page 3 (Dependent child entry age: 91 days) vs Page 8 (Newborn delivery expenses cover from birth)"
    },
    {
        "id": "HT-9",
        "category": "Modern Treatment Sublimit Condition",
        "question": "Are modern treatments like Deep Brain Stimulation and Balloon Sinoplasty covered without any sublimits?",
        "governing_pages": [5],
        "expected_verdict": "depends",
        "target_provisions": "Page 5 (Modern Treatments covered up to limits specified in policy wordings, not unlimited)"
    },
    {
        "id": "HT-10",
        "category": "Restricted Benefit Utilization",
        "question": "Can the insured person utilize the additional organ donor sum insured for their own treatment expenses?",
        "governing_pages": [6],
        "expected_verdict": "excluded",
        "target_provisions": "Page 6 (Additional donor sum insured can be utilized by the Donor and NOT by the Insured Person)"
    }
]

def evaluate_case_list(cases: List[Dict[str, Any]], suite_name: str) -> Dict[str, Any]:
    print(f"\n{'='*30} RUNNING {suite_name} ({len(cases)} cases) {'='*30}")
    results = []
    retrieval_latencies = []
    model_latencies = []
    total_latencies = []
    retries = 0

    for case in cases:
        q = case["question"]
        print(f"\n--- Running {case['id']}: '{q}' ---")
        start_time = time.time()
        
        # 1. Retrieval
        retrieval_start = time.time()
        retrieved = retrieve_chunks(q, processed_policy.chunks, top_k=settings.retrieval_top_k)
        retrieval_ms = int((time.time() - retrieval_start) * 1000)
        retrieval_latencies.append(retrieval_ms)
        
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
                    retries += 1
                    print(" -> Rate limit hit, cooling down 10s and retrying...")
                    time.sleep(10.0)
                    ans_result = policy_service.ask_question(processed_policy, q)
                else:
                    raise first_exc
            model_ms = int((time.time() - model_start) * 1000)
            total_latency_ms = int((time.time() - start_time) * 1000)
            model_latencies.append(model_ms)
            total_latencies.append(total_latency_ms)
            
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

        citation_support_verified = citations_valid and (len(citations_info) > 0 or verdict == "not_stated")
        unsupported_material_claim = not citations_valid if verdict in ["covered", "excluded", "depends"] else False

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
            "unsupported_material_claim": unsupported_material_claim,
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
        print(f" -> Governing Pages: {retrieved_pages} vs Exp: {case['governing_pages']} | Hit: {retrieval_hit} | Full Hit: {full_retrieval_hit}")
        print(f" -> Verdict: {verdict} (Expected: {case['expected_verdict']}) | Match: {verdict == case['expected_verdict']}")
        print(f" -> Citations Valid: {citations_valid} | Citations Count: {len(citations_info)}")
        print(f" -> Latency: Retrieval {retrieval_ms}ms | Model {model_ms}ms | Total {total_latency_ms}ms")

    # Metrics
    total = len(results)
    retrieval_success_count = sum(1 for r in results if r["governing_clause_found"])
    full_retrieval_success_count = sum(1 for r in results if r["all_governing_clauses_found"])
    verdict_matches = sum(1 for r in results if r["verdict_match"])
    citations_valid_count = sum(1 for r in results if r["citations_valid"])
    correct_abstentions = sum(1 for r in results if r["expected_verdict"] == "not_stated" and r["verdict"] == "not_stated")
    negative_cases = sum(1 for r in results if r["expected_verdict"] == "not_stated")
    unsupported_claims_count = sum(1 for r in results if r["unsupported_material_claim"])

    return {
        "suite_name": suite_name,
        "total_cases": total,
        "governing_clause_retrieval_rate": f"{retrieval_success_count}/{total} ({retrieval_success_count/total*100:.1f}%)",
        "all_governing_clauses_retrieval_rate": f"{full_retrieval_success_count}/{total} ({full_retrieval_success_count/total*100:.1f}%)",
        "verdict_accuracy_rate": f"{verdict_matches}/{total} ({verdict_matches/total*100:.1f}%)",
        "citations_valid_rate": f"{citations_valid_count}/{total} ({citations_valid_count/total*100:.1f}%)",
        "unsupported_material_claim_rate": f"{unsupported_claims_count}/{total} ({unsupported_claims_count/total*100:.1f}%)",
        "correct_abstention_rate": f"{correct_abstentions}/{negative_cases} ({correct_abstentions/negative_cases*100:.1f}%)" if negative_cases else "N/A",
        "retrieval_latency_p50_ms": int(np.percentile(retrieval_latencies, 50)) if retrieval_latencies else 0,
        "retrieval_latency_p95_ms": int(np.percentile(retrieval_latencies, 95)) if retrieval_latencies else 0,
        "model_latency_p50_ms": int(np.percentile(model_latencies, 50)) if model_latencies else 0,
        "model_latency_p95_ms": int(np.percentile(model_latencies, 95)) if model_latencies else 0,
        "total_latency_p50_ms": int(np.percentile(total_latencies, 50)) if total_latencies else 0,
        "total_latency_p95_ms": int(np.percentile(total_latencies, 95)) if total_latencies else 0,
        "api_retries": retries,
        "cases": results
    }

# Run both suites
benchmark_report = evaluate_case_list(ORIGINAL_BENCHMARK, "Original Benchmark Set (9 Cases)")
heldout_report = evaluate_case_list(HELDOUT_CHALLENGE_SET, "Held-Out Challenge Set (10 Unseen Cases)")

full_report = {
    "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "stage": "Stage 2.1 — Held-Out Reliability & Citation Audit",
    "git_commit": "519ef4acd8f920fce999f25d11ff2520cc2adffa",
    "pdf_file": PDF_PATH,
    "pdf_sha256": pdf_sha256,
    "model": settings.groq_model,
    "top_k": settings.retrieval_top_k,
    "original_benchmark": benchmark_report,
    "heldout_challenge_set": heldout_report
}

output_path = os.path.join(ARTIFACT_DIR, "qa_stage2_1_evaluation_report.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(full_report, f, indent=2)

print("\n" + "="*70)
print("STAGE 2.1 EVALUATION COMPLETE")
print(f"Report saved to: {output_path}")
print(f"Original Benchmark Verdict Accuracy: {benchmark_report['verdict_accuracy_rate']}")
print(f"Held-Out Challenge Verdict Accuracy: {heldout_report['verdict_accuracy_rate']}")
print(f"Held-Out Citations Valid: {heldout_report['citations_valid_rate']}")
print(f"Held-Out Abstention Rate: {heldout_report['correct_abstention_rate']}")
print(f"Retrieval Latency p50: {heldout_report['retrieval_latency_p50_ms']}ms | p95: {heldout_report['retrieval_latency_p95_ms']}ms")
print(f"Model Latency p50: {heldout_report['model_latency_p50_ms']}ms | p95: {heldout_report['model_latency_p95_ms']}ms")
print("="*70)
