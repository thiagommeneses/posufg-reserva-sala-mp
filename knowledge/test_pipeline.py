"""Tests for the ingestion pipeline: extraction, chunking and indexing.

The embedding model is mocked throughout. Running the real ONNX model would make the
suite depend on a several-hundred-megabyte download and turn a fast test run into a
slow one, without testing any of our own logic.
"""

from unittest.mock import patch

import pytest
from django.conf import settings

from knowledge import chunking, extraction, services
from knowledge.embedding import EmbeddingError
from knowledge.extraction import ExtractionError
from knowledge.manifest import ManifestError, find_file, load_sources
from knowledge.models import Document, DocumentChunk

NORMA = """CAPÍTULO I
DISPOSIÇÕES GERAIS

Art. 1º Este regulamento disciplina o uso do auditório, estabelecendo normas para sua
utilização por parte da comunidade acadêmica e de terceiros.

Art. 2º O auditório possui capacidade para 60 pessoas.

§ 1º Cabe ao solicitante observar o horário no momento da reserva.

Art. 3º Fica expressamente vedado o uso do auditório para eventos de caráter
exclusivamente comercial ou promocional de empresas privadas.
"""


def _texto_longo(repeticoes: int = 30) -> str:
    """Return a text comfortably above the extraction minimum."""
    return (NORMA + "\n") * repeticoes


def _vetores(quantidade: int) -> list[list[float]]:
    """Return dummy vectors with the configured dimensionality."""
    return [[0.1] * settings.EMBEDDING_DIMENSIONS for _ in range(quantidade)]


@pytest.fixture
def corpus_dir(tmp_path, settings):
    """Point the corpus directory at a temporary folder."""
    settings.KNOWLEDGE_DOCUMENTS_DIR = tmp_path
    with patch("knowledge.manifest.MANIFEST_PATH", tmp_path / "fontes.json"):
        yield tmp_path


@pytest.fixture
def fonte():
    """Return a single manifest entry."""
    return {
        "id": 1,
        "slug": "ufpa-ifch-regulamento-auditorio",
        "instituicao": "UFPA - IFCH",
        "documento": "Regulamento no 1/2025",
        "categoria": "regulamento-auditorio",
        "url": "https://example.org/regulamento.pdf",
        "verificado": True,
    }


class TestExtraction:
    """Tests for text extraction."""

    def test_extracts_plain_text(self, tmp_path):
        """A .txt file is read and normalised."""
        caminho = tmp_path / "01-norma.txt"
        caminho.write_text(_texto_longo(), encoding="utf-8")

        resultado = extraction.extract(caminho)

        assert resultado.word_count > extraction.MIN_WORDS
        assert "Art. 1º" in resultado.text
        assert resultado.page_count is None

    def test_rejects_unsupported_format(self, tmp_path):
        """An unknown extension is refused."""
        caminho = tmp_path / "01-norma.docx"
        caminho.write_bytes(b"conteudo")

        with pytest.raises(ExtractionError, match="Formato não suportado"):
            extraction.extract(caminho)

    def test_rejects_text_below_minimum(self, tmp_path):
        """A near-empty file is refused instead of entering the index."""
        caminho = tmp_path / "01-norma.txt"
        caminho.write_text("Apenas algumas palavras soltas.", encoding="utf-8")

        with pytest.raises(ExtractionError, match="palavras extraídas"):
            extraction.extract(caminho)

    def test_rejects_javascript_shell(self, tmp_path):
        """An HTML page with only navigation is refused."""
        caminho = tmp_path / "01-norma.html"
        caminho.write_text(
            "<html><body><nav>Menu</nav><script>app()</script></body></html>",
            encoding="utf-8",
        )

        with pytest.raises(ExtractionError, match="casca renderizada"):
            extraction.extract(caminho)

    def test_falls_back_when_boilerplate_detector_discards_content(self, tmp_path):
        """Content laid out in tables survives even if trafilatura discards it.

        Reproduz o caso real dos portais da UFPI, do IFC e da UFU: trafilatura
        devolvia menos de 70 palavras em páginas com centenas.
        """
        linhas = "".join(
            f"<tr><td>Art. {n}º Sobre a reserva de espaços, " + "regra " * 20 + "</td></tr>"
            for n in range(1, 12)
        )
        caminho = tmp_path / "01-norma.html"
        caminho.write_text(
            f"<html><body><nav>Menu</nav><table>{linhas}</table>"
            f"<footer>Rodapé</footer></body></html>",
            encoding="utf-8",
        )

        resultado = extraction.extract(caminho)

        assert resultado.word_count >= extraction.MIN_WORDS
        assert "Art. 1º" in resultado.text
        assert "Menu" not in resultado.text
        assert "Rodapé" not in resultado.text

    def test_pdf_error_message_mentions_scanning(self, tmp_path):
        """The diagnostic for a PDF points at the missing text layer."""
        from pypdf import PdfWriter

        caminho = tmp_path / "01-norma.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with caminho.open("wb") as handle:
            writer.write(handle)

        with pytest.raises(ExtractionError, match="sem camada de texto"):
            extraction.extract(caminho)

    def test_normalise_preserves_paragraphs(self):
        """Whitespace collapses but paragraph breaks survive."""
        resultado = extraction.normalise("Art.  1º   texto\n\n\n\nArt. 2º outro")

        assert resultado == "Art. 1º texto\n\nArt. 2º outro"


