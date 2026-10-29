"""Request intent classification and multi-category policy summary routing.

Distinguishes between:
* Specific coverage questions ("Is my surgery covered?")
* General policy overviews ("What does my policy cover?")
* Exclusion summaries ("What does my policy exclude?")
* Clause explanations ("Explain the waiting period for pre-existing diseases")
* General educational advice ("How should I choose health insurance?")
* Conversational greetings ("hi", "hello")
"""
from __future__ import annotations

from enum import Enum
import re
from typing import Sequence

from backend.document_processing.chunker import PolicyChunk
from backend.qa.retrieval import retrieve_chunks
from backend.qa.schemas import Verdict


class RequestIntent(str, Enum):
    GREETING = "greeting"
    GENERAL_EDUCATION = "general_education"
    POLICY_SUMMARY = "policy_summary"
    EXCLUSION_SUMMARY = "exclusion_summary"
    CLAUSE_EXPLANATION = "clause_explanation"
    SPECIFIC_COVERAGE = "specific_coverage"


_GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "heya",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "howdy",
    "sup",
    "whats up",
    "what's up",
    "who are you",
    "what can you do",
    "help",
    "start",
}


def classify_intent(question: str) -> RequestIntent:
    """Classify user query into distinct operational intents."""
    if not question or not question.strip():
        return RequestIntent.SPECIFIC_COVERAGE

    q_clean = re.sub(r"[^\w\s]", "", question.strip().lower()).strip()
    q_lower = question.lower()

    # 1. Conversational Greeting & Assistant Introduction
    intro_patterns = [
        r"\b(?:tell\s+me\s+about\s+yourself|who\s+are\s+you|what\s+are\s+you|introduce\s+yourself)\b",
        r"\b(?:what\s+(?:can|do)\s+you\s+do|how\s+(?:can|do)\s+you\s+help(?:\s+me)?)\b",
        r"\b(?:what\s+is\s+coverscope|about\s+coverscope|how\s+do\s+you\s+work)\b",
    ]
    if q_clean in _GREETING_WORDS or any(re.search(p, q_lower) for p in intro_patterns):
        return RequestIntent.GREETING

    tokens = q_clean.split()
    if any(t in {"hi", "hello", "hey", "heya", "greetings"} for t in tokens):
        insurance_terms = {
            "cover", "covered", "policy", "claim", "wait", "limit", "room",
            "disease", "ped", "cash", "pay", "deduct", "cataract",
            "surgery", "hospital", "ayush", "dental", "icu",
        }
        if not any(t in insurance_terms for t in tokens):
            return RequestIntent.GREETING

    # 2. General Health Insurance Education
    # Queries asking how to select, buy, compare, or choose insurance in general,
    # distinct from queries evaluating the specific uploaded document.
    edu_patterns = [
        r"\b(?:how\s+(?:should|do|to|can)\s+(?:i\s+)?(?:choose|pick|select|buy|evaluate))\b",
        r"\b(?:what\s+to\s+look\s+for\s+when\s+(?:buying|choosing|selecting))\b",
        r"\b(?:tips\s+(?:for|on)\s+(?:buying|choosing|selecting)\s+health\s+insurance)\b",
        r"\b(?:how\s+much\s+health\s+insurance\s+(?:do\s+i|should\s+i)\s+(?:need|buy))\b",
        r"\b(?:what\s+is\s+health\s+insurance|why\s+(?:do\s+i\s+need|buy)\s+health\s+insurance)\b",
        r"\b(?:difference\s+between\s+(?:individual|floater|super\s*top[- ]*up))\b",
    ]
    if any(re.search(p, q_lower) for p in edu_patterns):
        # Ensure it is not an inquiry about "this policy"
        if not re.search(r"\b(?:this|my|our|the\s+uploaded)\s+policy\b", q_lower):
            return RequestIntent.GENERAL_EDUCATION

    # 3. Policy Exclusion Summary
    exclusion_patterns = [
        r"\b(?:what\s+does\s+(?:my|this|the)\s+policy\s+exclude)\b",
        r"\b(?:what\s+is\s+(?:not\s+covered|excluded)\s+(?:under|in)\s+(?:this|my|the)\s+policy)\b",
        r"\b(?:list\s+(?:all\s+)?exclusions|exclusions\s+summary|major\s+exclusions)\b",
        r"\b(?:what\s+are\s+the\s+exclusions)\b",
    ]
    if any(re.search(p, q_lower) for p in exclusion_patterns):
        return RequestIntent.EXCLUSION_SUMMARY

    # 4. Broad Policy Coverage Summary
    summary_patterns = [
        r"\b(?:what\s+does\s+(?:my|this|the)\s+policy\s+cover)\b",
        r"\b(?:what\s+is\s+covered\s+(?:under|in)\s+(?:this|my|the)\s+policy)\b",
        r"\b(?:overview\s+of\s+(?:the\s+|this\s+|my\s+)?policy|policy\s+overview)\b",
        r"\b(?:summarize\s+(?:my|this|the)\s+policy|policy\s+summary)\b",
        r"\b(?:what\s+are\s+the\s+(?:main\s+)?benefits\s+(?:of|in|under)\s+(?:this|my|the)\s+policy)\b",
        r"\b(?:key\s+features\s+of\s+(?:this|my|the)\s+policy)\b",
    ]
    if any(re.search(p, q_lower) for p in summary_patterns):
        return RequestIntent.POLICY_SUMMARY

    # 5. Clause Explanation
    explanation_patterns = [
        r"\b(?:explain\s+(?:the\s+)?(?:waiting\s+period|deductible|co-?payment|sublimit|cash\s+benefit))\b",
        r"\b(?:how\s+does\s+(?:the\s+)?(?:waiting\s+period|co-?payment|deductible|restoration)\s+work)\b",
        r"\b(?:what\s+is\s+the\s+meaning\s+of\s+(?:pre-existing|ped|co-?payment|deductible))\b",
    ]
    if any(re.search(p, q_lower) for p in explanation_patterns):
        return RequestIntent.CLAUSE_EXPLANATION

    return RequestIntent.SPECIFIC_COVERAGE


