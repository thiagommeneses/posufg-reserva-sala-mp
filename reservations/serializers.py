"""Serializers for the reservations app."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import serializers

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
from spaces.models import Space


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
        space = data["space"]
        start_time = data["start_time"]
        end_time = data["end_time"]

        if end_time <= start_time:
            raise serializers.ValidationError(
                {"end_time": "End time must be after start time."},
            )

        overlapping_reservations = Reservation.objects.filter(
            space=space,
            status__in=[
                ReservationStatus.CONFIRMED,
                ReservationStatus.CHECKED_IN,
            ],
        ).filter(
            Q(start_time__lt=end_time) & Q(end_time__gt=start_time),
        )
        if overlapping_reservations.exists():
            raise serializers.ValidationError(
                {
                    "non_field_errors": (
                        "This maintenance block overlaps with an existing reservation."
                    ),
                },
            )

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
        space = data["space"]
        start_time = data["start_time"]
        end_time = data["end_time"]

        if not space.is_active:
            raise serializers.ValidationError(
                {"space": "This space is not available for reservations."},
            )

        if end_time <= start_time:
            raise serializers.ValidationError(
                {"end_time": "End time must be after start time."},
            )

        # Check overlapping confirmed/checked_in reservations
        overlapping_reservations = Reservation.objects.filter(
            space=space,
            status__in=[
                ReservationStatus.CONFIRMED,
                ReservationStatus.CHECKED_IN,
            ],
        ).filter(
            Q(start_time__lt=end_time) & Q(end_time__gt=start_time),
        )
        if overlapping_reservations.exists():
            raise serializers.ValidationError(
                {"non_field_errors": "This time slot overlaps with an existing reservation."},
            )

        # Check overlapping maintenance blocks
        overlapping_blocks = MaintenanceBlock.objects.filter(
            space=space,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if overlapping_blocks.exists():
            raise serializers.ValidationError(
                {"non_field_errors": "This time slot overlaps with a maintenance block."},
            )

        return data

    def create(self, validated_data):
        """Create a reservation with confirmed status."""
        validated_data["status"] = ReservationStatus.CONFIRMED
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"non_field_errors": "This time slot overlaps with an existing reservation."}
            ) from exc
