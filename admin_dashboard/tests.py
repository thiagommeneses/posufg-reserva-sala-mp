"""Tests for the admin dashboard app."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
from spaces.models import Space

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff test user."""
    return User.objects.create_user(
        username="staffuser",
        email="staff@example.com",
        password="staffpass123",
        is_staff=True,
    )


@pytest.fixture
def non_staff_user(db):
    """Create a non-staff test user."""
    return User.objects.create_user(
        username="regular",
        email="regular@example.com",
        password="regularpass123",
    )


@pytest.fixture
def dashboard_space(db):
    """Create a test space for dashboard tests."""
    return Space.objects.create(
        name="Dashboard Room",
        capacity=10,
        location="Floor 1",
        is_active=True,
    )


@pytest.mark.django_db
class TestAdminDashboardView:
    """Tests for the admin dashboard view."""

    def test_staff_user_gets_200(self, client, staff_user):
        """Staff users should be able to access the admin dashboard."""
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/")
        assert response.status_code == 200
        assert "admin_dashboard/index.html" in [t.name for t in response.templates]

    def test_non_staff_user_gets_403(self, client, non_staff_user):
        """Non-staff users should be forbidden from accessing the admin dashboard."""
        client.force_login(non_staff_user)
        response = client.get("/admin-dashboard/")
        assert response.status_code == 403

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Unauthenticated users should be redirected to login."""
        response = client.get("/admin-dashboard/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_context_contains_total_spaces(self, client, staff_user, dashboard_space):
        """Context should include total spaces count."""
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/")
        assert response.status_code == 200
        assert response.context["total_spaces"] == 1

    def test_context_contains_occupied_now(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Context should reflect occupied spaces from active reservations."""
        now = timezone.now()
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now - timezone.timedelta(minutes=30),
            end_time=now + timezone.timedelta(minutes=30),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/")
        assert response.status_code == 200
        assert response.context["occupied_now"] == 1
        assert response.context["available_now"] == 0

    def test_context_contains_maintenance_now(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Context should reflect spaces under maintenance."""
        now = timezone.now()
        MaintenanceBlock.objects.create(
            space=dashboard_space,
            start_time=now - timezone.timedelta(minutes=30),
            end_time=now + timezone.timedelta(minutes=30),
            reason="Limpeza",
            created_by=non_staff_user,
        )
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/")
        assert response.status_code == 200
        assert response.context["maintenance_now"] == 1
        assert response.context["available_now"] == 0

    def test_context_contains_no_shows_today(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Context should reflect no-show reservations from today."""
        now = timezone.now()
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now - timezone.timedelta(hours=2),
            end_time=now - timezone.timedelta(hours=1),
            status=ReservationStatus.NO_SHOW,
        )
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/")
        assert response.status_code == 200
        assert response.context["no_shows_today"] == 1

    def test_space_cards_reflect_status(self, client, staff_user, dashboard_space, non_staff_user):
        """Space cards should include correct status labels."""
        now = timezone.now()
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now - timezone.timedelta(minutes=30),
            end_time=now + timezone.timedelta(minutes=30),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/")
        assert response.status_code == 200
        cards = response.context["space_cards"]
        assert len(cards) == 1
        assert cards[0]["status"] == "occupied"
        assert cards[0]["status_label"] == "Ocupado"

    def test_htmx_request_returns_partial(self, client, staff_user):
        """HTMX request should return the partial template without base layout."""
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert "admin_dashboard/_occupancy_grid.html" in [t.name for t in response.templates]
        assert "base.html" not in [t.name for t in response.templates]

    def test_cancelled_reservation_not_occupied(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Cancelled reservations should not count as occupied."""
        now = timezone.now()
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now - timezone.timedelta(minutes=30),
            end_time=now + timezone.timedelta(minutes=30),
            status=ReservationStatus.CANCELLED,
        )
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/")
        assert response.status_code == 200
        assert response.context["occupied_now"] == 0
        assert response.context["available_now"] == 1