def handle_general_education(question: str) -> dict:
    """Provide authoritative health insurance buying and evaluation advice.

    Completely distinguished from specific findings about the uploaded policy.
    No document citations are fabricated or attached.
    """
    answer = (
        "### General Health Insurance Selection & Evaluation Framework\n\n"
        "When choosing or reviewing a health insurance plan, evaluate these critical factors:\n\n"
        "1. **Adequate Sum Insured & Room Rent Slabs**:\n"
        "   * Choose a base Sum Insured that matches tertiary treatment costs in your city (₹10L–₹25L recommended for metro families).\n"
        "   * **Room Rent Limit**: Opt for plans with 'No Room Rent Capping' or 'Single Private A/C Room'. Sublimits (e.g. 1% of SI) trigger proportional deductions on doctor fees, surgeries, and nursing charges.\n\n"
        "2. **Waiting Periods & Pre-Existing Diseases (PED)**:\n"
        "   * Review the standard waiting periods: 30 days initial, 24 months for specific diseases (cataract, hernia, joint replacements), and 36 to 48 months for PED.\n"
        "   * Look for reduction riders if you or family members have pre-existing conditions.\n\n"
        "3. **Co-Payment & Deductible Rules**:\n"
        "   * Avoid compulsory co-payments (e.g. 10%–20% senior citizen co-pay) unless necessary to lower premiums.\n"
        "   * Ensure hospital cash or surgical deductibles align with your out-of-pocket expectations.\n\n"
        "4. **Cashless Network & Claim Settlement Ratio (CSR)**:\n"
        "   * Verify that top hospitals in your vicinity have active cashless tie-ups with the insurer.\n"
        "   * Check the insurer's Incurred Claim Ratio (ICR, ideally 70%–90%) and Claim Settlement Ratio (>90%).\n\n"
        "5. **Day-Care & Advanced Modern Treatments**:\n"
        "   * Confirm that surgical procedures requiring less than 24 hours hospitalization (e.g. keyhole surgeries, chemotherapy, dialysis, robotic procedures) are covered up to full Sum Insured.\n\n"
        "6. **Restoration / Recharge Benefits**:\n"
        "   * Check if the policy restores 100% of the Sum Insured upon exhaustion for unrelated or subsequent illnesses within the same policy year."
    )
    caveats = [
        "Educational Guidance: The recommendations above are general insurance advisory principles.",
        "Document Distinction: These principles are not extracted from your uploaded policy document. To review binding coverage, inspect your policy wording.",
    ]
    return {
        "verdict": "not_stated",
        "answer": answer,
        "citations": [],
        "confidence": "high",
        "caveats": caveats,
        "citations_valid": True,
        "manual_review_required": False,
        "warnings": [],
    }