class TestChunking:
    """Tests for text segmentation."""

    def test_splits_long_text(self):
        """A long document yields multiple chunks."""
        trechos = chunking.split(_texto_longo(), chunk_size=400, overlap=50)

        assert len(trechos) > 1
        assert all(trecho.strip() for trecho in trechos)

    def test_short_text_stays_whole(self):
        """Text below the chunk size is not split."""
        trechos = chunking.split("Art. 1º Texto curto.", chunk_size=1000, overlap=0)

        assert trechos == ["Art. 1º Texto curto."]

    def test_prefers_article_boundaries(self):
        """Articles that fit in a chunk are never cut in the middle."""
        # Cada artigo ocupa ~210 caracteres; com chunk_size de 250 cabe um por
        # trecho, e dois não cabem juntos. Se o separador de artigo não fosse
        # respeitado, os cortes cairiam no meio do texto.
        texto = "".join(f"\nArt. {n}º " + "palavra " * 25 for n in range(1, 8))

        trechos = chunking.split(texto, chunk_size=250, overlap=0)

        assert len(trechos) > 1
        assert all(trecho.startswith("Art.") for trecho in trechos)


class TestManifest:
    """Tests for manifest loading and file matching."""

    def test_missing_manifest_raises(self, corpus_dir):
        """A missing manifest is reported clearly."""
        with pytest.raises(ManifestError, match="não encontrado"):
            load_sources()

    def test_invalid_manifest_raises(self, corpus_dir):
        """Malformed JSON is reported as such."""
        (corpus_dir / "fontes.json").write_text("{invalido", encoding="utf-8")

        with pytest.raises(ManifestError, match="inválido"):
            load_sources()

    def test_filters_by_id(self, corpus_dir, fonte):
        """Only the requested ids are returned."""
        import json

        outra = {**fonte, "id": 2, "slug": "outra"}
        (corpus_dir / "fontes.json").write_text(
            json.dumps({"fontes": [fonte, outra]}), encoding="utf-8"
        )

        assert [f["id"] for f in load_sources([2])] == [2]

    def test_find_file_matches_by_numeric_prefix(self, corpus_dir):
        """The file is located by id even when the slug on disk differs."""
        (corpus_dir / "07-nome-totalmente-diferente.pdf").write_bytes(b"x")

        encontrado = find_file(7)

        assert encontrado is not None
        assert encontrado.name == "07-nome-totalmente-diferente.pdf"

    def test_find_file_returns_none_when_absent(self, corpus_dir):
        """A source without a file yields None."""
        assert find_file(42) is None


