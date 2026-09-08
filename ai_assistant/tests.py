"""Tests for the ai_assistant app."""

from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from django.contrib.auth import get_user_model
from groq import AuthenticationError, GroqError, RateLimitError
from rest_framework.test import APIClient

from ai_assistant.exceptions import AIServiceError
from ai_assistant.services import (
    GENERIC_GROQ_FAILURE_MESSAGE,
    _ai_error_from_groq,
    _run_json_completion,
    classify_maintenance_reason,
    extract_room_search_filters,
    normalize_room_search_attributes,
)
from spaces.models import Attribute, Space, SpaceAttribute

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(username="ai_user", password="testpass123")


@pytest.fixture
def api_client(user):
    """Return an API client authenticated as the test user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def projector_space(db):
    """Create a space with capacity 10 and a projector attribute."""
    space = Space.objects.create(name="Sala Grande", capacity=10, location="Bloco A")
    attribute = Attribute.objects.create(name="projetor")
    SpaceAttribute.objects.create(space=space, attribute=attribute)
    return space


@pytest.fixture
def small_space(db):
    """Create a small space without any attributes."""
    return Space.objects.create(name="Sala Pequena", capacity=2, location="Bloco B")


class TestExtractRoomSearchFilters:
    """Unit tests for services.extract_room_search_filters."""

    @patch("ai_assistant.services._run_json_completion")
    def test_returns_parsed_filters(self, mock_completion):
        """It should return the filters parsed from the LLM JSON response."""
        mock_completion.return_value = {
            "min_capacity": 8,
            "max_capacity": None,
            "attributes": ["projetor"],
            "location": None,
            "summary": "Sala para 8 pessoas com projetor.",
        }

        result = extract_room_search_filters("sala para 8 pessoas com projetor")

        assert result["min_capacity"] == 8
        assert result["max_capacity"] is None
        assert result["attributes"] == ["Projetor"]
        assert result["summary"] == "Sala para 8 pessoas com projetor."

    @patch("ai_assistant.services._run_json_completion")
    def test_extracts_max_capacity_for_upper_bound(self, mock_completion):
        """'Até N pessoas' should populate max_capacity, not min_capacity."""
        mock_completion.return_value = {
            "min_capacity": None,
            "max_capacity": 4,
            "attributes": [],
            "location": None,
            "summary": "Sala para até 4 pessoas.",
        }

        result = extract_room_search_filters("preciso de uma sala com capacidade de até 4 pessoas")

        assert result["min_capacity"] is None
        assert result["max_capacity"] == 4
        assert "até 4" in result["summary"]

    @patch("ai_assistant.services._run_json_completion")
    def test_normalizes_internet_synonym_to_wifi(self, mock_completion):
        """Popular synonyms like 'internet' should map to the Wi-Fi catalog attribute."""
        mock_completion.return_value = {
            "min_capacity": None,
            "max_capacity": None,
            "attributes": ["internet"],
            "location": None,
            "summary": "Sala com internet.",
        }

        result = extract_room_search_filters("sala com internet")

        assert result["attributes"] == ["Wi-Fi"]

    @patch("ai_assistant.services._run_json_completion")
    def test_drops_unknown_attributes_from_llm_response(self, mock_completion):
        """Invented equipment labels should not remain in the extracted filters."""
        mock_completion.return_value = {
            "min_capacity": 12,
            "max_capacity": None,
            "attributes": ["internet", "sistema de som"],
            "location": "Bloco A",
            "summary": "Sala grande com internet no Bloco A.",
        }

        result = extract_room_search_filters("sala grande com internet no bloco A")

        assert result["attributes"] == ["Wi-Fi"]
        assert result["min_capacity"] == 12
        assert result["max_capacity"] is None
        assert result["location"] == "Bloco A"

    @patch("ai_assistant.services._get_client")
    def test_raises_ai_service_error_when_client_unavailable(self, mock_get_client):
        """It should propagate AIServiceError raised while building the client."""
        mock_get_client.side_effect = AIServiceError("Serviço de IA não configurado.")

        with pytest.raises(AIServiceError):
            extract_room_search_filters("sala para 8 pessoas")


class TestNormalizeRoomSearchAttributes:
    """Unit tests for services.normalize_room_search_attributes."""

    def test_maps_common_wifi_synonyms(self):
        """Internet-related wording should resolve to Wi-Fi."""
        assert normalize_room_search_attributes(["internet", "wifi", "Wi-Fi"]).aceitos == ["Wi-Fi"]

    def test_maps_expanded_equipment_synonyms(self):
        """Popular equipment wording should resolve to catalog attributes."""
        assert normalize_room_search_attributes(["meet"]).aceitos == ["Videoconferência"]
        assert normalize_room_search_attributes(["slides"]).aceitos == ["Projetor"]
        assert normalize_room_search_attributes(["monitor"]).aceitos == ["TV"]
        assert normalize_room_search_attributes(["ac"]).aceitos == ["Ar-condicionado"]
        assert normalize_room_search_attributes(["pizarra"]).aceitos == ["Quadro branco"]
        assert normalize_room_search_attributes(["cam"]).aceitos == ["Webcam"]

    def test_drops_unknown_attributes(self):
        """Labels outside the catalog should be discarded, not used as filters."""
        resultado = normalize_room_search_attributes(["som surround", "internet"])
        assert resultado.aceitos == ["Wi-Fi"]
        assert resultado.ignorados == ["som surround"]


class TestClassifyMaintenanceReason:
    """Unit tests for services.classify_maintenance_reason."""

    @patch("ai_assistant.services._run_json_completion")
    def test_returns_valid_category(self, mock_completion):
        """It should return the category classified by the LLM."""
        mock_completion.return_value = {
            "category": "eletrica",
            "confidence": "alta",
            "justification": "Menciona troca de lâmpadas.",
        }

        result = classify_maintenance_reason("Troca de lâmpadas queimadas")

        assert result["category"] == "eletrica"
        assert result["confidence"] == "alta"

    @patch("ai_assistant.services._run_json_completion")
    def test_falls_back_to_outros_for_unknown_category(self, mock_completion):
        """It should fall back to 'outros' when the LLM returns an unexpected category."""
        mock_completion.return_value = {
            "category": "categoria-invalida",
            "confidence": "baixa",
            "justification": "",
        }

        result = classify_maintenance_reason("Algo estranho")

        assert result["category"] == "outros"


class TestRoomSearchAssistantView:
    """Integration tests for the room search assistant endpoint."""

    @patch("ai_assistant.views.extract_room_search_filters")
    def test_returns_matching_spaces(
        self,
        mock_extract,
        api_client,
        projector_space,
        small_space,
    ):
        """It should return only spaces matching the extracted filters."""
        mock_extract.return_value = {
            "min_capacity": 8,
            "max_capacity": None,
            "attributes": ["projetor"],
            "location": None,
            "summary": "Sala para 8 pessoas com projetor.",
        }

        response = api_client.post(
            "/api/v1/ai/room-search/",
            {"query": "sala para 8 pessoas com projetor"},
        )

        assert response.status_code == 200
        result_ids = [item["id"] for item in response.data["results"]]
        assert result_ids == [projector_space.id]

    @patch("ai_assistant.views.extract_room_search_filters")
    def test_filters_by_max_capacity(
        self,
        mock_extract,
        api_client,
        projector_space,
        small_space,
    ):
        """An upper bound should exclude rooms larger than max_capacity."""
        mock_extract.return_value = {
            "min_capacity": None,
            "max_capacity": 4,
            "attributes": [],
            "location": None,
            "summary": "Sala para até 4 pessoas.",
        }

        response = api_client.post(
            "/api/v1/ai/room-search/",
            {"query": "sala com capacidade de até 4 pessoas"},
        )

        assert response.status_code == 200
        result_ids = [item["id"] for item in response.data["results"]]
        assert small_space.id in result_ids
        assert projector_space.id not in result_ids

    def test_rejects_short_query(self, api_client):
        """It should return 400 for a query below the minimum length."""
        response = api_client.post("/api/v1/ai/room-search/", {"query": "ab"})

        assert response.status_code == 400

    def test_requires_authentication(self):
        """It should reject unauthenticated requests."""
        client = APIClient()

        response = client.post(
            "/api/v1/ai/room-search/",
            {"query": "sala para 8 pessoas"},
        )

        assert response.status_code in (401, 403)

    @patch("ai_assistant.views.extract_room_search_filters")
    def test_returns_502_when_ai_service_fails(self, mock_extract, api_client):
        """It should return 502 when the AI provider is unavailable."""
        mock_extract.side_effect = AIServiceError("Não foi possível consultar o serviço de IA.")

        response = api_client.post(
            "/api/v1/ai/room-search/",
            {"query": "sala para 8 pessoas"},
        )

        assert response.status_code == 502


class TestMaintenanceReasonClassifierView:
    """Integration tests for the maintenance reason classifier endpoint."""

    @patch("ai_assistant.views.classify_maintenance_reason")
    def test_returns_classification(self, mock_classify, api_client):
        """It should return the classification produced by the AI service."""
        mock_classify.return_value = {
            "category": "eletrica",
            "confidence": "alta",
            "justification": "Menciona lâmpadas.",
        }

        response = api_client.post(
            "/api/v1/ai/maintenance-classify/",
            {"reason": "Troca de lâmpadas queimadas"},
        )

        assert response.status_code == 200
        assert response.data["category"] == "eletrica"

    def test_rejects_empty_reason(self, api_client):
        """It should return 400 when the reason is empty."""
        response = api_client.post("/api/v1/ai/maintenance-classify/", {"reason": ""})

        assert response.status_code == 400

    def test_requires_authentication(self):
        """It should reject unauthenticated requests."""
        client = APIClient()

        response = client.post(
            "/api/v1/ai/maintenance-classify/",
            {"reason": "Troca de lâmpadas"},
        )

        assert response.status_code in (401, 403)


class TestMessageForGroqError:
    """Unit tests for user-facing Groq error messages."""

    def _rate_limit_error(self, message: str) -> RateLimitError:
        """Build a RateLimitError with a controllable message string."""
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        response = httpx.Response(429, request=request)
        return RateLimitError(message, response=response, body=None)

    def test_rate_limit_includes_retry_hint(self):
        """Daily quota exhaustion should mention approximate wait time."""
        exc = self._rate_limit_error("Rate limit reached for model. Please try again in 33m50.4s.")

        error = _ai_error_from_groq(exc)

        assert "muitas consultas" in error.user_message
        assert "cerca de 34 minutos" in error.user_message
        assert "RateLimitError" in error.technical_detail
        assert "33m50.4s" in error.technical_detail

    def test_rate_limit_without_retry_hint(self):
        """Missing retry timing should still explain a temporary pause."""
        exc = self._rate_limit_error("Rate limit reached for model.")

        error = _ai_error_from_groq(exc)

        assert "muitas consultas" in error.user_message
        assert "minutos" not in error.user_message
        assert "RateLimitError" in error.technical_detail

    def test_authentication_error(self):
        """Invalid API keys keep a friendly UI message and technical detail."""
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        response = httpx.Response(401, request=request)
        exc = AuthenticationError("Invalid API Key", response=response, body=None)

        error = _ai_error_from_groq(exc)

        assert "não está disponível" in error.user_message
        assert "chave" not in error.user_message.lower()
        assert "AuthenticationError" in error.technical_detail

    def test_generic_groq_error(self):
        """Unclassified Groq failures keep the generic fallback."""
        error = _ai_error_from_groq(GroqError("boom"))

        assert error.user_message == GENERIC_GROQ_FAILURE_MESSAGE
        assert "GroqError: boom" in error.technical_detail


class TestEsperaHttp429:
    """Short TPM waits are retried; daily-quota waits are not slept through."""

    def _rate_limit_error(self, message: str) -> RateLimitError:
        """Build a RateLimitError with a controllable message string."""
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        response = httpx.Response(429, request=request)
        return RateLimitError(message, response=response, body=None)

    def _completion(self, payload: str):
        """Build a Groq-shaped completion object."""
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            choices=[SimpleNamespace(message=SimpleNamespace(content=payload))],
        )

    @patch("ai_assistant.services.time.sleep")
    @patch("ai_assistant.services._get_client")
    def test_retry_curto_registra_espera(self, mock_get_client, mock_sleep):
        """A 1.5s TPM pause is slept and recorded separately from token usage."""
        erro = self._rate_limit_error("Please try again in 1.5s.")
        mock_get_client.return_value.chat.completions.create.side_effect = [
            erro,
            self._completion('{"ok": true}'),
        ]
        sink = {}

        result = _run_json_completion("sistema", "usuario", usage_sink=sink)

        assert result == {"ok": True}
        mock_sleep.assert_called_once_with(1.5)
        assert sink["espera_ms"] == 1500

    @patch("ai_assistant.services.time.sleep")
    @patch("ai_assistant.services._get_client")
    def test_cota_diaria_nao_dorme(self, mock_get_client, mock_sleep):
        """A half-hour daily quota must not freeze the test runner."""
        erro = self._rate_limit_error("Please try again in 33m50.4s.")
        mock_get_client.return_value.chat.completions.create.side_effect = erro

        with pytest.raises(AIServiceError):
            _run_json_completion("sistema", "usuario")

        mock_sleep.assert_not_called()