SUMMARY_CATEGORIES = [
    {
        "category_id": "hospitalization",
        "title": "1. Main In-Patient Hospitalization & Medical Expenses",
        "query": "hospitalization room rent board nursing ICU surgeon medical expenses fees",
        "keywords": ["hospitalization", "room rent", "icu", "nursing", "boarding", "surgeon"],
    },
    {
        "category_id": "day_care",
        "title": "2. Outpatient, Day-Care & Specified Treatments",
        "query": "day care daycare procedure outpatient pre post hospitalization ambulance modern",
        "keywords": ["day care", "daycare", "pre-hospitalization", "post-hospitalization", "ambulance", "modern"],
    },
    {
        "category_id": "waiting_periods",
        "title": "3. Waiting Periods & Pre-Existing Disease Clocks",
        "query": "waiting period initial 30 days pre-existing disease PED 24 months 36 months",
        "keywords": ["waiting period", "pre-existing", "ped", "30 days", "24 months", "36 months"],
    },
    {
        "category_id": "exclusions",
        "title": "4. Permanent Exclusions & Restricted Procedures",
        "query": "exclusions not covered excluded cosmetic self injury substance addiction",
        "keywords": ["exclusion", "exclusions", "not covered", "excluded", "permanent"],
    },
    {
        "category_id": "financial_limits",
        "title": "5. Deductibles, Co-Payments, Sublimits & Financial Caps",
        "query": "deductible co-payment copay sublimit cataract limit hospital cash cap",
        "keywords": ["deductible", "co-payment", "copay", "sublimit", "limit", "cap"],
    },
    {
        "category_id": "eligibility_claims",
        "title": "6. Eligibility, Entry Age & Claim Conditions",
        "query": "eligibility entry age adult dependent child cashless claim reimbursement intimation",
        "keywords": ["entry age", "dependent child", "eligibility", "cashless", "reimbursement", "intimation"],
    },
    {
        "category_id": "renewal_continuity",
        "title": "7. Renewal, Cumulative Bonus & Portability",
        "query": "renewal lifelong grace period cumulative bonus no claim bonus portability",
        "keywords": ["renewal", "grace period", "cumulative bonus", "portability", "lifelong"],
    },
]


def _is_unusable_fragment(text: str) -> bool:
    """Check if a fragment is merely a heading, incomplete bullet, or short phrase."""
    t = text.strip()
    if len(t) < 30:
        return True
    # Headings ending with colon (e.g. "Claims Procedure for Reimbursement:")
    if t.endswith(":"):
        return True
    # Section markers without verb/substance (e.g. "g) Cumulative Bonus", "1. Inpatient Care")
    if re.match(r"^(?:[a-z0-9ivx]+[\).:-]|section\s+[ivx\d]+[:.-]?)\s+[A-Z][a-zA-Z\s]{1,40}$", t, re.I):
        return True
    # Fragments ending abruptly in conjunction or preposition
    if re.search(r"\b(?:and|or|of|to|for|in|with|by|including|excluding|the|a|an)\s*$", t, re.I):
        return True
    # Does it have any operative clause verbs or rule words?
    operative_words = {
        "cover", "covered", "pay", "payable", "exceed", "limit", "sublimit", "period",
        "deduct", "deductible", "day", "days", "month", "months", "year", "years",
        "percent", "percentage", "expenses", "provided", "subject", "shall", "will",
        "eligible", "exclusion", "excluded", "waiting", "incurred", "hospitalization",
        "indemnify", "reimburse", "bonus", "discount", "claim", "claims", "treatment",
    }
    words = set(re.findall(r"\w+", t.lower()))
    if not (words & operative_words):
        return True
    return False


