"""App configuration for the services app."""

from django.apps import AppConfig


class ServicesConfig(AppConfig):
    """Configuration for the services app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "services"
    verbose_name = "Serviços"
