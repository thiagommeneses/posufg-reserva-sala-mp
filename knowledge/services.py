"""Ingestion pipeline for the normative corpus.

Orchestrates the four steps that turn a downloaded file into retrievable chunks:
extraction, segmentation, embedding and persistence.

Ingestion is idempotent. Each document records the SHA-256 of the file it was built
from; a second run over unchanged files does nothing. This keeps re-indexing cheap and
makes incremental reprocessing the default rather than a special mode.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.utils import timezone

from knowledge import chunking, embedding, extraction
from knowledge.manifest import find_file, load_sources
from knowledge.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

#: Texto em português: usa o dicionário do PostgreSQL para radicalização.
SEARCH_CONFIG = "portuguese"

FORMAT_BY_SUFFIX = {
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
    ".txt": "txt",
}


@dataclass
class IngestionReport:
    """Outcome of an ingestion run."""

    indexed: list[tuple[int, str, int]] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)
    missing: list[tuple[int, str]] = field(default_factory=list)
    failed: list[tuple[int, str, str]] = field(default_factory=list)

    @property
    def total_chunks(self) -> int:
        """Return how many chunks were written in this run."""
        return sum(chunks for _, _, chunks in self.indexed)


def file_hash(path: Path) -> str:
    """Return the SHA-256 of a file, read in blocks.

    Args:
        path: File to hash.

    Returns:
        str: Hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def ingest_corpus(source_ids: list[int] | None = None, *, force: bool = False):
    """Ingest every source of the manifest that has a file on disk.

    Args:
        source_ids: Restrict the run to these manifest ids.
        force: Re-index documents even when the file has not changed.

    Returns:
        IngestionReport: What was indexed, skipped, missing or failed.
    """
    report = IngestionReport()

    for source in load_sources(source_ids):
        identifier, label = source["id"], source["instituicao"]
        path = find_file(identifier)

        if path is None:
            report.missing.append((identifier, label))
            continue

        try:
            document, chunk_count, was_skipped = ingest_document(source, path, force=force)
        except (extraction.ExtractionError, embedding.EmbeddingError) as exc:
            logger.warning("Falha ao indexar %s: %s", path.name, exc)
            report.failed.append((identifier, label, str(exc)))
            continue

        if was_skipped:
            report.skipped.append((identifier, document.file_name))
        else:
            report.indexed.append((identifier, document.file_name, chunk_count))

    return report


@transaction.atomic
def ingest_document(source: dict, path: Path, *, force: bool = False):
    """Ingest a single file, replacing any chunks it had before.

    Args:
        source: Manifest entry for this document.
        path: File on disk.
        force: Re-index even when the content hash is unchanged.

    Returns:
        tuple[Document, int, bool]: The document, how many chunks were written, and
        whether the work was skipped because nothing changed.

    Raises:
        ExtractionError: If the file yields no usable text.
        EmbeddingError: If the embedding model fails.
    """
    digest = file_hash(path)
    document = Document.objects.filter(source_id=source["id"]).first()

    if document and document.content_hash == digest and document.is_indexed and not force:
        return document, document.chunks.count(), True

    extracted = extraction.extract(path)
    texts = chunking.split(extracted.text)
    vectors = embedding.embed_passages(texts)

    document = _upsert_document(source, path, digest, extracted)
    document.chunks.all().delete()

    DocumentChunk.objects.bulk_create(
        [
            DocumentChunk(
                document=document,
                position=position,
                text=text,
                embedding=vector,
                word_count=len(text.split()),
            )
            for position, (text, vector) in enumerate(zip(texts, vectors, strict=True))
        ]
    )

    # O tsvector é calculado no banco para usar o dicionário português do PostgreSQL.
    document.chunks.update(search_vector=SearchVector("text", config=SEARCH_CONFIG))

    document.indexed_at = timezone.now()
    document.save(update_fields=["indexed_at", "updated_at"])
    return document, len(texts), False


def _upsert_document(source: dict, path: Path, digest: str, extracted) -> Document:
    """Create or update the Document row for a source."""
    document, _ = Document.objects.update_or_create(
        source_id=source["id"],
        defaults={
            "slug": source["slug"],
            "institution": source["instituicao"],
            "title": source["documento"],
            "category": source["categoria"],
            "source_url": source["url"],
            "file_name": path.name,
            "file_format": FORMAT_BY_SUFFIX.get(path.suffix.lower(), "txt"),
            "content_hash": digest,
            "word_count": extracted.word_count,
            "page_count": extracted.page_count,
        },
    )
    return document
