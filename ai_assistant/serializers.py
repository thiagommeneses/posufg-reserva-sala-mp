"""Serializers for the ai_assistant app."""

from rest_framework import serializers

from spaces.serializers import SpaceSerializer


class RoomSearchRequestSerializer(serializers.Serializer):
    """Input serializer for the natural-language room search endpoint."""

    query = serializers.CharField(
        min_length=3,
        max_length=500,
        trim_whitespace=True,
        help_text="Pedido em linguagem natural, ex.: 'sala para 8 pessoas com projetor'.",
    )

    class Meta:
        """Meta options for RoomSearchRequestSerializer."""

        fields = ["query"]


class RoomSearchResponseSerializer(serializers.Serializer):
    """Output serializer for the natural-language room search endpoint."""

    summary = serializers.CharField()
    filters = serializers.DictField()
    results = SpaceSerializer(many=True)

    class Meta:
        """Meta options for RoomSearchResponseSerializer."""

        fields = ["summary", "filters", "results"]


class MaintenanceClassifyRequestSerializer(serializers.Serializer):
    """Input serializer for the maintenance reason classification endpoint."""

    reason = serializers.CharField(
        min_length=3,
        max_length=255,
        trim_whitespace=True,
        help_text="Texto livre descrevendo o motivo do bloqueio de manutenção.",
    )

    class Meta:
        """Meta options for MaintenanceClassifyRequestSerializer."""

        fields = ["reason"]


class MaintenanceClassifyResponseSerializer(serializers.Serializer):
    """Output serializer for the maintenance reason classification endpoint."""

    category = serializers.CharField()
    confidence = serializers.CharField()
    justification = serializers.CharField()

    class Meta:
        """Meta options for MaintenanceClassifyResponseSerializer."""

        fields = ["category", "confidence", "justification"]