def _extract_substantive_clause(text: str, keywords: list[str]) -> tuple[str, str]:
    """Extract a complete, meaningful clause excerpt rather than isolated fragment.

    Returns (quote, status):
    status is 'supported', 'partial', or 'not_located'.
    """
    # 1. Normalize line wraps: join lines that break mid-sentence
    raw_lines = [l.strip() for l in text.split("\n") if l.strip()]
    normalized_lines: list[str] = []
    curr_line = ""
    for l in raw_lines:
        if not curr_line:
            curr_line = l
        elif curr_line.endswith((".", "!", "?", ";")) or re.match(r"^(?:[a-z0-9ivx]+[\).:-]|section|\d+\.)", l, re.I):
            normalized_lines.append(curr_line)
            curr_line = l
        else:
            curr_line = f"{curr_line} {l}"
    if curr_line:
        normalized_lines.append(curr_line)

    # 2. Split into sentences
    candidates: list[str] = []
    for line in normalized_lines:
        for s in re.split(r"(?<=[.!?])\s+", line):
            s_clean = s.strip()
            if len(s_clean) >= 20:
                candidates.append(s_clean)

    # 3. Look for complete substantive sentence containing keywords
    for s in candidates:
        s_lower = s.lower()
        if any(kw in s_lower for kw in keywords):
            if not _is_unusable_fragment(s):
                if len(s) > 350:
                    s = s[:347].rsplit(" ", 1)[0] + "..."
                return s, "supported"

    # 4. Fallback: check if we found a partial sentence or heading with keywords
    for s in candidates:
        s_lower = s.lower()
        if any(kw in s_lower for kw in keywords):
            return s, "partial"

    return "", "not_located"


def _extract_best_sentence(text: str, keywords: list[str]) -> str:
    """Extract a concise, verbatim sentence from chunk containing key terms."""
    quote, _ = _extract_substantive_clause(text, keywords)
    if quote:
        return quote
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        s_clean = s.strip()
        if 20 <= len(s_clean) <= 300 and any(kw in s_clean.lower() for kw in keywords):
            return s_clean
    return text[:200].strip()


def handle_policy_summary(chunks: Sequence[PolicyChunk]) -> dict:
    """Synthesize structured, evidence-grounded summary across 7 core categories.

    Distinguishes between substantively supported, partially supported, and
    unlocated categories. Headings alone do not count as substantive evidence.
    """
    sections: list[str] = []
    citations: list[dict] = []
    categories_supported = 0
    categories_partial = 0
    categories_not_located = 0

    for cat in SUMMARY_CATEGORIES:
        retrieved = retrieve_chunks(cat["query"], chunks, top_k=2)
        found_chunk: PolicyChunk | None = None
        extracted_quote = ""
        clause_status = "not_located"

        for item in retrieved:
            item_lower = item.text.lower()
            if any(kw in item_lower for kw in cat["keywords"]):
                q, status = _extract_substantive_clause(item.text, cat["keywords"])
                if status == "supported":
                    found_chunk = item
                    extracted_quote = q
                    clause_status = "supported"
                    break
                elif status == "partial" and clause_status != "supported":
                    found_chunk = item
                    extracted_quote = q
                    clause_status = "partial"

        if clause_status == "supported" and found_chunk and extracted_quote:
            categories_supported += 1
            citations.append({
                "chunk_id": found_chunk.chunk_id,
                "page_number": found_chunk.page_number,
                "quote": extracted_quote,
            })
            sections.append(
                f"### {cat['title']}\n"
                f"* **Document Finding**: \"{extracted_quote}\"\n"
                f"* *Source*: Page {found_chunk.page_number} ({found_chunk.chunk_id})"
            )
        elif clause_status == "partial" and found_chunk:
            categories_partial += 1
            sections.append(
                f"### {cat['title']}\n"
                f"* **Status**: *Partially referenced in policy (Page {found_chunk.page_number}), but complete conditions or limits are not detailed in this section.*"
            )
        else:
            categories_not_located += 1
            sections.append(
                f"### {cat['title']}\n"
                f"* **Status**: *Not explicitly located or specified in the extracted text of this document.*"
            )

    summary_text = (
        "## Policy Coverage & Conditions Summary\n\n"
        "Here is an evidence-grounded overview organized across the 7 standard policy categories:\n\n"
        + "\n\n".join(sections)
    )

    if categories_supported >= 4:
        confidence = "high"
        citations_valid = True
        manual_review = False
    elif categories_supported >= 1:
        confidence = "medium"
        citations_valid = True
        manual_review = False
    else:
        confidence = "low"
        citations_valid = False
        manual_review = True

    caveats = [
        f"Multi-Category Synthesis: {categories_supported} of 7 categories substantively supported, "
        f"{categories_partial} partially referenced, {categories_not_located} not located in extracted text.",
        "Categories marked 'Not explicitly located' or 'Partially referenced' may be governed by policy schedules, add-ons, or omitted endorsements.",
        "Individual claim admissibility is strictly subject to the specific policy terms and sum insured schedule.",
    ]

    return {
        "verdict": "summary",
        "answer": summary_text,
        "citations": citations,
        "confidence": confidence,
        "caveats": caveats,
        "citations_valid": citations_valid,
        "manual_review_required": manual_review,
        "warnings": [],
    }


