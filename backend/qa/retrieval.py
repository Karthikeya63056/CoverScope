"""Deterministic lexical retrieval over the existing page-scoped chunks.

No embeddings, vector store, or external service is involved. Ranking is a
small, explainable TF-IDF variant with a coverage bonus and an adjacent-phrase
bonus. Common English stop words are removed so they cannot look like evidence.
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
    return [_normalise_term(token) for token in _TOKEN_RE.findall(search_text(text))]


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
) -> list[RetrievedChunk]:
    """Rank chunks by lexical relevance to ``question``.

    The score combines:

    * IDF-weighted term frequency (rare terms are more informative),
    * a coverage bonus for matching more distinct query terms,
    * a bonus when two adjacent query terms appear as a phrase.

    Returns an empty list for an empty question, an empty document, or a query
    that matches no meaningful terms. Ranking is deterministic: ties break by
    page number and then chunk ID.
    """
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    if not chunks:
        return []

    query_terms = extract_query_terms(question)
    if not query_terms:
        return []

    prepared: list[tuple[PolicyChunk, str, Counter[str]]] = []
    for chunk in chunks:
        text = search_text(chunk.text)
        prepared.append((chunk, text, Counter(_tokens(chunk.text))))

    total_chunks = len(prepared)
    idf: dict[str, float] = {}
    for term in query_terms:
        document_frequency = sum(
            1 for _, _, counts in prepared if counts.get(term, 0) > 0
        )
        idf[term] = math.log((total_chunks + 1) / (document_frequency + 1)) + 1.0

    phrase_pairs = list(zip(query_terms, query_terms[1:]))
    ranked: list[RetrievedChunk] = []
    for chunk, text, counts in prepared:
        matched = [term for term in query_terms if counts.get(term, 0) > 0]
        if not matched:
            continue

        score = 0.0
        for term in matched:
            score += idf[term] * (1.0 + math.log(counts[term]))
        score += 0.5 * (len(matched) / len(query_terms))

        padded = f" {text} "
        for left, right in phrase_pairs:
            if left not in matched or right not in matched:
                continue
            if f" {left} {right} " in padded:
                score += 0.75 * ((idf[left] + idf[right]) / 2.0)

        if score <= min_score:
            continue
        ranked.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                page_number=chunk.page_number,
                text=chunk.text,
                score=round(score, 6),
                matched_terms=tuple(matched),
            )
        )

    ranked.sort(key=lambda item: (-item.score, item.page_number, item.chunk_id))
    return ranked[:top_k]
