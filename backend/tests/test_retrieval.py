from app.retrieval import bm25_scores_from_tokens, hybrid_rerank_score, tokenize


def test_bm25_scores_rank_exact_rare_term_match():
    documents = [
        tokenize("a general discussion about engines"),
        tokenize("ZX-81 rotor torque specification"),
    ]

    scores = bm25_scores_from_tokens(
        tokenize("ZX-81 rotor torque"), documents
    )

    assert scores[1] > scores[0]


def test_hybrid_reranker_can_promote_lexical_match():
    exact_match = hybrid_rerank_score(0.40, 2.0, 2.0)
    dense_match = hybrid_rerank_score(0.52, 0.0, 2.0)

    assert exact_match > dense_match


def test_bm25_returns_zero_for_empty_or_unmatched_query():
    documents = [tokenize("the blue notebook")]

    assert bm25_scores_from_tokens([], documents) == [0.0]
    assert bm25_scores_from_tokens(tokenize("orange"), documents) == [0.0]