@pytest.mark.django_db
class TestIngestion:
    """Tests for the ingestion service."""

    def _preparar(self, corpus_dir, fonte, conteudo=None):
        """Write the manifest and the document file to the temporary corpus."""
        import json

        (corpus_dir / "fontes.json").write_text(json.dumps({"fontes": [fonte]}), encoding="utf-8")
        (corpus_dir / "01-norma.txt").write_text(conteudo or _texto_longo(), encoding="utf-8")

    def test_indexes_document_and_chunks(self, corpus_dir, fonte):
        """A full run creates the document and its chunks."""
        self._preparar(corpus_dir, fonte)

        with patch(
            "knowledge.services.embedding.embed_passages", side_effect=lambda t: _vetores(len(t))
        ):
            report = services.ingest_corpus()

        assert len(report.indexed) == 1
        documento = Document.objects.get(source_id=1)
        assert documento.institution == "UFPA - IFCH"
        assert documento.is_indexed
        assert documento.chunks.count() == report.total_chunks > 0

    def test_second_run_skips_unchanged(self, corpus_dir, fonte):
        """Re-running over an unchanged file does no work."""
        self._preparar(corpus_dir, fonte)

        with patch(
            "knowledge.services.embedding.embed_passages", side_effect=lambda t: _vetores(len(t))
        ):
            services.ingest_corpus()
            report = services.ingest_corpus()

        assert report.indexed == []
        assert len(report.skipped) == 1

    def test_force_reindexes(self, corpus_dir, fonte):
        """--force reprocesses even when nothing changed."""
        self._preparar(corpus_dir, fonte)

        with patch(
            "knowledge.services.embedding.embed_passages", side_effect=lambda t: _vetores(len(t))
        ):
            services.ingest_corpus()
            report = services.ingest_corpus(force=True)

        assert len(report.indexed) == 1

    def test_changed_file_is_reindexed(self, corpus_dir, fonte):
        """A changed file produces a new hash and is reprocessed."""
        self._preparar(corpus_dir, fonte)

        with patch(
            "knowledge.services.embedding.embed_passages", side_effect=lambda t: _vetores(len(t))
        ):
            services.ingest_corpus()
            hash_inicial = Document.objects.get(source_id=1).content_hash

            (corpus_dir / "01-norma.txt").write_text(_texto_longo(40), encoding="utf-8")
            report = services.ingest_corpus()

        assert len(report.indexed) == 1
        assert Document.objects.get(source_id=1).content_hash != hash_inicial

    def test_reindexing_replaces_old_chunks(self, corpus_dir, fonte):
        """Chunks from a previous run do not accumulate."""
        self._preparar(corpus_dir, fonte)

        with patch(
            "knowledge.services.embedding.embed_passages", side_effect=lambda t: _vetores(len(t))
        ):
            services.ingest_corpus()
            primeiro_total = DocumentChunk.objects.count()
            services.ingest_corpus(force=True)

        assert DocumentChunk.objects.count() == primeiro_total

    def test_missing_file_is_reported(self, corpus_dir, fonte):
        """A source without a file on disk is listed as missing."""
        import json

        (corpus_dir / "fontes.json").write_text(json.dumps({"fontes": [fonte]}), encoding="utf-8")

        report = services.ingest_corpus()

        assert len(report.missing) == 1
        assert Document.objects.count() == 0

    def test_extraction_failure_is_reported(self, corpus_dir, fonte):
        """An unusable file is reported without aborting the run."""
        self._preparar(corpus_dir, fonte, conteudo="curto demais")

        report = services.ingest_corpus()

        assert len(report.failed) == 1
        assert "palavras extraídas" in report.failed[0][2]
        assert Document.objects.count() == 0

    def test_embedding_failure_is_reported(self, corpus_dir, fonte):
        """A model failure is caught and reported per document."""
        self._preparar(corpus_dir, fonte)

        with patch(
            "knowledge.services.embedding.embed_passages",
            side_effect=EmbeddingError("modelo indisponível"),
        ):
            report = services.ingest_corpus()

        assert len(report.failed) == 1
        assert "modelo indisponível" in report.failed[0][2]

    def test_file_hash_is_stable(self, corpus_dir):
        """The same content always hashes to the same value."""
        caminho = corpus_dir / "arquivo.txt"
        caminho.write_text("conteúdo", encoding="utf-8")

        assert services.file_hash(caminho) == services.file_hash(caminho)
