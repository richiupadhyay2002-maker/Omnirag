"""Sample API fixture for the OmniRAG eval harness (code retrieval)."""
import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns a float between -1 and 1 (1 = identical direction).
    Used in retrieval experiments before switching to Chroma distances.
    """
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def chunk_text(text: str, size: int = 1000, overlap: int = 120) -> list[str]:
    """Naive sliding-window splitter (fixture only, not production code)."""
    out = []
    step = max(1, size - overlap)
    for i in range(0, len(text), step):
        out.append(text[i:i + size])
    return out
