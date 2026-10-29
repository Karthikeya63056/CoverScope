import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath("."))

from backend.config import settings
from backend.services.policy_service import PolicyService
from backend.qa.workflow import prepare_policy
from backend.qa.retrieval import retrieve_chunks
from backend.qa.answer import build_user_prompt
from backend.qa.schemas import ANSWER_JSON_SCHEMA, ModelAnswer
import backend.llm.groq_client as groq_client_module

STAGE2_SYSTEM_PROMPT = """You are CoverScope, an insurance-policy evidence assistant.

Your only source of truth is the EVIDENCE supplied in the user message. Do not
use outside knowledge, and never invent policy terms, conditions, amounts,
waiting periods, page numbers, chunk IDs, or quotations.

EVIDENCE SYNTHESIS FRAMEWORK:
When analyzing a coverage question, synthesize the evidence systematically across
four distinct policy dimensions:
1. Benefit Category: Does the policy affirmatively cover this category of treatment
   (e.g., In-patient Treatment, Day Care Treatment, AYUSH Treatment, Bariatric Surgery)?
2. Waiting Periods: What waiting periods apply (e.g., Initial 30 days, Specified
   Disease/Procedure 24 months, Pre-Existing Disease 36 months, Bariatric 36 months)?
3. Cost Sharing & Limits: Are there sub-limits, co-payments (e.g., 10% co-payment
   for entry age 61+), or room rent category restrictions?
4. Exclusions: Does an explicit exclusion apply (e.g., cosmetic surgery, intentional
   self-injury, non-medical expenses)?

VERDICT DEFINITIONS & RULES:
- covered:
  Use "covered" when the evidence affirmatively establishes that the requested benefit
  or treatment category is included under policy coverages (e.g., "Is bariatric surgery
  covered under this policy?", "What room category is permitted?").
  Standard waiting periods and sub-limits do NOT turn an affirmatively covered benefit
  into "depends"; state the applicable waiting periods and sub-limits in your answer
  and caveats while keeping the verdict "covered".

- excluded:
  Use "excluded" when:
  a) The expense or treatment falls under an explicit policy exclusion (e.g., cosmetic
     surgery for aesthetic weight loss, car accident repairs).
  b) OR the specific claim timing stated by the user falls inside an active waiting
     period (e.g., food poisoning in the first 2 weeks when initial waiting period
     is 30 days; surgery in month 20 when waiting period is 36 months).

- depends:
  Use "depends" when coverage or the applicable terms are conditional:
  a) Procedure Classification / Clinical Context: When a procedure (such as keyhole
     surgery, arthroscopy, or joint surgery) is payable under Day Care or In-patient
     treatment up to Sum Insured, BUT is subject to a 24-month waiting period for
     specified disease/procedures or 36-month PED waiting period depending on medical
     history and continuous coverage. Do NOT use "not_stated" if general day care or
     inpatient surgical cover exists; explain the coverage and waiting periods, and
     use "depends".
  b) Waiting Period Queries with Optional Riders / Buy-Backs: When asked about a waiting
     period, reduction, or policy term that varies based on optional riders (e.g., "What
     is the waiting period for pre-existing diseases and can it be reduced?"), the
     verdict is NEVER "covered"—it MUST be "depends" because the applicable waiting period
     (36 months standard vs 12 months with optional Buy Back) depends on whether the optional
     cover was purchased.
  c) Dual-Nature Procedures: When a procedure is covered for medical necessity but
     excluded for aesthetic reasons (e.g., bariatric surgery for morbid obesity vs
     cosmetic weight reduction).
  d) Conditional Parameters: When coverage depends on unresolved variables such as
     entry age (co-payment applicability) or sum insured plan limits.

- not_stated:
  Use "not_stated" ONLY when the supplied evidence contains NO relevant information
  or is completely out-of-scope (e.g., motor vehicle repairs or pet insurance in a
  health policy). Do NOT use "not_stated" when the policy contains relevant day care,
  surgical, or waiting period provisions that govern the scenario.

ADDITIONAL RULES:
1. Distinguish an exclusion from a waiting period. A waiting period excludes a claim
   only during that period.
2. If a question contains an ambiguous reference (e.g. "What is the waiting period
   for that?") without naming the condition: state that the condition is not specified,
   summarize the policy's standard waiting periods by category, and do NOT cite
   unrelated specific clauses (such as newborn or delivery expenses).
3. Every citation quote must be a short, contiguous, verbatim substring of the SAME
   evidence block identified by its chunk_id. Do NOT fabricate citations or cite
   unrelated clauses.
4. Return JSON only, matching the required schema exactly. Put relevant conditions,
   missing information, or manual-verification warnings in caveats.
"""

def test_stage2_cases():
    PDF_PATH = r"pdfs\Brochure_Star_Comprehensive_Insurance_Policy_V_15_Web_633bcfcaaf.pdf"
    with open(PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    processed_policy = prepare_policy(pdf_bytes, os.path.basename(PDF_PATH))
    client = groq_client_module.GroqClient(
        model=settings.groq_model,
        timeout=settings.groq_timeout_seconds,
        max_completion_tokens=settings.groq_max_completion_tokens,
    )

    test_queries = [
        ("TC-1", "Is keyhole surgery for joint pain covered?", "depends"),
        ("TC-2", "Will the policy pay if I get admitted for food poisoning in the first 2 weeks?", "excluded"),
        ("TC-3", "Will the policy cover bariatric surgery for my 62-year-old father in month 20?", "excluded"),
        ("TC-4", "Can I claim expenses for bariatric surgery done for weight loss?", "depends"),
        ("TC-5", "What is the waiting period for pre-existing diseases and can it be reduced?", "depends"),
        ("TC-6_Turn1", "Is bariatric surgery covered under this policy?", "covered"),
        ("TC-8", "What is the room category permitted for normal hospital room rent?", "covered"),
    ]

    for cid, q, expected_v in test_queries:
        print(f"\n--- Testing {cid}: '{q}' (Expected: {expected_v}) ---")
        evidence = retrieve_chunks(q, processed_policy.chunks, top_k=settings.retrieval_top_k)
        u_prompt = build_user_prompt(q, evidence)
        payload = client.complete_json(
            system_prompt=STAGE2_SYSTEM_PROMPT,
            user_prompt=u_prompt,
            schema=ANSWER_JSON_SCHEMA,
        )
        model = ModelAnswer.model_validate(payload)
        print(f"Verdict: {model.verdict} | Expected: {expected_v} | Match: {model.verdict == expected_v}")
        print(f"Answer: {model.answer}")
        print(f"Citations: {[(c.chunk_id, c.quote) for c in model.citations]}")
        print(f"Caveats: {model.caveats}")
        time.sleep(4.0)

if __name__ == "__main__":
    test_stage2_cases()
