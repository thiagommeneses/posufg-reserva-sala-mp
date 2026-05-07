"""Serializers for the spaces app."""

from rest_framework import serializers

from .models import Attribute, Space


class AttributeSerializer(serializers.ModelSerializer):
    """Serializer for the Attribute model."""

    class Meta:
        """Meta options for AttributeSerializer."""

        model = Attribute
        fields = ["id", "name"]


class SpaceSerializer(serializers.ModelSerializer):
    """Serializer for the Space model, including nested attribute names."""

    attributes = serializers.SerializerMethodField()

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
            "created_at",
            "updated_at",
            "attributes",
        ]

    def get_attributes(self, obj: Space) -> list[str]:
        """Return a list of attribute names linked to this space."""
        return [sa.attribute.name for sa in obj.space_attributes.select_related("attribute").all()]
