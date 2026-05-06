from django.test import TestCase


class SmokeTestCase(TestCase):
    """Basic smoke test to verify Django and pytest integration."""

    def test_settings_loaded(self):
        """Verify that Django settings module is loaded."""
        from django.conf import settings

        self.assertTrue(settings.DEBUG is not None)
