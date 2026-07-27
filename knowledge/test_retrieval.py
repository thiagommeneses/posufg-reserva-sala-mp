"""Tests for retrieval and the RAG service.

Both the embedding model and the LLM are mocked. What is under test here is our own
logic: rank fusion, prompt assembly, provenance and error handling — not whether a
third-party model returns good vectors.
"""

from unittest.mock import patch

import pytest
from django.conf import settings

from ai_assistant.exceptions import AIServiceError
from ai_assistant.services import NO_CONTEXT_ANSWER, _build_context, answer_from_documents
from knowledge import retrieval
from knowledge.embedding import EmbeddingError
from knowledge.models import Document, DocumentChunk, DocumentFormat


def _vetor(valor: float = 0.1) -> list[float]:
    """Return a dummy embedding with the configured dimensionality."""
    return [valor] * settings.EMBEDDING_DIMENSIONS


@pytest.fixture
def documento(db):
    """Create a document to hang chunks from."""
    return Document.objects.create(
        source_id=28,
        slug="ufba-ims-regulamento-auditorios",
        institution="UFBA - IMS",
        title="Regulamento dos Auditórios do IMS",
        source_url="https://example.org/ufba.pdf",
        file_name="28-ufba-ims-regulamento-auditorios.pdf",
        file_format=DocumentFormat.PDF,
        content_hash="c" * 64,
    )


@pytest.fixture
def trechos(db, documento):
    """Create three chunks with distinct texts."""
    return [
        DocumentChunk.objects.create(
            document=documento,
            position=posicao,
            text=texto,
            embedding=_vetor(),
            word_count=len(texto.split()),
        )
        for posicao, texto in enumerate(
            [
                "A taxa de utilização do auditório será de R$ 1.200,00 por dia.",
                "Os pedidos deverão ser feitos com no mínimo 30 dias de antecedência.",
                "É vedado o uso para reuniões político-partidárias.",
            ]
        )
    ]


class TestRankFusion:
    """Tests for Reciprocal Rank Fusion."""

    def test_chunk_in_both_rankings_wins(self, db, trechos):
        """A passage found by both strategies outranks one found by a single one."""
        semantico = [trechos[0], trechos[1]]
        lexical = [trechos[2], trechos[0]]

        resultado = retrieval._fuse(semantico, lexical, top_k=3)

        assert resultado[0].chunk_id == trechos[0].id

    def test_respects_top_k(self, db, trechos):
        """Only top_k results come back."""
        resultado = retrieval._fuse(trechos, trechos, top_k=2)

        assert len(resultado) == 2

    def test_deduplicates_across_rankings(self, db, trechos):
        """A passage present in both lists appears once."""
        resultado = retrieval._fuse(trechos, trechos, top_k=10)

        assert len(resultado) == len(trechos)

    def test_scores_are_descending(self, db, trechos):
        """Results come back ordered by score."""
        resultado = retrieval._fuse(trechos, list(reversed(trechos)), top_k=3)

        pontuacoes = [item.score for item in resultado]
        assert pontuacoes == sorted(pontuacoes, reverse=True)

    def test_carries_provenance(self, db, trechos, documento):
        """Each result knows which document it came from."""
        resultado = retrieval._fuse([trechos[0]], [], top_k=1)

        assert resultado[0].institution == documento.institution
        assert resultado[0].source_url == documento.source_url
        assert resultado[0].citation == f"{documento.institution} — {documento.title}"


class TestContextBuilding:
    """Tests for prompt context assembly."""

    def test_numbers_and_attributes_each_excerpt(self, db, trechos):
        """Excerpts are numbered and carry the institution."""
        recuperados = retrieval._fuse(trechos, [], top_k=3)

        contexto = _build_context(recuperados)

        assert "[1]" in contexto
        assert "[3]" in contexto
        assert contexto.count("UFBA - IMS") == 3

    def test_empty_context_is_empty_string(self):
        """No passages yields an empty context."""
        assert _build_context([]) == ""


@pytest.mark.django_db
class TestAnswerFromDocuments:
    """Tests for the RAG service."""

    def test_returns_answer_and_sources(self, trechos):
        """A successful run returns the answer plus the passages used."""
        recuperados = retrieval._fuse(trechos, [], top_k=3)

        with (
            patch("ai_assistant.services.retrieval.search", return_value=recuperados),
            patch(
                "ai_assistant.services._run_text_completion",
                return_value="A UFBA cobra R$ 1.200,00 por dia [1].",
            ),
        ):
            resultado = answer_from_documents("Quanto custa usar o auditório?")

        assert resultado["used_context"] is True
        assert len(resultado["sources"]) == 3
        assert resultado["sources"][0]["position"] == 1
        assert resultado["sources"][0]["institution"] == "UFBA - IMS"
        assert "1.200" in resultado["answer"]

    def test_does_not_call_llm_without_context(self, db):
        """With nothing retrieved the model is never asked."""
        with (
            patch("ai_assistant.services.retrieval.search", return_value=[]),
            patch("ai_assistant.services._run_text_completion") as completion,
        ):
            resultado = answer_from_documents("Pergunta sobre assunto ausente")

        completion.assert_not_called()
        assert resultado["used_context"] is False
        assert resultado["answer"] == NO_CONTEXT_ANSWER
        assert resultado["sources"] == []

    def test_prompt_carries_question_and_context(self, trechos):
        """The prompt sent to the model includes both question and excerpts."""
        recuperados = retrieval._fuse(trechos, [], top_k=3)

        with (
            patch("ai_assistant.services.retrieval.search", return_value=recuperados),
            patch(
                "ai_assistant.services._run_text_completion", return_value="resposta"
            ) as completion,
        ):
            answer_from_documents("Qual a antecedência mínima?")

        _, prompt = completion.call_args[0]
        assert "Qual a antecedência mínima?" in prompt
        assert "30 dias de antecedência" in prompt

    def test_embedding_failure_becomes_service_error(self, db):
        """A model failure surfaces as AIServiceError, which the view maps to 502."""
        with patch(
            "ai_assistant.services.retrieval.search",
            side_effect=EmbeddingError("modelo indisponível"),
        ):
            with pytest.raises(AIServiceError, match="modelo indisponível"):
                answer_from_documents("Qualquer pergunta")

    def test_hybrid_flag_is_forwarded(self, trechos):
        """Disabling hybrid search reaches the retrieval layer."""
        with (
            patch("ai_assistant.services.retrieval.search", return_value=[]) as search,
            patch("ai_assistant.services._run_text_completion"),
        ):
            answer_from_documents("Pergunta", top_k=7, hybrid=False)

        search.assert_called_once_with("Pergunta", 7, hybrid=False)
