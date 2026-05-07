"""Models for the reservations app."""

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.fields.ranges import RangeOperators
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Func, Q


class TstzRange(Func):
    """PostgreSQL tstzrange function for exclusion constraints."""

    function = "tstzrange"
    output_field = DateTimeRangeField()


class ReservationStatus(models.TextChoices):
    """Status choices for a reservation."""

    CONFIRMED = "confirmed", "Confirmed"
    CANCELLED = "cancelled", "Cancelled"
    CHECKED_IN = "checked_in", "Checked In"
    COMPLETED = "completed", "Completed"
    NO_SHOW = "no_show", "No Show"


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
        """Validate the reservation data."""
        super().clean()
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")

        if self.status not in {
            ReservationStatus.CANCELLED,
            ReservationStatus.COMPLETED,
            ReservationStatus.NO_SHOW,
        }:
            overlapping = (
                Reservation.objects.filter(
                    space=self.space,
                    status__in=[
                        ReservationStatus.CONFIRMED,
                        ReservationStatus.CHECKED_IN,
                    ],
                )
                .exclude(pk=self.pk)
                .filter(
                    models.Q(start_time__lt=self.end_time) & models.Q(end_time__gt=self.start_time),
                )
            )
            if overlapping.exists():
                raise ValidationError(
                    "This time slot overlaps with an existing reservation.",
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
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")

        overlapping_reservations = Reservation.objects.filter(
            space=self.space,
            status__in=[
                ReservationStatus.CONFIRMED,
                ReservationStatus.CHECKED_IN,
            ],
        ).filter(
            models.Q(start_time__lt=self.end_time) & models.Q(end_time__gt=self.start_time),
        )
        if overlapping_reservations.exists():
            raise ValidationError(
                "This maintenance block overlaps with an existing reservation.",
            )
