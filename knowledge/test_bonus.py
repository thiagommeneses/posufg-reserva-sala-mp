"""Tests for the complementary features: conversation history and automatic evaluation."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from ai_assistant import evaluation
from ai_assistant.exceptions import AIServiceError
from ai_assistant.services import _build_history, answer_from_documents
from knowledge.models import ConversationTurn

User = get_user_model()

RESULTADO = {
    "answer": "A UFBA cobra R$ 1.200,00 por dia [1].",
    "sources": [
        {
            "position": 1,
            "institution": "UFBA - IMS",
            "document": "Regulamento dos Auditórios",
            "url": "https://example.org/ufba.pdf",
            "excerpt": "A taxa será de R$ 1.200,00 por dia.",
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


@pytest.mark.django_db
class TestConversationHistory:
    """Tests for the conversation history feature."""

    def test_question_is_persisted(self, cliente, url, usuario):
        """Asking a question records the turn."""
        with patch("knowledge.views.answer_from_documents", return_value=RESULTADO):
            cliente.post(url, {"question": "Quanto custa o auditório?"})

        turno = ConversationTurn.objects.get(user=usuario)
        assert turno.question == "Quanto custa o auditório?"
        assert turno.used_context is True
        assert turno.source_count == 1

    def test_sources_are_stored_denormalised(self, cliente, url, usuario):
        """The excerpt is copied, so it survives a reindex of the corpus."""
        with patch("knowledge.views.answer_from_documents", return_value=RESULTADO):
            cliente.post(url, {"question": "Quanto custa o auditório?"})

        turno = ConversationTurn.objects.get(user=usuario)
        assert turno.sources[0]["institution"] == "UFBA - IMS"
        assert "1.200,00" in turno.sources[0]["excerpt"]

    def test_previous_turns_are_passed_as_context(self, cliente, url, usuario):
        """A follow-up question receives the earlier turns."""
        ConversationTurn.objects.create(
            user=usuario,
            question="Quanto custa o auditório da UFBA?",
            answer="R$ 1.200,00 por dia.",
            sources=[],
        )

        with patch("knowledge.views.answer_from_documents", return_value=RESULTADO) as service:
            cliente.post(url, {"question": "E na UFS?"})

        historico = service.call_args.kwargs["history"]
        assert len(historico) == 1
        assert historico[0].question == "Quanto custa o auditório da UFBA?"

    def test_context_is_limited_to_recent_turns(self, cliente, url, usuario):
        """Only the most recent turns are used as context."""
        for indice in range(6):
            ConversationTurn.objects.create(
                user=usuario,
                question=f"Pergunta {indice}",
                answer=f"Resposta {indice}",
                sources=[],
            )

        with patch("knowledge.views.answer_from_documents", return_value=RESULTADO) as service:
            cliente.post(url, {"question": "Mais uma pergunta"})

        assert len(service.call_args.kwargs["history"]) == 3

    def test_history_is_per_user(self, cliente, url, usuario, db):
        """One user never sees another user's history."""
        outro = User.objects.create_user(username="outro", password="senha-forte-123")
        ConversationTurn.objects.create(
            user=outro, question="Pergunta alheia", answer="Resposta", sources=[]
        )

        response = cliente.get(url)

        assert list(response.context["history"]) == []

    def test_history_appears_on_the_page(self, cliente, url, usuario):
        """Past questions are rendered."""
        ConversationTurn.objects.create(
            user=usuario, question="Qual a antecedência?", answer="30 dias.", sources=[]
        )

        response = cliente.get(url)

        assert "Qual a antecedência?" in response.content.decode()

    def test_failed_question_is_not_persisted(self, cliente, url, usuario):
        """A failed call leaves no turn behind."""
        with patch(
            "knowledge.views.answer_from_documents",
            side_effect=AIServiceError("indisponível"),
        ):
            cliente.post(url, {"question": "Qual a regra?"})

        assert ConversationTurn.objects.count() == 0

    def test_build_history_orders_oldest_first(self, usuario):
        """The preamble reads chronologically, though the queryset is newest first."""
        recentes = [
            ConversationTurn(user=usuario, question="Segunda", answer="B"),
            ConversationTurn(user=usuario, question="Primeira", answer="A"),
        ]

        texto = _build_history(recentes)

        assert texto.index("Primeira") < texto.index("Segunda")

    def test_build_history_empty_without_turns(self):
        """No history yields no preamble."""
        assert _build_history([]) == ""
        assert _build_history(None) == ""

    def test_history_reaches_the_prompt(self, db, usuario):
        """Follow-ups are rewritten for retrieval, then the answer uses history."""
        anterior = ConversationTurn(
            user=usuario, question="Quanto custa na UFBA?", answer="R$ 1.200,00."
        )
        recuperados = [object()]

        with (
            patch(
                "ai_assistant.services.rewrite_followup_question",
                return_value="Quanto custa o auditório na UFS?",
            ) as rewrite,
            patch(
                "ai_assistant.services.retrieval.search",
                return_value=recuperados,
            ) as search,
            patch(
                "ai_assistant.services._run_text_completion",
                return_value="Na UFS a taxa é R$ 800,00 [1].",
            ) as completion,
            patch(
                "ai_assistant.services._build_context",
                return_value="[1] UFS — Regimento\nTaxa de R$ 800,00.",
            ),
        ):
            resultado = answer_from_documents("E na UFS?", history=[anterior])

        rewrite.assert_called_once_with("E na UFS?", [anterior])
        search.assert_called_once_with("Quanto custa o auditório na UFS?", None, hybrid=True)
        prompt = completion.call_args[0][1]
        assert "E na UFS?" in prompt
        assert "Quanto custa na UFBA?" in prompt
        assert resultado["used_context"] is True

    def test_followup_rewrite_falls_back_on_llm_failure(self, usuario):
        """If rewrite fails, retrieval uses the previous question plus the follow-up."""
        from ai_assistant.services import rewrite_followup_question

        anterior = ConversationTurn(
            user=usuario, question="Quanto custa na UFBA?", answer="R$ 1.200,00."
        )

        with patch(
            "ai_assistant.services._run_text_completion",
            side_effect=AIServiceError("indisponível"),
        ):
            reescrita = rewrite_followup_question("E na UFS?", [anterior])

        assert reescrita == "Quanto custa na UFBA? E na UFS?"

    def test_followup_without_history_keeps_original_question(self):
        """A first question is searched as-is."""
        from ai_assistant.services import rewrite_followup_question

        assert rewrite_followup_question("Qual a antecedência?", None) == "Qual a antecedência?"
        assert rewrite_followup_question("Qual a antecedência?", []) == "Qual a antecedência?"


