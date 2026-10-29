"""Hybrid lexical and insurance-concept retrieval over page-scoped chunks.

Ranking combines:
* IDF-weighted term frequency (rare terms are more informative),
* adjacent-phrase and bigram proximity bonuses,
* coverage bonuses for matching distinct query terms,
* conservative insurance-concept expansion hints (discounted weight = 0.35)
  to bridge layperson phrasing to policy wording without assuming legal equivalence,
* page-level diversity to prevent a single repetitive page from crowding out
  disjoint governing clauses (e.g. benefit schedule vs waiting periods vs exclusions).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re

from backend.document_processing.chunker import PolicyChunk
from backend.document_processing.normalization import search_text

_TOKEN_RE = re.compile(r"[a-z0-9]+")

STOP_WORDS = frozenset(
    """
    a an and are as at be been being but by can could did do does for from had
    has have he her here him his how i if in into is it its me my no nor not of
    on or our ours out over she should so some such than that the their theirs
    them then there these they this those through to under until up was we were
    what when where which while who whom why will with would you your yours
    """.split()
)

# Conservative insurance retrieval hints (General insurance terminology)
# Expansion terms are retrieval hints ONLY to locate candidate evidence;
# they never establish legal equivalence or coverage.
INSURANCE_CONCEPT_EXPANSIONS = {
    # Illness & Initial Waiting Clocks
    "food poisoning": ["illness", "initial", "waiting", "period", "30", "days"],
    "poisoning": ["illness", "initial", "waiting", "period", "30", "days"],
    "fever": ["illness", "initial", "waiting", "period", "30", "days"],
    "infection": ["illness", "initial", "waiting", "period", "30", "days"],
    "first 2 weeks": ["initial", "waiting", "period", "30", "days", "commencement"],
    "two weeks": ["initial", "waiting", "period", "30", "days"],
    "first month": ["initial", "waiting", "period", "30", "days"],

    # Day Care, Surgical & Specific Ailments
    "keyhole": ["day", "care", "daycare", "procedure", "surgical", "specified"],
    "keyhole surgery": ["day", "care", "daycare", "procedure", "surgical", "specified"],
    "joint pain": ["specified", "disease", "procedure", "waiting", "period", "joint"],
    "knee surgery": ["joint", "replacement", "specified", "disease", "procedure", "24", "months"],
    "cataract": ["cataract", "ophthalmic", "eye", "lens", "specified", "disease", "24", "months"],

    # Co-Payment & Age Tiers
    "father": ["age", "entry", "senior", "co-payment", "copay", "61"],
    "mother": ["age", "entry", "senior", "co-payment", "copay", "61"],
    "62": ["61", "age", "entry", "co-payment", "copay"],
    "senior": ["co-payment", "copay", "entry", "age", "61"],

    # Pre-Existing Disease & Buy-Back / Reduction
    "pre-existing": ["ped", "waiting", "period", "buy", "back", "reduction", "12", "months"],
    "reduce": ["buy", "back", "reduction", "optional", "cover"],
    "reduced": ["buy", "back", "reduction", "optional", "cover"],

    # Bariatric & Cosmetic
    "weight loss": ["bariatric", "surgery", "obesity", "cosmetic", "exclusion"],
    "bariatric": ["bariatric", "surgery", "hospitalization", "waiting", "period", "36", "months"],
}


@dataclass(frozen=True)
class RetrievedChunk:
    """A ranked chunk. ``text`` is always the original, unmodified source."""

    chunk_id: str
    page_number: int
    text: str
    score: float
    matched_terms: tuple[str, ...]


def _normalise_term(term: str) -> str:
    """Very small plural normalizer; deliberately not a stemmer."""
    if len(term) > 4 and term.endswith("ies"):
        return term[:-3] + "y"
    if (
        len(term) > 3
        and term.endswith("s")
        and not term.endswith(("ss", "us", "is"))
    ):
        return term[:-1]
    return term


def _tokens(text: str) -> list[str]:
    """Tokenize, drop stop words first, then apply the tiny plural normalizer."""
    return [
        _normalise_term(token)
        for token in _TOKEN_RE.findall(search_text(text))
        if token not in STOP_WORDS
    ]


def extract_query_terms(question: str) -> list[str]:
    """Return unique meaningful terms in question order."""
    if not question or not question.strip():
        return []
    terms: list[str] = []
    for token in _tokens(question):
        if len(token) < 2 or token in STOP_WORDS:
            continue
        if token not in terms:
            terms.append(token)
    return terms


def retrieve_chunks(
    question: str,
    chunks: list[PolicyChunk] | tuple[PolicyChunk, ...],
    *,
    top_k: int = 5,
    min_score: float = 0.0,
    max_per_page: int = 2,
) -> list[RetrievedChunk]:
    """Rank chunks by hybrid lexical relevance and insurance concept hints.

    The score combines:
    * Primary lexical terms (IDF-weighted term frequency with coverage & phrase bonus),
    * Conservative insurance concept retrieval hints (discounted weight = 0.35),
    * Diversified page allocation to prevent repetitive sections from crowding out
      disjoint governing clauses.

    Returns an empty list for an empty question, an empty document, or a query
    that matches no meaningful terms. Ranking is deterministic: ties break by
    page number and then chunk ID.
    """
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    if not chunks:
        return []

    raw_query_terms = extract_query_terms(question)
    if not raw_query_terms:
        return []

    # Conservative concept expansion
    q_lower = question.lower()
    expansion_terms: list[str] = []
    for phrase, hints in INSURANCE_CONCEPT_EXPANSIONS.items():
        if phrase in q_lower:
            for h in hints:
                norm_h = _normalise_term(h.lower())
                if (
                    norm_h not in raw_query_terms
                    and norm_h not in expansion_terms
                    and norm_h not in STOP_WORDS
                ):
                    expansion_terms.append(norm_h)

    prepared: list[tuple[PolicyChunk, str, Counter[str]]] = []
    for chunk in chunks:
        text = search_text(chunk.text)
        prepared.append((chunk, text, Counter(_tokens(chunk.text))))

    total_chunks = len(prepared)

    # Compute IDF for all query + expansion terms
    all_terms = list(dict.fromkeys(raw_query_terms + expansion_terms))
    idf: dict[str, float] = {}
    for term in all_terms:
        document_frequency = sum(
            1 for _, _, counts in prepared if counts.get(term, 0) > 0
        )
        idf[term] = math.log((total_chunks + 1) / (document_frequency + 1)) + 1.0

    phrase_pairs = list(zip(raw_query_terms, raw_query_terms[1:]))
    ranked: list[RetrievedChunk] = []

    for chunk, text, counts in prepared:
        matched_raw = [term for term in raw_query_terms if counts.get(term, 0) > 0]
        matched_exp = [term for term in expansion_terms if counts.get(term, 0) > 0]

        if not matched_raw and not matched_exp:
            continue

        score = 0.0

        # 1. Primary Lexical Scoring (Full Weight = 1.0)
        for term in matched_raw:
            score += 1.0 * idf[term] * (1.0 + math.log(counts[term]))
        if raw_query_terms:
            score += 0.5 * (len(matched_raw) / len(raw_query_terms))

        # 2. Adjacent Phrase Proximity Bonus (Full Weight = 0.75)
        padded = f" {text} "
        for left, right in phrase_pairs:
            if left in matched_raw and right in matched_raw:
                if f" {left} {right} " in padded:
                    score += 0.75 * ((idf[left] + idf[right]) / 2.0)

        # 3. Conservative Concept Expansion Scoring (Discounted Weight = 0.35)
        for term in matched_exp:
            score += 0.35 * idf[term] * (1.0 + math.log(counts[term]))

        if score <= min_score:
            continue

        all_matched = list(dict.fromkeys(matched_raw + matched_exp))
        ranked.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                page_number=chunk.page_number,
                text=chunk.text,
                score=round(score, 6),
                matched_terms=tuple(all_matched),
            )
        )

    # Deterministic sort: descending by score, tie-break by page_number, chunk_id
    ranked.sort(key=lambda item: (-item.score, item.page_number, item.chunk_id))

    # Page Diversity: Prevent any single page from occupying more than max_per_page slots
    diversified: list[RetrievedChunk] = []
    page_counts: Counter[int] = Counter()
    overflow: list[RetrievedChunk] = []

    for item in ranked:
        if page_counts[item.page_number] < max_per_page:
            diversified.append(item)
            page_counts[item.page_number] += 1
        else:
            overflow.append(item)
        if len(diversified) == top_k:
            break

    # If diverse selection didn't fill top_k, fill from overflow
    if len(diversified) < top_k:
        for item in overflow:
            diversified.append(item)
            if len(diversified) == top_k:
                break

    return diversified
