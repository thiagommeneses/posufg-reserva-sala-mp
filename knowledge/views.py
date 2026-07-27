"""Web views for the document assistant.

The page lives here rather than in ``ai_assistant`` so that app stays what it is: the
boundary with the LLM provider, exposed only as services and API endpoints. This view
consumes that boundary the same way ``spaces.views.SpaceListView`` does for the
natural-language room search.
"""

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from ai_assistant.exceptions import AIServiceError
from ai_assistant.services import answer_from_documents
from knowledge.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

TEMPLATE = "knowledge/assistant.html"
ANSWER_PARTIAL = "knowledge/_assistant_answer.html"

MIN_QUESTION_LENGTH = 5

SUGGESTED_QUESTIONS = [
    "Quais instituições cobram taxa pelo uso do auditório e quanto?",
    "Com quanta antecedência devo solicitar a reserva de um auditório?",
    "Uma empresa privada pode usar o auditório para um evento comercial?",
    "É permitido consumir alimentos e bebidas dentro do auditório?",
    "Que penalidades se aplicam a quem descumpre o regulamento?",
]


class DocumentAssistantView(LoginRequiredMixin, View):
    """Natural-language consultation over the indexed corpus of norms."""

    def get(self, request):
        """Render the consultation page with the corpus summary."""
        return render(request, TEMPLATE, self._base_context())

    def post(self, request):
        """Answer a question and return the answer partial (HTMX)."""
        question = request.POST.get("question", "").strip()

        if len(question) < MIN_QUESTION_LENGTH:
            return render(
                request,
                ANSWER_PARTIAL,
                {"error": "Escreva uma pergunta com pelo menos 5 caracteres."},
            )

        try:
            result = answer_from_documents(question)
        except AIServiceError as exc:
            logger.warning("Falha na consulta documental via web: %s", exc)
            return render(request, ANSWER_PARTIAL, {"error": str(exc)})

        return render(request, ANSWER_PARTIAL, {"result": result, "question": question})

    def _base_context(self) -> dict:
        """Return the corpus statistics shown alongside the search box."""
        return {
            "suggested_questions": SUGGESTED_QUESTIONS,
            "document_count": Document.objects.filter(indexed_at__isnull=False).count(),
            "chunk_count": DocumentChunk.objects.count(),
            "institution_count": (
                Document.objects.filter(indexed_at__isnull=False)
                .values("institution")
                .distinct()
                .count()
            ),
        }
