"""App configuration for the reservations app."""

from django.apps import AppConfig


class ReservationsConfig(AppConfig):
    """Configuration for the reservations app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "reservations"
