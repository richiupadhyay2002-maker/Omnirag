"""
Local, free embedding model via sentence-transformers. No API key, no cost,
runs entirely on CPU (GPU used automatically if available).
"""
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from app.config import settings


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(settings.EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
