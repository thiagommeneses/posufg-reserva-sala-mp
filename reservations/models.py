"""Models for the reservations app."""

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.fields.ranges import RangeOperators
from django.db import models
from django.db.models import F, Func, Q

from reservations.enums import ACTIVE_RESERVATION_STATUSES, ReservationStatus
from reservations.validators import (
    validate_maintenance_slot,
    validate_no_reservation_overlap,
    validate_time_range,
)

__all__ = [
    "ACTIVE_RESERVATION_STATUSES",
    "MaintenanceBlock",
    "Reservation",
    "ReservationStatus",
    "TstzRange",
]


class TstzRange(Func):
    """PostgreSQL tstzrange function for exclusion constraints."""

    function = "tstzrange"
    output_field = DateTimeRangeField()


class Reservation(models.Model):
    """A reservation of a space by a user for a specific time slot."""

    space = models.ForeignKey(
        "spaces.Space",
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus,
        default=ReservationStatus.CONFIRMED,
    )
    checked_in_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Reservation."""

        ordering = ["-start_time"]
        constraints = [
            ExclusionConstraint(
                name="exclude_overlapping_reservations",
                expressions=[
                    (F("space"), RangeOperators.EQUAL),
                    (TstzRange(F("start_time"), F("end_time")), RangeOperators.OVERLAPS),
                ],
                condition=Q(
                    status__in=[
                        ReservationStatus.CONFIRMED,
                        ReservationStatus.CHECKED_IN,
                    ],
                ),
            ),
        ]

    def __str__(self):
        """Return a human-readable description of the reservation."""
        return f"{self.space.name} — {self.start_time} to {self.end_time}"

    def clean(self):
        """Validate the reservation data.

        Delegates to :mod:`reservations.validators` so the rules stay identical
        to the ones applied by the service layer and by the API serializers.
        """
        super().clean()
        validate_time_range(self.start_time, self.end_time)

        if self.status in ACTIVE_RESERVATION_STATUSES:
            validate_no_reservation_overlap(
                self.space,
                self.start_time,
                self.end_time,
                exclude_pk=self.pk,
            )


class MaintenanceBlock(models.Model):
    """A maintenance block that prevents reservations for a space."""

    space = models.ForeignKey(
        "spaces.Space",
        on_delete=models.CASCADE,
        related_name="maintenance_blocks",
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    reason = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="maintenance_blocks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for MaintenanceBlock."""

        ordering = ["-start_time"]

    def __str__(self):
        """Return a human-readable description of the block."""
        return f"{self.space.name} — {self.reason} ({self.start_time} to {self.end_time})"

    def clean(self):
        """Validate the maintenance block data."""
        super().clean()
        validate_maintenance_slot(self.space, self.start_time, self.end_time)
