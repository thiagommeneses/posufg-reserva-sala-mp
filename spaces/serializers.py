"""Serializers for the spaces app."""

from rest_framework import serializers

from core.serializers import utc_datetime_field_mapping

from .models import Attribute, Space


class AttributeSerializer(serializers.ModelSerializer):
    """Serializer for the Attribute model."""

    class Meta:
        """Meta options for AttributeSerializer."""

        model = Attribute
        fields = ["id", "name"]


class SpaceSerializer(serializers.ModelSerializer):
    """Serializer for the Space model, including nested attribute names."""

    serializer_field_mapping = utc_datetime_field_mapping(
        serializers.ModelSerializer.serializer_field_mapping
    )

    attributes = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    space_type = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    # ``read_only`` não é cosmético aqui: um campo gravável com source pontilhado
    # faz o ``ModelSerializer.create`` recusar o POST inteiro. O nome do tipo é
    # conveniência de leitura; quem escreve usa a tela administrativa.
    space_type_name = serializers.CharField(source="space_type.name", read_only=True, default=None)

    class Meta:
        """Meta options for SpaceSerializer."""

        model = Space
        fields = [
            "id",
            "name",
            "description",
            "capacity",
            "location",
            "is_active",
            "space_type",
            "space_type_name",
            "cover_image_url",
            "created_at",
            "updated_at",
            "attributes",
        ]

    def get_attributes(self, obj: Space) -> list[str]:
        """Return a list of attribute names linked to this space."""
        return [sa.attribute.name for sa in obj.space_attributes.select_related("attribute").all()]

    def get_cover_image_url(self, obj: Space) -> str | None:
        """Return the absolute URL of the cover image, or ``None`` when absent.

        A URL é absoluta para que um cliente fora do mesmo host consiga usá-la;
        ``None`` deixa a decisão de fallback com quem consome, em vez de
        devolver o caminho de um arquivo que não existe.
        """
        if not obj.cover_image:
            return None
        url = obj.cover_image.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url
