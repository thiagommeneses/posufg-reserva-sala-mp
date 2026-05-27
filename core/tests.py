"""Core application tests."""

from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from spaces.models import Attribute, Space


class SmokeTestCase(TestCase):
    """Basic smoke test to verify Django and pytest integration."""

    def test_settings_loaded(self):
        """Verify that Django settings module is loaded."""
        from django.conf import settings

        assert settings.DEBUG is not None


class TemplateInfrastructureTestCase(TestCase):
    """Tests for template infrastructure, HTMX, DaisyUI, and Tailwind setup."""

    def test_base_template_contains_tailwind_cdn(self):
        """Verify base.html includes Tailwind CSS CDN."""
        response = self.client.get(reverse("htmx_test"))
        self.assertContains(response, "cdn.tailwindcss.com")

    def test_base_template_contains_daisyui_cdn(self):
        """Verify base.html includes DaisyUI CDN."""
        response = self.client.get(reverse("htmx_test"))
        self.assertContains(response, "daisyui")

    def test_base_template_contains_htmx_cdn(self):
        """Verify base.html includes HTMX CDN."""
        response = self.client.get(reverse("htmx_test"))
        self.assertContains(response, "htmx.org")

    def test_base_template_has_theme_attribute(self):
        """Verify base.html has DaisyUI theme data-theme attribute."""
        response = self.client.get(reverse("htmx_test"))
        self.assertContains(response, 'data-theme="light"')

    def test_htmx_test_view_returns_full_page(self):
        """Verify HTMX test view returns full HTML page for regular requests."""
        response = self.client.get(reverse("htmx_test"))
        assert response.status_code == 200
        assert "<html" in response.content.decode()
        assert "HTMX Test Page" in response.content.decode()

    def test_htmx_test_view_returns_partial(self):
        """Verify HTMX test view returns partial for HX-Request header."""
        response = self.client.get(
            reverse("htmx_test"),
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert "<html" not in response.content.decode()
        assert "HTMX partial swap works!" in response.content.decode()
        assert 'id="htmx-test-target"' in response.content.decode()

    def test_base_user_template_renders_navbar(self):
        """Verify base_user.html contains expected navbar elements."""
        from django.template.loader import render_to_string

        html = render_to_string("base_user.html", {})
        assert "Reserva de Espaços" in html
        assert "Espaços" in html
        assert "Minhas Reservas" in html
        assert "Sair" in html
        assert "navbar" in html
        assert "drawer" in html

    def test_base_admin_template_renders_sidebar(self):
        """Verify base_admin.html contains expected sidebar elements."""
        from django.template.loader import render_to_string

        html = render_to_string("base_admin.html", {})
        assert "Admin Dashboard" in html
        assert "Dashboard" in html
        assert "Espaços" in html
        assert "Reservas" in html
        assert "Manutenção" in html
        assert "drawer" in html
        assert "menu-title" in html

    def test_messages_partial_renders_alerts(self):
        """Verify messages partial renders DaisyUI alerts."""
        from django.contrib.messages import constants
        from django.contrib.messages.storage.base import Message
        from django.template.loader import render_to_string

        messages = [
            Message(constants.SUCCESS, "Operation successful"),
            Message(constants.ERROR, "Something went wrong"),
        ]
        html = render_to_string("partials/_messages.html", {"messages": messages})
        assert "alert-success" in html
        assert "alert-error" in html
        assert "Operation successful" in html
        assert "Something went wrong" in html


class SeedDataCommandTestCase(TestCase):
    """Tests for the seed_data management command."""

    def test_command_runs_successfully(self):
        """Verify seed_data command completes without errors."""
        out = StringIO()
        call_command("seed_data", stdout=out)
        output = out.getvalue()
        assert "Database seeding completed successfully!" in output

    def test_command_is_idempotent(self):
        """Verify running seed_data twice does not duplicate records."""
        call_command("seed_data")
        attr_count_first = Attribute.objects.count()
        space_count_first = Space.objects.count()
        user_count_first = User.objects.count()

        call_command("seed_data")
        attr_count_second = Attribute.objects.count()
        space_count_second = Space.objects.count()
        user_count_second = User.objects.count()

        assert attr_count_first == attr_count_second
        assert space_count_first == space_count_second
        assert user_count_first == user_count_second

    def test_flush_flag_removes_and_recreates(self):
        """Verify --flush removes seed data and recreates it."""
        call_command("seed_data")
        assert Attribute.objects.count() == 7
        assert Space.objects.count() == 5
        assert User.objects.filter(username="admin").exists()

        call_command("seed_data", flush=True)
        assert Attribute.objects.count() == 7
        assert Space.objects.count() == 5
        assert User.objects.filter(username="admin").exists()

    def test_command_creates_portuguese_content(self):
        """Verify seeded content is in Portuguese (pt-BR)."""
        call_command("seed_data")

        assert Attribute.objects.filter(name="Ar-condicionado").exists()
        assert Attribute.objects.filter(name="Videoconferência").exists()
        assert Space.objects.filter(name="Sala de Reunião Alfa").exists()
        assert Space.objects.filter(location="Térreo").exists()
