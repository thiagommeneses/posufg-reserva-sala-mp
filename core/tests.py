"""Core application tests."""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from reservations.models import Reservation, ReservationStatus
from reservations.services import (
    auto_release_no_shows,
    check_in_reservation,
    create_reservation,
    get_availability_for_date,
)
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


@pytest.mark.django_db
class TestReservationLifecycleIntegration:
    """End-to-end integration tests for the reservation lifecycle."""

    def test_full_lifecycle_create_search_reserve_checkin(self, client):
        """Cover full lifecycle: create space, search by attributes, reserve, check-in."""
        attr = Attribute.objects.create(name="Projetor")
        space = Space.objects.create(
            name="Sala Integração",
            capacity=10,
            location="Térreo",
            is_active=True,
        )
        space.space_attributes.create(attribute=attr)

        user = User.objects.create_user(username="lifecycle_user", password="testpass123")
        client.login(username="lifecycle_user", password="testpass123")

        # Search spaces by attribute
        response = client.get("/spaces/", {"attributes": attr.name})
        assert response.status_code == 200
        spaces = response.context["spaces"]
        assert space in list(spaces)

        # Create reservation via API (start within check-in window)
        now = timezone.now()
        start = now - timezone.timedelta(minutes=5)
        end = now + timezone.timedelta(hours=1)
        response = client.post(
            "/api/reservations/",
            {
                "space": space.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        reservation = Reservation.objects.get(pk=response.json()["id"])
        assert reservation.status == ReservationStatus.CONFIRMED

        # Check-in to reservation
        check_in_reservation(reservation, user)
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CHECKED_IN
        assert reservation.checked_in_at is not None

    def test_no_show_flow_auto_releases_slot(self):
        """Overdue reservation without check-in is marked no_show and slot frees up."""
        space = Space.objects.create(
            name="Sala No-show", capacity=5, location="1º andar", is_active=True
        )
        user = User.objects.create_user(username="noshow_user", password="testpass123")

        now = timezone.now()
        start = now - timezone.timedelta(hours=2)
        end = now - timezone.timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CONFIRMED,
        )

        # Verify slot is occupied before auto-release
        availability = get_availability_for_date(space, start.date())
        assert len(availability["occupied"]) > 0

        # Run auto-release
        released = auto_release_no_shows(threshold_minutes=15)
        assert released == 1

        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.NO_SHOW

        # Verify slot is now available
        availability = get_availability_for_date(space, start.date())
        assert len(availability["occupied"]) == 0

    def test_conflict_prevention_two_users_same_slot(self):
        """Two users trying to book the same slot: second one is rejected."""
        space = Space.objects.create(
            name="Sala Conflito", capacity=5, location="2º andar", is_active=True
        )
        user1 = User.objects.create_user(username="user1", password="testpass123")
        user2 = User.objects.create_user(username="user2", password="testpass123")

        now = timezone.now()
        start = now + timezone.timedelta(hours=1)
        end = now + timezone.timedelta(hours=2)

        # User 1 books successfully
        res1 = create_reservation(user1, space, start, end)
        assert res1.status == ReservationStatus.CONFIRMED

        # User 2 tries to book the same slot and is rejected
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            create_reservation(user2, space, start, end)

    def test_cancel_and_rebook_frees_slot(self):
        """User cancels reservation, then another user successfully books the same slot."""
        space = Space.objects.create(
            name="Sala Rebook", capacity=5, location="3º andar", is_active=True
        )
        user1 = User.objects.create_user(username="canceler", password="testpass123")
        user2 = User.objects.create_user(username="rebooker", password="testpass123")

        now = timezone.now()
        start = now + timezone.timedelta(hours=1)
        end = now + timezone.timedelta(hours=2)

        # User 1 creates reservation
        reservation = create_reservation(user1, space, start, end)
        assert Reservation.objects.filter(pk=reservation.pk).exists()

        # User 1 cancels reservation
        from reservations.services import cancel_reservation

        cancel_reservation(reservation, user1)
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED

        # User 2 books the now-free slot
        res2 = create_reservation(user2, space, start, end)
        assert res2.status == ReservationStatus.CONFIRMED
        assert res2.pk != reservation.pk
