"""Tests for the document assistant web page."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from ai_assistant.exceptions import AIServiceError
from knowledge.models import Document, DocumentChunk, DocumentFormat

User = get_user_model()

RESULTADO = {
    "answer": "A UFBA cobra R$ 1.200,00 por dia [1].",
    "sources": [
        {
            "position": 1,
            "institution": "UFBA - IMS",
            "document": "Regulamento dos Auditórios",
            "url": "https://example.org/ufba.pdf",
            "excerpt": "A taxa de utilização será de R$ 1.200,00 por dia.",
            "score": 0.0164,
        }
    ],
    "used_context": True,
}


@pytest.fixture
def usuario(db):
    """Create an authenticated user."""
    return User.objects.create_user(username="consulta", password="senha-forte-123")


@pytest.fixture
def cliente(client, usuario):
    """Return a client logged in as the user."""
    client.force_login(usuario)
    return client


@pytest.fixture
def url():
    """Return the assistant page URL."""
    return reverse("document_assistant")


@pytest.fixture
def corpus(db):
    """Create two indexed documents with chunks."""
    for indice, instituicao in enumerate(["UFBA - IMS", "UFS - BICEN"], start=1):
        documento = Document.objects.create(
            source_id=indice,
            slug=f"doc-{indice}",
            institution=instituicao,
            title=f"Regulamento {indice}",
            source_url=f"https://example.org/{indice}.pdf",
            file_name=f"{indice:02d}-doc.pdf",
            file_format=DocumentFormat.PDF,
            content_hash=f"{indice}" * 64,
            indexed_at=timezone.now(),
        )
        DocumentChunk.objects.create(
            document=documento,
            position=0,
            text="Trecho de exemplo.",
            embedding=[0.1] * 384,
        )


class TestDocumentAssistantPage:
    """Tests for GET on the assistant page."""

    def test_authenticated_user_gets_page(self, cliente, url):
        """The page renders for a logged-in user."""
        response = cliente.get(url)

        assert response.status_code == 200
        assert "Consultar Normas" in response.content.decode()

    def test_unauthenticated_user_is_redirected(self, db, client, url):
        """The page requires authentication."""
        response = client.get(url)

        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_shows_corpus_statistics(self, cliente, url, corpus):
        """Indexed documents, institutions and chunks are counted."""
        response = cliente.get(url)

        assert response.context["document_count"] == 2
        assert response.context["institution_count"] == 2
        assert response.context["chunk_count"] == 2

    def test_unindexed_documents_are_not_counted(self, cliente, url, db):
        """A document without indexed_at does not appear in the statistics."""
        Document.objects.create(
            source_id=99,
            slug="nao-indexado",
            institution="Instituição",
            title="Documento",
            source_url="https://example.org/x.pdf",
            file_name="99-x.pdf",
            file_format=DocumentFormat.PDF,
            content_hash="9" * 64,
        )

        response = cliente.get(url)

        assert response.context["document_count"] == 0

    def test_offers_suggested_questions(self, cliente, url):
        """Suggested questions are available to the template."""
        response = cliente.get(url)

        assert len(response.context["suggested_questions"]) > 0


class TestDocumentAssistantQuestion:
    """Tests for POST on the assistant page."""

    def test_returns_answer_partial(self, cliente, url):
        """A valid question renders the answer partial with its sources."""
        with patch("knowledge.views.answer_from_documents", return_value=RESULTADO):
            response = cliente.post(url, {"question": "Quanto custa o auditório?"})

        conteudo = response.content.decode()
        assert response.status_code == 200
        assert "1.200,00" in conteudo
        assert "UFBA - IMS" in conteudo
        assert "Fontes utilizadas" in conteudo

    def test_partial_does_not_extend_base_template(self, cliente, url):
        """The HTMX response is a fragment, not a full page."""
        with patch("knowledge.views.answer_from_documents", return_value=RESULTADO):
            response = cliente.post(url, {"question": "Quanto custa o auditório?"})

        assert "<html" not in response.content.decode()

    def test_short_question_shows_error(self, cliente, url):
        """A question below the minimum length is refused without calling the AI."""
        with patch("knowledge.views.answer_from_documents") as service:
            response = cliente.post(url, {"question": "oi"})

        service.assert_not_called()
        assert "pelo menos 5 caracteres" in response.content.decode()

    def test_blank_question_shows_error(self, cliente, url):
        """An empty question is refused."""
        with patch("knowledge.views.answer_from_documents") as service:
            response = cliente.post(url, {"question": "   "})

        service.assert_not_called()
        assert response.status_code == 200

    def test_ai_failure_shows_message(self, cliente, url):
        """A failure in the AI service is shown to the user, not raised."""
        with patch(
            "knowledge.views.answer_from_documents",
            side_effect=AIServiceError(
                "O assistente precisa de uma pausa.",
                technical_detail="RateLimitError: TPD exceeded",
            ),
        ):
            response = cliente.post(url, {"question": "Qual a regra?"})

        assert response.status_code == 200
        html = response.content.decode()
        assert "O assistente precisa de uma pausa." in html
        assert "RateLimitError: TPD exceeded" in html
        assert "console.warn" in html

    def test_answer_without_context_is_flagged(self, cliente, url):
        """An answer with no retrieved passages warns the user."""
        vazio = {"answer": "Não encontrei nada.", "sources": [], "used_context": False}

        with patch("knowledge.views.answer_from_documents", return_value=vazio):
            response = cliente.post(url, {"question": "Assunto ausente"})

        assert "Nenhum trecho da base foi usado" in response.content.decode()

    def test_sources_link_to_original_document(self, cliente, url):
        """Each source links back to where it came from."""
        with patch("knowledge.views.answer_from_documents", return_value=RESULTADO):
            response = cliente.post(url, {"question": "Quanto custa o auditório?"})

        assert "https://example.org/ufba.pdf" in response.content.decode()

    def test_unauthenticated_post_is_redirected(self, db, client, url):
        """Posting requires authentication."""
        response = client.post(url, {"question": "Qual a regra?"})

        assert response.status_code == 302
