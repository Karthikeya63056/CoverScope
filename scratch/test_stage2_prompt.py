import os
import sys
import re

sys.path.insert(0, os.path.abspath("."))

from backend.qa.schemas import Citation
from backend.qa.retrieval import RetrievedChunk

_STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it", "its",
    "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no",
    "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "should",
    "shouldn't", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
    "were", "weren't", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "won't", "would", "wouldn't", "you", "your", "yours", "yourself",
    "yourselves"
})

_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "maternity_newborn": {"maternity", "delivery", "new born", "newborn", "infant", "obstetric"},
    "bariatric": {"bariatric", "weight loss", "obesity", "metabolic"},
    "dental": {"dental", "denture", "teeth", "tooth", "oral"},
    "ophthalmic": {"cataract", "ophthalmic", "eye", "lens"},
    "ayush": {"ayush", "ayurveda", "homeopathy", "unani", "siddha", "yoga", "naturopathy"},
    "motor": {"vehicle", "car", "motor", "repair", "traffic"},
}

def check_citation_relevance(quote: str, question: str | None, answer: str | None) -> str | None:
    if not question and not answer:
        return None
    context_text = f"{question or ''} {answer or ''}".lower()
    quote_lower = quote.lower()

    # 1. Specialized Domain Mismatch
    for domain, terms in _DOMAIN_KEYWORDS.items():
        quote_has_domain = any(t in quote_lower for t in terms)
        if quote_has_domain:
            context_has_domain = any(t in context_text for t in terms)
            if not context_has_domain:
                return f"Quotation pertains to {domain} which is not relevant to the question or answer claim."

    # 2. Token Overlap Check
    q_tokens = {w for w in re.findall(r"\w+", quote_lower) if w not in _STOPWORDS and (len(w) >= 3 or w.isdigit())}
    ctx_tokens = {w for w in re.findall(r"\w+", context_text) if w not in _STOPWORDS and (len(w) >= 3 or w.isdigit())}
    if len(q_tokens) >= 2 and len(q_tokens & ctx_tokens) == 0:
        return "Quotation does not share topical relevance with the claim or question."

    return None

# Test scenarios
print("TC-6 Turn 2 test (bariatric follow-up):")
q = "What is the waiting period for that?"
ans = "The waiting period is 24 months."
quote_bad = "Delivery Expenses and New Born: 24 months"
print("Bad quote check:", check_citation_relevance(quote_bad, q, ans))

quote_good = "Bariatric Surgery: 36 months"
q2 = "What is the waiting period for bariatric surgery?"
ans2 = "The waiting period for bariatric surgery is 36 months."
print("Good quote check:", check_citation_relevance(quote_good, q2, ans2))

# TC-2 test
q_tc2 = "Will the policy pay if I get admitted for food poisoning in the first 2 weeks?"
ans_tc2 = "No. The policy has an initial waiting period of 30 days, so a hospitalization for food poisoning within the first two weeks is not payable."
quote_tc2 = "Initial Waiting Period: 30 days"
print("TC-2 quote check:", check_citation_relevance(quote_tc2, q_tc2, ans_tc2))

