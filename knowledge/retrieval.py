"""Retrieval over the indexed corpus.

Two strategies, combined:

* **Semantic** — cosine distance over the embeddings, via the pgvector HNSW index.
  Finds passages that mean the same thing as the question even when they share no
  vocabulary with it.
* **Lexical** — PostgreSQL full-text search over ``search_vector``, using the
  Portuguese dictionary. Finds exact terms the embedding may gloss over: an article
  number, an institution's name, a specific amount.

Neither alone is enough for this corpus. A question like "quais instituições cobram
taxa?" needs the semantic side to match paraphrases of charging, and the lexical side
to anchor on the word "taxa" where it appears verbatim. The two rankings are merged
with Reciprocal Rank Fusion, which combines orderings without needing the scores to be
on a comparable scale.
"""

import logging
from dataclasses import dataclass

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from pgvector.django import CosineDistance

from knowledge.embedding import embed_query
from knowledge.models import DocumentChunk

logger = logging.getLogger(__name__)

SEARCH_CONFIG = "portuguese"

#: Constante do Reciprocal Rank Fusion. 60 é o valor do artigo original (Cormack et
#: al., 2009) e amortece o peso das primeiras posições, evitando que uma única lista
#: domine o resultado.
RRF_K = 60

#: Quantos candidatos cada estratégia traz antes da fusão. Um pool maior que o top-k
#: final dá à fusão margem para promover um trecho bem posicionado em apenas uma delas.
CANDIDATE_POOL = 20


@dataclass(frozen=True)
class RetrievedChunk:
    """A passage retrieved for a question, with its provenance."""

    chunk_id: int
    text: str
    document_title: str
    institution: str
    source_url: str
    file_name: str
    score: float

    @property
    def citation(self) -> str:
        """Return a short human-readable reference to the source."""
        return f"{self.institution} — {self.document_title}"


def search(question: str, top_k: int | None = None, *, hybrid: bool = True):
    """Retrieve the passages most relevant to a question.

    Args:
        question: Natural-language question.
        top_k: How many passages to return. Defaults to ``RAG_TOP_K``.
        hybrid: When False, uses semantic search only. Useful for comparing the two
            strategies in the technical report.

    Returns:
        list[RetrievedChunk]: Passages ordered by relevance, best first.
    """
    top_k = top_k or settings.RAG_TOP_K

    semantic = _semantic_search(question, CANDIDATE_POOL)
    if not hybrid:
        return [_to_retrieved(chunk, 1.0 / (index + 1)) for index, chunk in enumerate(semantic)]

    lexical = _lexical_search(question, CANDIDATE_POOL)
    return _fuse(semantic, lexical, top_k)


def _semantic_search(question: str, limit: int) -> list[DocumentChunk]:
    """Rank chunks by cosine distance to the question embedding."""
    vector = embed_query(question)
    return list(
        DocumentChunk.objects.select_related("document")
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance")[:limit]
    )


def _lexical_search(question: str, limit: int) -> list[DocumentChunk]:
    """Rank chunks by full-text relevance to the question."""
    query = SearchQuery(question, config=SEARCH_CONFIG, search_type="websearch")
    return list(
        DocumentChunk.objects.select_related("document")
        .filter(search_vector=query)
        .annotate(rank=SearchRank("search_vector", query))
        .order_by("-rank")[:limit]
    )


def _fuse(semantic: list[DocumentChunk], lexical: list[DocumentChunk], top_k: int):
    """Merge two rankings with Reciprocal Rank Fusion.

    Each list contributes ``1 / (k + position)`` to a chunk's score, so a passage that
    appears in both rankings outranks one that appears high in only a single list.

    Args:
        semantic: Chunks ordered by embedding similarity.
        lexical: Chunks ordered by full-text rank.
        top_k: How many results to keep.

    Returns:
        list[RetrievedChunk]: The fused ranking.
    """
    scores: dict[int, float] = {}
    by_id: dict[int, DocumentChunk] = {}

    for ranking in (semantic, lexical):
        for position, chunk in enumerate(ranking):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (RRF_K + position + 1)
            by_id[chunk.id] = chunk

    best = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
    return [_to_retrieved(by_id[chunk_id], score) for chunk_id, score in best]


def _to_retrieved(chunk: DocumentChunk, score: float) -> RetrievedChunk:
    """Convert a model instance into the transport object used by the RAG service."""
    return RetrievedChunk(
        chunk_id=chunk.id,
        text=chunk.text,
        document_title=chunk.document.title,
        institution=chunk.document.institution,
        source_url=chunk.document.source_url,
        file_name=chunk.document.file_name,
        score=score,
    )
