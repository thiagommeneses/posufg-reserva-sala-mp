"""Enumerations and status groupings for the reservations app.

Kept in a dedicated module (instead of ``reservations.models``) so that
``reservations.validators`` can be imported by the models themselves without
creating a circular import.
"""

from django.db import models


class ReservationStatus(models.TextChoices):
    """Status choices for a reservation."""

    CONFIRMED = "confirmed", "Confirmed"
    CANCELLED = "cancelled", "Cancelled"
    CHECKED_IN = "checked_in", "Checked In"
    COMPLETED = "completed", "Completed"
    NO_SHOW = "no_show", "No Show"


#: Statuses that still hold the space: only these block a time slot.
ACTIVE_RESERVATION_STATUSES = (
    ReservationStatus.CONFIRMED,
    ReservationStatus.CHECKED_IN,
)
