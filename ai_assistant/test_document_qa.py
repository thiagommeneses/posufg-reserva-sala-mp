"""Tests for the document question-answering endpoint."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from ai_assistant.exceptions import AIServiceError

User = get_user_model()

RESPOSTA = {
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
def cliente(usuario):
    """Return an API client authenticated as the user."""
    client = APIClient()
    client.force_authenticate(user=usuario)
    return client


@pytest.fixture
def url():
    """Return the endpoint URL."""
    return reverse("ai-document-qa")


class TestDocumentQAView:
    """Tests for the /api/v1/ai/document-qa/ endpoint."""

    def test_returns_answer_with_sources(self, cliente, url):
        """A valid question returns the answer and its sources."""
        with patch("ai_assistant.views.answer_from_documents", return_value=RESPOSTA):
            response = cliente.post(url, {"question": "Quanto custa o auditório?"}, format="json")

        assert response.status_code == 200
        assert response.data["used_context"] is True
        assert len(response.data["sources"]) == 1
        assert response.data["sources"][0]["institution"] == "UFBA - IMS"

    def test_rejects_short_question(self, cliente, url):
        """A question below the minimum length is refused."""
        response = cliente.post(url, {"question": "oi"}, format="json")

        assert response.status_code == 400

    def test_rejects_missing_question(self, cliente, url):
        """The question field is required."""
        response = cliente.post(url, {}, format="json")

        assert response.status_code == 400

    def test_rejects_out_of_range_top_k(self, cliente, url):
        """top_k outside the accepted range is refused."""
        response = cliente.post(
            url, {"question": "Qual a antecedência?", "top_k": 99}, format="json"
        )

        assert response.status_code == 400

    def test_unauthenticated_request_is_rejected(self, db, url):
        """The endpoint requires authentication."""
        response = APIClient().post(url, {"question": "Qual a regra?"}, format="json")

        assert response.status_code in (401, 403)

    def test_ai_failure_returns_502(self, cliente, url):
        """A failure in the AI service maps to 502, as in the other AI endpoints."""
        with patch(
            "ai_assistant.views.answer_from_documents",
            side_effect=AIServiceError("serviço indisponível"),
        ):
            response = cliente.post(url, {"question": "Qual a regra?"}, format="json")

        assert response.status_code == 502
        assert "indisponível" in response.data["detail"]

    def test_forwards_options_to_service(self, cliente, url):
        """top_k and hybrid reach the service layer."""
        with patch("ai_assistant.views.answer_from_documents", return_value=RESPOSTA) as service:
            cliente.post(
                url,
                {"question": "Qual a antecedência?", "top_k": 3, "hybrid": False},
                format="json",
            )

        service.assert_called_once_with("Qual a antecedência?", 3, hybrid=False)

    def test_empty_corpus_answer_is_returned(self, cliente, url):
        """A run with no retrieved context still returns 200."""
        vazio = {"answer": "Não encontrei nada.", "sources": [], "used_context": False}

        with patch("ai_assistant.views.answer_from_documents", return_value=vazio):
            response = cliente.post(url, {"question": "Assunto ausente"}, format="json")

        assert response.status_code == 200
        assert response.data["used_context"] is False
        assert response.data["sources"] == []
