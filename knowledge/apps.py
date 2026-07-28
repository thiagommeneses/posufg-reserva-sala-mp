"""App configuration for the knowledge app."""

from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    """Configuration for the knowledge app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge"
    verbose_name = "Base de conhecimento"
