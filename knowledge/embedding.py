"""Dense embeddings for the corpus, computed locally with fastembed.

fastembed runs an ONNX model in-process, so no API key and no network call at query
time. The trade-off is the first run: the model weights are downloaded once into
``FASTEMBED_CACHE_DIR``, which docker-compose maps to a named volume so a rebuild does
not throw the download away.

The model is loaded lazily and kept for the life of the process — loading it per call
would dominate the cost of indexing.
"""

import logging
import os
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

#: e5-style models expect asymmetric prefixes; the multilingual MiniLM default does
#: not. Kept explicit so switching models is a settings change, not a code change.
QUERY_PREFIX = os.environ.get("EMBEDDING_QUERY_PREFIX", "")
PASSAGE_PREFIX = os.environ.get("EMBEDDING_PASSAGE_PREFIX", "")


class EmbeddingError(Exception):
    """Raised when the embedding model cannot be loaded or applied."""


@lru_cache(maxsize=1)
def get_model():
    """Return the shared embedding model, loading it on first use.

    Returns:
        TextEmbedding: The fastembed model configured in ``EMBEDDING_MODEL``.

    Raises:
        EmbeddingError: If fastembed is unavailable or the model cannot be loaded.
    """
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:  # pragma: no cover - dependência declarada no projeto
        raise EmbeddingError("fastembed não está instalado.") from exc

    logger.info("Carregando modelo de embedding %s", settings.EMBEDDING_MODEL)
    try:
        return TextEmbedding(model_name=settings.EMBEDDING_MODEL)
    except Exception as exc:
        raise EmbeddingError(
            f"Não foi possível carregar o modelo {settings.EMBEDDING_MODEL}: {exc}"
        ) from exc


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed document chunks for storage.

    Args:
        texts: Chunk texts, in order.

    Returns:
        list[list[float]]: One vector per chunk, in the same order.

    Raises:
        EmbeddingError: If the model fails to produce vectors.
    """
    return _embed([f"{PASSAGE_PREFIX}{text}" for text in texts])


def embed_query(text: str) -> list[float]:
    """Embed a single user question for retrieval.

    Args:
        text: The natural-language question.

    Returns:
        list[float]: The query vector.

    Raises:
        EmbeddingError: If the model fails to produce a vector.
    """
    return _embed([f"{QUERY_PREFIX}{text}"])[0]


def _embed(texts: list[str]) -> list[list[float]]:
    """Run the model over the given texts and validate the output shape.

    Raises:
        EmbeddingError: If embedding fails or the dimensionality does not match the
            schema, which would otherwise surface as an opaque database error.
    """
    if not texts:
        return []

    model = get_model()
    try:
        vectors = [list(map(float, vector)) for vector in model.embed(texts)]
    except Exception as exc:
        raise EmbeddingError(f"Falha ao gerar embeddings: {exc}") from exc

    expected = settings.EMBEDDING_DIMENSIONS
    for vector in vectors:
        if len(vector) != expected:
            raise EmbeddingError(
                f"O modelo {settings.EMBEDDING_MODEL} devolveu vetores de {len(vector)} "
                f"dimensões, mas o schema espera {expected}. Ajuste EMBEDDING_DIMENSIONS "
                f"e gere uma nova migration."
            )
    return vectors
