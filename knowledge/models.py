"""Models for the knowledge app.

Stores the normative corpus and its vector index. A ``Document`` is one file from
``data/normas/``; a ``DocumentChunk`` is a retrievable passage of that file, carrying
both a dense embedding (semantic search) and a full-text vector (lexical search), so
the two can be combined into a hybrid retrieval strategy.
"""

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from pgvector.django import HnswIndex, VectorField


class DocumentCategory(models.TextChoices):
    """Thematic grouping of a document, mirroring data/normas/fontes.json."""

    REGULAMENTO_AUDITORIO = "regulamento-auditorio", "Regulamento de auditório"
    RESOLUCAO_INSTITUCIONAL = "resolucao-institucional", "Resolução institucional"
    PROCEDIMENTO_RESERVA = "procedimento-reserva", "Procedimento de reserva"
    CONTEXTO_JURIDICO = "contexto-juridico", "Contexto jurídico"
    COMPLEMENTAR_INTERNACIONAL = "complementar-internacional", "Complementar internacional"


class DocumentFormat(models.TextChoices):
    """Source format of the ingested file."""

    PDF = "pdf", "PDF"
    HTML = "html", "HTML"
    TXT = "txt", "Texto"


class Document(models.Model):
    """A normative document ingested into the corpus."""

    source_id = models.PositiveIntegerField(
        unique=True,
        help_text="Identificador da fonte em data/normas/fontes.json.",
    )
    slug = models.SlugField(max_length=120, unique=True)
    institution = models.CharField(max_length=255)
    title = models.CharField(max_length=500)
    category = models.CharField(
        max_length=40,
        choices=DocumentCategory,
        default=DocumentCategory.REGULAMENTO_AUDITORIO,
    )
    source_url = models.URLField(max_length=1000)
    file_name = models.CharField(max_length=255)
    file_format = models.CharField(max_length=10, choices=DocumentFormat)
    content_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 do arquivo. Permite reprocessar apenas o que mudou.",
    )
    word_count = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(blank=True, null=True)
    indexed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Document."""

        ordering = ["source_id"]
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"

    def __str__(self):
        """Return the institution and title."""
        return f"{self.institution} — {self.title}"

    @property
    def is_indexed(self) -> bool:
        """Return True if the document has already been chunked and embedded."""
        return self.indexed_at is not None


class DocumentChunk(models.Model):
    """A retrievable passage of a document, with its dense and lexical vectors."""

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    position = models.PositiveIntegerField(
        help_text="Ordem do trecho dentro do documento, começando em zero.",
    )
    text = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS)
    search_vector = SearchVectorField(blank=True, null=True)
    word_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options for DocumentChunk."""

        ordering = ["document", "position"]
        verbose_name = "Trecho"
        verbose_name_plural = "Trechos"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "position"],
                name="unique_chunk_position_per_document",
            ),
        ]
        indexes = [
            # HNSW com distância de cosseno: o padrão para busca semântica em
            # embeddings normalizados. m e ef_construction são os valores
            # recomendados pelo pgvector para corpus desta ordem de grandeza.
            HnswIndex(
                name="chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
            # Suporta o lado lexical da busca híbrida.
            GinIndex(fields=["search_vector"], name="chunk_search_vector_gin"),
        ]

    def __str__(self):
        """Return a short identification of the chunk."""
        return f"{self.document.slug} #{self.position}"
