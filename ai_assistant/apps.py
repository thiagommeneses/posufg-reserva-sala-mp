"""App configuration for the ai_assistant app."""

from django.apps import AppConfig


class AiAssistantConfig(AppConfig):
    """Configuration for the ai_assistant app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_assistant"
    verbose_name = "Assistente de IA"
