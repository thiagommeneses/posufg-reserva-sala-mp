"""Views exposing AI-assisted features backed by an LLM (Groq).

Two independent AI operations are exposed here:

1. :class:`RoomSearchAssistantView` — extraction/interpretation: converts a
   natural-language request into structured search filters and queries real
   spaces in the database.
2. :class:`MaintenanceReasonClassifierView` — text classification: assigns a
   free-text maintenance reason to a fixed category.
"""

import logging

from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_assistant.exceptions import AIServiceError
from ai_assistant.serializers import (
    MaintenanceClassifyRequestSerializer,
    MaintenanceClassifyResponseSerializer,
    RoomSearchRequestSerializer,
    RoomSearchResponseSerializer,
)
from ai_assistant.services import classify_maintenance_reason, extract_room_search_filters
from spaces.models import Space

logger = logging.getLogger(__name__)

MAX_SEARCH_RESULTS = 10


class RoomSearchAssistantView(APIView):
    """Suggests available spaces from a natural-language request (LLM-powered)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Interpret a natural-language room request and return matching spaces."""
        request_serializer = RoomSearchRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        query = request_serializer.validated_data["query"]

        try:
            filters = extract_room_search_filters(query)
        except AIServiceError as exc:
            logger.warning("Falha no serviço de IA de busca de salas: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        queryset = Space.objects.filter(is_active=True).prefetch_related(
            "space_attributes__attribute",
        )
        if filters["min_capacity"]:
            queryset = queryset.filter(capacity__gte=filters["min_capacity"])
        if filters["location"]:
            queryset = queryset.filter(location__icontains=filters["location"])
        for attribute_name in filters["attributes"]:
            queryset = queryset.filter(
                space_attributes__attribute__name__icontains=attribute_name,
            )
        queryset = queryset.distinct()[:MAX_SEARCH_RESULTS]

        response_serializer = RoomSearchResponseSerializer(
            {
                "summary": filters["summary"],
                "filters": filters,
                "results": queryset,
            },
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class MaintenanceReasonClassifierView(APIView):
    """Classifies a free-text maintenance block reason into a fixed category (LLM-powered)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Classify a free-text maintenance reason into a fixed category via LLM."""
        request_serializer = MaintenanceClassifyRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        reason = request_serializer.validated_data["reason"]

        try:
            classification = classify_maintenance_reason(reason)
        except AIServiceError as exc:
            logger.warning("Falha no serviço de IA de classificação de manutenção: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        response_serializer = MaintenanceClassifyResponseSerializer(classification)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