class TestAutomaticEvaluation:
    """Tests for the LLM-as-a-judge evaluation."""

    def test_judge_returns_scores_and_average(self):
        """A verdict is converted into per-criterion scores plus the mean."""
        veredito = {
            "fundamentacao": 5,
            "completude": 4,
            "citacao": 3,
            "justificativa": "Boa fundamentação.",
        }

        with patch("ai_assistant.evaluation._run_json_completion", return_value=veredito):
            notas = evaluation.judge_answer("Pergunta", "Resposta", RESULTADO["sources"])

        assert notas["fundamentacao"] == 5
        assert notas["media"] == 4.0
        assert notas["justificativa"] == "Boa fundamentação."

    def test_scores_are_clamped_to_the_scale(self):
        """A judge returning out-of-range values does not corrupt the aggregate."""
        veredito = {"fundamentacao": 9, "completude": -2, "citacao": "4"}

        with patch("ai_assistant.evaluation._run_json_completion", return_value=veredito):
            notas = evaluation.judge_answer("Pergunta", "Resposta", [])

        assert notas["fundamentacao"] == evaluation.MAX_SCORE
        assert notas["completude"] == 0
        assert notas["citacao"] == 4

    def test_unreadable_score_raises(self):
        """A verdict that is not numeric at all is an error, not a silent zero."""
        veredito = {"fundamentacao": "ótimo", "completude": 4, "citacao": 4}

        with patch("ai_assistant.evaluation._run_json_completion", return_value=veredito):
            with pytest.raises(AIServiceError, match="Nota inválida"):
                evaluation.judge_answer("Pergunta", "Resposta", [])

    def test_judge_receives_question_answer_and_excerpts(self):
        """The judge prompt carries everything it needs to score groundedness."""
        veredito = {"fundamentacao": 5, "completude": 5, "citacao": 5}

        with patch("ai_assistant.evaluation._run_json_completion", return_value=veredito) as judge:
            evaluation.judge_answer("Quanto custa?", "R$ 1.200,00 [1].", RESULTADO["sources"])

        _, prompt = judge.call_args[0]
        assert "Quanto custa?" in prompt
        assert "R$ 1.200,00 [1]." in prompt
        assert "UFBA - IMS" in prompt

    def test_summarise_averages_across_questions(self):
        """The summary averages each criterion and then the criteria."""
        resultados = [
            {"fundamentacao": 5, "completude": 5, "citacao": 5},
            {"fundamentacao": 3, "completude": 3, "citacao": 3},
        ]

        resumo = evaluation.summarise(resultados)

        assert resumo["fundamentacao"] == 4.0
        assert resumo["media"] == 4.0

    def test_summarise_handles_empty_input(self):
        """No results yields zeros rather than a division error."""
        resumo = evaluation.summarise([])

        assert resumo["media"] == 0.0