def handle_exclusion_summary(chunks: Sequence[PolicyChunk]) -> dict:
    """Synthesize evidence-grounded summary focusing on exclusions, waiting periods and caps."""
    exclusion_queries = [
        ("Permanent Exclusions", "permanent exclusions not covered cosmetic self injury substance war addiction", ["not covered", "excluded", "permanent exclusion"]),
        ("Waiting Period Exclusions", "waiting period initial 30 days pre-existing disease specified ailments 24 months 36 months", ["waiting period", "pre-existing", "30 days", "24 months"]),
        ("Deductibles & Non-Payable Caps", "deductible co-payment copay sublimit non-medical cataract limit", ["deductible", "co-payment", "sublimit", "limit"]),
    ]

    sections: list[str] = []
    citations: list[dict] = []

    for title, query, keywords in exclusion_queries:
        retrieved = retrieve_chunks(query, chunks, top_k=3)
        found_quotes: list[tuple[int, str, str]] = []

        for item in retrieved:
            item_lower = item.text.lower()
            if any(kw in item_lower for kw in keywords):
                quote = _extract_best_sentence(item.text, keywords)
                if quote and not any(q[2] == quote for q in found_quotes):
                    found_quotes.append((item.page_number, item.chunk_id, quote))
                    citations.append({
                        "chunk_id": item.chunk_id,
                        "page_number": item.page_number,
                        "quote": quote,
                    })

        if found_quotes:
            quote_lines = [
                f"* \"{q}\" — *Page {p} ({cid})*"
                for p, cid, q in found_quotes[:3]
            ]
            sections.append(f"### {title}\n" + "\n".join(quote_lines))
        else:
            sections.append(f"### {title}\n* *No explicit clauses located under this category.*")

    answer_text = (
        "## Policy Exclusions & Restrictions Summary\n\n"
        "Here are the governing exclusions, waiting periods, and restrictive conditions identified in your policy:\n\n"
        + "\n\n".join(sections)
    )

    caveats = [
        "Exclusion Grounding: Clauses are quoted verbatim from the extracted policy text.",
        "Check your policy schedule for any opted add-ons that may waive or buy back specific exclusions.",
    ]

    has_citations = len(citations) > 0
    confidence = "high" if len(citations) >= 3 else ("medium" if has_citations else "low")
    citations_valid = has_citations
    manual_review = not has_citations

    return {
        "verdict": "summary",
        "answer": answer_text,
        "citations": citations,
        "confidence": confidence,
        "caveats": caveats,
        "citations_valid": citations_valid,
        "manual_review_required": manual_review,
        "warnings": [],
    }

