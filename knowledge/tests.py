"""Tests for the knowledge app."""

import pytest
from django.conf import settings
from django.db import IntegrityError

from knowledge.models import Document, DocumentCategory, DocumentChunk, DocumentFormat


@pytest.fixture
def document(db):
    """Create a test document."""
    return Document.objects.create(
        source_id=1,
        slug="ufpa-ifch-regulamento-auditorio",
        institution="UFPA — IFCH",
        title="Regulamento nº 1/2025 — Uso do Auditório",
        category=DocumentCategory.REGULAMENTO_AUDITORIO,
        source_url="https://ifch.ufpa.br/images/PDF/2025/Regula_Auditrio.pdf",
        file_name="01-ufpa-ifch-regulamento-auditorio.pdf",
        file_format=DocumentFormat.PDF,
        content_hash="a" * 64,
        word_count=1209,
        page_count=4,
    )


def _embedding(valor: float = 0.1) -> list[float]:
    """Return a dummy embedding with the configured dimensionality."""
    return [valor] * settings.EMBEDDING_DIMENSIONS


class TestDocument:
    """Tests for the Document model."""

    def test_create_document(self, document):
        """Creating a document should persist its metadata."""
        assert document.source_id == 1
        assert document.word_count == 1209
        assert document.indexed_at is None

    def test_str(self, document):
        """__str__ should combine institution and title."""
        assert str(document) == "UFPA — IFCH — Regulamento nº 1/2025 — Uso do Auditório"

    def test_is_indexed_defaults_to_false(self, document):
        """A freshly created document has not been indexed yet."""
        assert document.is_indexed is False

    def test_is_indexed_after_timestamp(self, db, document):
        """Setting indexed_at marks the document as indexed."""
        from django.utils import timezone

        document.indexed_at = timezone.now()
        document.save(update_fields=["indexed_at"])
        assert document.is_indexed is True

    def test_source_id_is_unique(self, db, document):
        """Two documents cannot share the same source_id."""
        with pytest.raises(IntegrityError):
            Document.objects.create(
                source_id=document.source_id,
                slug="outro-slug",
                institution="Outra",
                title="Outro",
                source_url="https://example.org/doc.pdf",
                file_name="99-outro.pdf",
                file_format=DocumentFormat.PDF,
                content_hash="b" * 64,
            )


class TestDocumentChunk:
    """Tests for the DocumentChunk model."""

    def test_create_chunk(self, db, document):
        """A chunk should store its text and embedding."""
        chunk = DocumentChunk.objects.create(
            document=document,
            position=0,
            text="Art. 1º Este regulamento disciplina o uso do auditório.",
            embedding=_embedding(),
            word_count=9,
        )
        assert chunk.document == document
        assert len(chunk.embedding) == settings.EMBEDDING_DIMENSIONS

    def test_str(self, db, document):
        """__str__ should identify document and position."""
        chunk = DocumentChunk.objects.create(
            document=document,
            position=3,
            text="trecho",
            embedding=_embedding(),
        )
        assert str(chunk) == f"{document.slug} #3"

    def test_position_is_unique_per_document(self, db, document):
        """The same position cannot repeat within a document."""
        DocumentChunk.objects.create(
            document=document,
            position=0,
            text="primeiro",
            embedding=_embedding(),
        )
        with pytest.raises(IntegrityError):
            DocumentChunk.objects.create(
                document=document,
                position=0,
                text="duplicado",
                embedding=_embedding(),
            )

    def test_chunks_ordered_by_position(self, db, document):
        """Chunks are returned in reading order."""
        for posicao in (2, 0, 1):
            DocumentChunk.objects.create(
                document=document,
                position=posicao,
                text=f"trecho {posicao}",
                embedding=_embedding(),
            )
        posicoes = list(document.chunks.values_list("position", flat=True))
        assert posicoes == [0, 1, 2]

    def test_deleting_document_removes_chunks(self, db, document):
        """Chunks are cascade-deleted with their document."""
        DocumentChunk.objects.create(
            document=document,
            position=0,
            text="trecho",
            embedding=_embedding(),
        )
        document.delete()
        assert DocumentChunk.objects.count() == 0
