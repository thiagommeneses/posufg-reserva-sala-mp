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


class DocumentQARequestSerializer(serializers.Serializer):
    """Input serializer for the document question-answering endpoint."""

    question = serializers.CharField(
        min_length=5,
        max_length=500,
        trim_whitespace=True,
        help_text="Pergunta em linguagem natural sobre as normas de uso de espaços.",
    )
    top_k = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        help_text="Quantos trechos recuperar. Padrão: RAG_TOP_K.",
    )
    hybrid = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Combina busca semântica e lexical. Desligue para comparar as duas.",
    )

    class Meta:
        """Meta options for DocumentQARequestSerializer."""

        fields = ["question", "top_k", "hybrid"]


class DocumentSourceSerializer(serializers.Serializer):
    """A passage used to ground the answer."""

    position = serializers.IntegerField()
    institution = serializers.CharField()
    document = serializers.CharField()
    url = serializers.URLField()
    excerpt = serializers.CharField()
    score = serializers.FloatField()

    class Meta:
        """Meta options for DocumentSourceSerializer."""

        fields = ["position", "institution", "document", "url", "excerpt", "score"]


class DocumentQAResponseSerializer(serializers.Serializer):
    """Output serializer for the document question-answering endpoint."""

    answer = serializers.CharField()
    sources = DocumentSourceSerializer(many=True)
    used_context = serializers.BooleanField()

    class Meta:
        """Meta options for DocumentQAResponseSerializer."""

        fields = ["answer", "sources", "used_context"]
