"""App configuration for the spaces app."""

from django.apps import AppConfig


class SpacesConfig(AppConfig):
    """Configuration for the spaces app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "spaces"

    def ready(self):
        """Register the signal handlers that clean up orphan media files."""
        from spaces import signals  # noqa: F401
