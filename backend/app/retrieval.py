"""Lightweight lexical scoring shared by retrieval and the evaluation harness."""
import math
import re

BM25_K1 = 1.5
BM25_B = 0.75
BM25_RERANK_WEIGHT = 0.15
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def bm25_scores_from_tokens(
    query_tokens: list[str],
    documents: list[list[str]],
) -> list[float]:
    if not documents or not query_tokens:
        return [0.0] * len(documents)

    document_frequencies: dict[str, int] = {}
    term_frequencies: list[dict[str, int]] = []
    for tokens in documents:
        frequencies: dict[str, int] = {}
        for token in tokens:
            frequencies[token] = frequencies.get(token, 0) + 1
        term_frequencies.append(frequencies)
        for token in frequencies:
            document_frequencies[token] = document_frequencies.get(token, 0) + 1

    corpus_size = len(documents)
    average_length = sum(map(len, documents)) / corpus_size
    if average_length == 0:
        return [0.0] * corpus_size

    scores = []
    for tokens, frequencies in zip(documents, term_frequencies):
        score = 0.0
        for token in dict.fromkeys(query_tokens):
            frequency = frequencies.get(token, 0)
            if not frequency:
                continue
            doc_frequency = document_frequencies[token]
            inverse_frequency = math.log(
                1 + (corpus_size - doc_frequency + 0.5) / (doc_frequency + 0.5)
            )
            denominator = frequency + BM25_K1 * (
                1 - BM25_B + BM25_B * len(tokens) / average_length
            )
            score += inverse_frequency * (
                frequency * (BM25_K1 + 1) / denominator
            )
        scores.append(score)
    return scores


def hybrid_rerank_score(
    dense_score: float,
    bm25_score: float,
    max_bm25: float,
) -> float:
    lexical_boost = (
        BM25_RERANK_WEIGHT * bm25_score / max_bm25 if max_bm25 else 0.0
    )
    return dense_score + lexical_boost
