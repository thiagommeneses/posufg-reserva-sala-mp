"""Serializers for the reservations app.

Business rules live in :mod:`reservations.validators` and
:mod:`reservations.services`. The serializers below only translate domain
errors into the field-level errors expected by the API.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from reservations.models import MaintenanceBlock, Reservation
from reservations.services import create_reservation
from reservations.validators import (
    INVALID_TIME_RANGE_CODE,
    SPACE_INACTIVE_CODE,
    validate_maintenance_slot,
    validate_reservation_slot,
)
from spaces.models import Space

#: Maps a domain error code to the API field that should carry the message.
#: Anything not listed here is reported as a non-field error.
ERROR_CODE_TO_FIELD = {
    SPACE_INACTIVE_CODE: "space",
    INVALID_TIME_RANGE_CODE: "end_time",
}


def _as_drf_error(exc: DjangoValidationError) -> serializers.ValidationError:
    """Convert a domain ValidationError into a DRF one, keyed by field.

    Args:
        exc: The error raised by the validators or the service layer.

    Returns:
        serializers.ValidationError: The equivalent DRF error.
    """
    field = ERROR_CODE_TO_FIELD.get(getattr(exc, "code", None), "non_field_errors")
    return serializers.ValidationError({field: exc.messages})


class MaintenanceBlockSerializer(serializers.ModelSerializer):
    """Serializer for the MaintenanceBlock model with overlap validation."""

    space = serializers.PrimaryKeyRelatedField(queryset=Space.objects.all())
    created_by = serializers.PrimaryKeyRelatedField(
        read_only=True,
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        """Meta options for MaintenanceBlockSerializer."""

        model = MaintenanceBlock
        fields = [
            "id",
            "space",
            "start_time",
            "end_time",
            "reason",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def validate(self, data):
        """Validate maintenance block data for conflicts."""
        try:
            validate_maintenance_slot(data["space"], data["start_time"], data["end_time"])
        except DjangoValidationError as exc:
            raise _as_drf_error(exc) from exc
        return data


class ReservationSerializer(serializers.ModelSerializer):
    """Serializer for the Reservation model with conflict validation."""

    space = serializers.PrimaryKeyRelatedField(queryset=Space.objects.all())
    user = serializers.PrimaryKeyRelatedField(
        read_only=True,
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        """Meta options for ReservationSerializer."""

        model = Reservation
        fields = [
            "id",
            "space",
            "user",
            "start_time",
            "end_time",
            "status",
            "checked_in_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "checked_in_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """Validate reservation data for conflicts."""
        try:
            validate_reservation_slot(data["space"], data["start_time"], data["end_time"])
        except DjangoValidationError as exc:
            raise _as_drf_error(exc) from exc
        return data

    def create(self, validated_data):
        """Create the reservation through the service layer.

        Keeps a single write path shared with the web interface, including the
        transaction and the database-level protection against race conditions.
        """
        try:
            return create_reservation(
                user=validated_data["user"],
                space=validated_data["space"],
                start_time=validated_data["start_time"],
                end_time=validated_data["end_time"],
            )
        except DjangoValidationError as exc:
            raise _as_drf_error(exc) from exc
