"""Tests for the admin dashboard app."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from ai_assistant.exceptions import AIServiceError
from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
from spaces.models import Attribute, Space, SpaceAttribute

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
        # Anchored to the start of today (not "now - 2h") so this can't flake
        # when the suite runs shortly after midnight.
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=today_start + timezone.timedelta(hours=1),
            end_time=today_start + timezone.timedelta(hours=2),
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


@pytest.mark.django_db
class TestAdminSpaceManagement:
    """Tests for admin space management views."""

    def test_staff_can_list_spaces(self, client, staff_user, dashboard_space):
        """Staff users should see the space list."""
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/spaces/")
        assert response.status_code == 200
        assert "spaces" in response.context
        assert dashboard_space in list(response.context["spaces"])

    def test_non_staff_cannot_list_spaces(self, client, non_staff_user):
        """Non-staff users should get 403 on space list."""
        client.force_login(non_staff_user)
        response = client.get("/admin-dashboard/spaces/")
        assert response.status_code == 403

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Unauthenticated users should be redirected to login on admin space pages."""
        response = client.get("/admin-dashboard/spaces/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_staff_can_create_space(self, client, staff_user):
        """Staff users should be able to create a new space."""
        client.force_login(staff_user)
        response = client.post(
            "/admin-dashboard/spaces/new/",
            {
                "name": "Nova Sala",
                "description": "Uma sala nova",
                "capacity": 10,
                "location": "Térreo",
                "is_active": "on",
            },
        )
        assert response.status_code == 302
        assert response.url == "/admin-dashboard/spaces/"
        assert Space.objects.filter(name="Nova Sala").exists()

    def test_non_staff_cannot_create_space(self, client, non_staff_user):
        """Non-staff users should get 403 when creating a space."""
        client.force_login(non_staff_user)
        response = client.post(
            "/admin-dashboard/spaces/new/",
            {
                "name": "Nova Sala",
                "capacity": 10,
                "location": "Térreo",
            },
        )
        assert response.status_code == 403

    def test_staff_can_update_space(self, client, staff_user, dashboard_space):
        """Staff users should be able to update an existing space."""
        client.force_login(staff_user)
        response = client.post(
            f"/admin-dashboard/spaces/{dashboard_space.pk}/",
            {
                "name": "Sala Atualizada",
                "description": "",
                "capacity": 20,
                "location": "2º andar",
            },
        )
        assert response.status_code == 302
        assert response.url == "/admin-dashboard/spaces/"
        dashboard_space.refresh_from_db()
        assert dashboard_space.name == "Sala Atualizada"
        assert dashboard_space.is_active is False

    def test_non_staff_cannot_update_space(self, client, non_staff_user, dashboard_space):
        """Non-staff users should get 403 when updating a space."""
        client.force_login(non_staff_user)
        response = client.post(
            f"/admin-dashboard/spaces/{dashboard_space.pk}/",
            {
                "name": "Sala Atualizada",
                "capacity": 20,
                "location": "2º andar",
            },
        )
        assert response.status_code == 403

    def test_create_space_with_attributes(self, client, staff_user, db):
        """Creating a space with attributes should persist the relationships."""
        attr1 = Attribute.objects.create(name="Projetor")
        attr2 = Attribute.objects.create(name="Wi-Fi")
        client.force_login(staff_user)
        response = client.post(
            "/admin-dashboard/spaces/new/",
            {
                "name": "Sala Completa",
                "description": "",
                "capacity": 15,
                "location": "Bloco B",
                "is_active": "on",
                "attributes": [str(attr1.pk), str(attr2.pk)],
            },
        )
        assert response.status_code == 302
        space = Space.objects.get(name="Sala Completa")
        attr_names = set(space.space_attributes.values_list("attribute__name", flat=True))
        assert attr_names == {"Projetor", "Wi-Fi"}

    def test_update_space_attributes(self, client, staff_user, dashboard_space, db):
        """Updating a space should correctly synchronize attributes."""
        attr1 = Attribute.objects.create(name="TV")
        attr2 = Attribute.objects.create(name="Ar-condicionado")
        SpaceAttribute.objects.create(space=dashboard_space, attribute=attr1)
        client.force_login(staff_user)
        response = client.post(
            f"/admin-dashboard/spaces/{dashboard_space.pk}/",
            {
                "name": dashboard_space.name,
                "description": "",
                "capacity": dashboard_space.capacity,
                "location": dashboard_space.location,
                "is_active": "on",
                "attributes": [str(attr2.pk)],
            },
        )
        assert response.status_code == 302
        dashboard_space.refresh_from_db()
        attr_names = set(dashboard_space.space_attributes.values_list("attribute__name", flat=True))
        assert attr_names == {"Ar-condicionado"}

    def test_staff_can_toggle_space_active(self, client, staff_user, dashboard_space):
        """Staff users should be able to toggle space is_active inline."""
        client.force_login(staff_user)
        response = client.patch(
            f"/admin-dashboard/spaces/{dashboard_space.pk}/toggle/",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert "Inativo" in response.content.decode()
        dashboard_space.refresh_from_db()
        assert dashboard_space.is_active is False

    def test_non_staff_cannot_toggle_space(self, client, non_staff_user, dashboard_space):
        """Non-staff users should get 403 when toggling a space."""
        client.force_login(non_staff_user)
        response = client.patch(
            f"/admin-dashboard/spaces/{dashboard_space.pk}/toggle/",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 403

    def test_space_list_no_infinite_spinner(self, client, staff_user, dashboard_space):
        """Status column spinner must be an htmx-indicator, hidden by default via CSS."""
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/spaces/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'class="spinner htmx-indicator' in content
        assert "style=\"display: none;\"" not in content

    def test_toggle_response_includes_functional_badge(self, client, staff_user, dashboard_space):
        """Toggle response should include a functional badge with a real htmx-indicator spinner."""
        client.force_login(staff_user)
        response = client.patch(
            f"/admin-dashboard/spaces/{dashboard_space.pk}/toggle/",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "hx-patch=" in content
        assert 'class="spinner htmx-indicator' in content
        assert "style=\"display: none;\"" not in content


@pytest.mark.django_db
class TestAdminReservationManagement:
    """Tests for admin reservation management views."""

    def test_staff_can_view_all_reservations(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Staff users should see all reservations, not just their own."""
        now = timezone.now()
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/reservations/")
        assert response.status_code == 200
        assert "reservations" in response.context
        assert len(response.context["reservations"]) == 1

    def test_non_staff_cannot_view_reservations(self, client, non_staff_user):
        """Non-staff users should get 403 on reservation list."""
        client.force_login(non_staff_user)
        response = client.get("/admin-dashboard/reservations/")
        assert response.status_code == 403

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Unauthenticated users should be redirected to login on admin reservation pages."""
        response = client.get("/admin-dashboard/reservations/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_staff_can_cancel_any_reservation(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Staff users should be able to cancel any user's reservation."""
        now = timezone.now()
        reservation = Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(staff_user)
        response = client.post(f"/admin-dashboard/reservations/{reservation.pk}/cancel/")
        assert response.status_code == 200
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED

    def test_staff_cancel_htmx_returns_updated_row(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """HTMX cancel request should return the updated row partial."""
        now = timezone.now()
        reservation = Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(staff_user)
        response = client.post(
            f"/admin-dashboard/reservations/{reservation.pk}/cancel/",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert "admin_dashboard/_reservation_row.html" in [t.name for t in response.templates]
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED
        content = response.content.decode()
        assert "Cancelada" in content

    def test_non_staff_cannot_cancel_reservation(self, client, non_staff_user, dashboard_space):
        """Non-staff users should get 403 when cancelling a reservation."""
        now = timezone.now()
        reservation = Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(non_staff_user)
        response = client.post(f"/admin-dashboard/reservations/{reservation.pk}/cancel/")
        assert response.status_code == 403
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CONFIRMED

    def test_filter_by_status(self, client, staff_user, dashboard_space, non_staff_user):
        """Filtering by status should return only matching reservations."""
        now = timezone.now()
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=3),
            end_time=now + timezone.timedelta(hours=4),
            status=ReservationStatus.CANCELLED,
        )
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/reservations/?status=confirmed")
        assert response.status_code == 200
        assert len(response.context["reservations"]) == 1
        assert response.context["reservations"][0].status == ReservationStatus.CONFIRMED

    def test_filter_by_space(self, client, staff_user, dashboard_space, non_staff_user):
        """Filtering by space should return only matching reservations."""
        now = timezone.now()
        other_space = Space.objects.create(name="Other Room", capacity=5, location="Floor 2")
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )
        Reservation.objects.create(
            space=other_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(staff_user)
        response = client.get(f"/admin-dashboard/reservations/?space={dashboard_space.pk}")
        assert response.status_code == 200
        assert len(response.context["reservations"]) == 1
        assert response.context["reservations"][0].space == dashboard_space

    def test_filter_by_user_search(self, client, staff_user, dashboard_space, non_staff_user):
        """Filtering by user search should return only matching reservations."""
        now = timezone.now()
        other_user = User.objects.create_user(
            username="other_user", email="other@example.com", password="pass"
        )
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )
        Reservation.objects.create(
            space=dashboard_space,
            user=other_user,
            start_time=now + timezone.timedelta(hours=3),
            end_time=now + timezone.timedelta(hours=4),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/reservations/?user_search=regular")
        assert response.status_code == 200
        assert len(response.context["reservations"]) == 1
        assert response.context["reservations"][0].user == non_staff_user

    def test_htmx_filter_returns_partial(self, client, staff_user, dashboard_space, non_staff_user):
        """HTMX filter request should return partial template without base layout."""
        now = timezone.now()
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(staff_user)
        response = client.get(
            "/admin-dashboard/reservations/?status=confirmed",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert "admin_dashboard/_reservation_table.html" in [t.name for t in response.templates]
        assert "base.html" not in [t.name for t in response.templates]

    def test_cancel_already_cancelled_returns_error(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Cancelling an already cancelled reservation should return an error."""
        now = timezone.now()
        reservation = Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            status=ReservationStatus.CANCELLED,
        )
        client.force_login(staff_user)
        response = client.post(f"/admin-dashboard/reservations/{reservation.pk}/cancel/")
        assert response.status_code == 400
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED

    def test_reservation_list_no_infinite_filter_indicator(self, client, staff_user):
        """Filter indicator must be an htmx-indicator, hidden by default via CSS."""
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/reservations/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="filter-indicator"' in content
        assert "htmx-indicator" in content
        assert "style=\"display: none;\"" not in content


@pytest.mark.django_db
class TestAdminMaintenanceManagement:
    """Tests for admin maintenance block management views."""

    def test_staff_can_list_maintenance_blocks(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Staff users should see the maintenance block list."""
        now = timezone.now()
        block = MaintenanceBlock.objects.create(
            space=dashboard_space,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            reason="Limpeza",
            created_by=non_staff_user,
        )
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/maintenance/")
        assert response.status_code == 200
        assert "maintenance_blocks" in response.context
        assert block in list(response.context["maintenance_blocks"])

    def test_non_staff_cannot_list_maintenance_blocks(self, client, non_staff_user):
        """Non-staff users should get 403 on maintenance block list."""
        client.force_login(non_staff_user)
        response = client.get("/admin-dashboard/maintenance/")
        assert response.status_code == 403

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Unauthenticated users should be redirected to login on maintenance pages."""
        response = client.get("/admin-dashboard/maintenance/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_staff_can_create_maintenance_block(self, client, staff_user, dashboard_space):
        """Staff users should be able to create a maintenance block on a free slot."""
        now = timezone.now()
        start = now + timezone.timedelta(hours=1)
        end = now + timezone.timedelta(hours=2)
        client.force_login(staff_user)
        response = client.post(
            "/admin-dashboard/maintenance/new/",
            {
                "space": str(dashboard_space.pk),
                "start_time": start.strftime("%Y-%m-%dT%H:%M"),
                "end_time": end.strftime("%Y-%m-%dT%H:%M"),
                "reason": "Manutenção do ar-condicionado",
            },
        )
        assert response.status_code == 302
        assert response.url == "/admin-dashboard/maintenance/"
        assert MaintenanceBlock.objects.filter(reason="Manutenção do ar-condicionado").exists()

    def test_non_staff_cannot_create_maintenance_block(
        self, client, non_staff_user, dashboard_space
    ):
        """Non-staff users should get 403 when creating a maintenance block."""
        now = timezone.now()
        client.force_login(non_staff_user)
        response = client.post(
            "/admin-dashboard/maintenance/new/",
            {
                "space": str(dashboard_space.pk),
                "start_time": (now + timezone.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (now + timezone.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
                "reason": "Limpeza",
            },
        )
        assert response.status_code == 403

    def test_create_maintenance_block_overlapping_reservation_shows_error(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Creating a maintenance block overlapping a confirmed reservation shows error."""
        now = timezone.now()
        Reservation.objects.create(
            space=dashboard_space,
            user=non_staff_user,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=3),
            status=ReservationStatus.CONFIRMED,
        )
        client.force_login(staff_user)
        response = client.post(
            "/admin-dashboard/maintenance/new/",
            {
                "space": str(dashboard_space.pk),
                "start_time": (now + timezone.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (now + timezone.timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M"),
                "reason": "Manutenção",
            },
        )
        assert response.status_code == 200
        assert "admin_dashboard/maintenance_form.html" in [t.name for t in response.templates]
        content = response.content.decode()
        assert "overlaps with an existing reservation" in content
        assert not MaintenanceBlock.objects.filter(reason="Manutenção").exists()

    def test_staff_can_delete_maintenance_block(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """Staff users should be able to delete a maintenance block."""
        now = timezone.now()
        block = MaintenanceBlock.objects.create(
            space=dashboard_space,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            reason="Limpeza",
            created_by=non_staff_user,
        )
        client.force_login(staff_user)
        response = client.delete(f"/admin-dashboard/maintenance/{block.pk}/delete/")
        assert response.status_code == 200
        assert not MaintenanceBlock.objects.filter(pk=block.pk).exists()

    def test_staff_delete_htmx_returns_empty(
        self, client, staff_user, dashboard_space, non_staff_user
    ):
        """HTMX delete request should return empty response."""
        now = timezone.now()
        block = MaintenanceBlock.objects.create(
            space=dashboard_space,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            reason="Limpeza",
            created_by=non_staff_user,
        )
        client.force_login(staff_user)
        response = client.delete(
            f"/admin-dashboard/maintenance/{block.pk}/delete/",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert response.content == b""
        assert not MaintenanceBlock.objects.filter(pk=block.pk).exists()

    def test_non_staff_cannot_delete_maintenance_block(
        self, client, non_staff_user, dashboard_space
    ):
        """Non-staff users should get 403 when deleting a maintenance block."""
        now = timezone.now()
        block = MaintenanceBlock.objects.create(
            space=dashboard_space,
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            reason="Limpeza",
            created_by=non_staff_user,
        )
        client.force_login(non_staff_user)
        response = client.delete(f"/admin-dashboard/maintenance/{block.pk}/delete/")
        assert response.status_code == 403
        assert MaintenanceBlock.objects.filter(pk=block.pk).exists()


@pytest.mark.django_db
class TestAdminMaintenanceClassifyView:
    """Tests for the AI-powered maintenance reason classification endpoint."""

    @patch("admin_dashboard.views.classify_maintenance_reason")
    def test_staff_gets_classification_suggestion(self, mock_classify, client, staff_user):
        """A valid reason should return the AI-suggested category."""
        mock_classify.return_value = {
            "category": "eletrica",
            "confidence": "alta",
            "justification": "Menciona curto-circuito no quadro de energia.",
        }
        client.force_login(staff_user)
        response = client.post(
            "/admin-dashboard/maintenance/classify/",
            {"reason": "curto-circuito no quadro de energia"},
        )
        assert response.status_code == 200
        mock_classify.assert_called_once_with("curto-circuito no quadro de energia")
        content = response.content.decode()
        assert "eletrica" in content
        assert "alta" in content

    def test_blank_reason_shows_error_without_calling_ai(self, client, staff_user):
        """An empty reason should be rejected before calling the AI service."""
        client.force_login(staff_user)
        response = client.post("/admin-dashboard/maintenance/classify/", {"reason": "  "})
        assert response.status_code == 200
        assert "Descreva o motivo" in response.content.decode()

    @patch("admin_dashboard.views.classify_maintenance_reason")
    def test_ai_service_error_shows_message(self, mock_classify, client, staff_user):
        """A failing AI service should return a friendly error, not crash."""
        mock_classify.side_effect = AIServiceError("Serviço de IA indisponível.")
        client.force_login(staff_user)
        response = client.post(
            "/admin-dashboard/maintenance/classify/",
            {"reason": "cheiro de queimado na tomada"},
        )
        assert response.status_code == 200
        assert "Serviço de IA indisponível." in response.content.decode()

    def test_non_staff_cannot_classify(self, client, non_staff_user):
        """Non-staff users should get 403."""
        client.force_login(non_staff_user)
        response = client.post(
            "/admin-dashboard/maintenance/classify/",
            {"reason": "cheiro de queimado na tomada"},
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestAdminUserManagement:
    """Tests for admin user management views."""

    def test_staff_can_list_users(self, client, staff_user, non_staff_user):
        """Staff users should see the user list."""
        client.force_login(staff_user)
        response = client.get("/admin-dashboard/users/")
        assert response.status_code == 200
        assert non_staff_user in list(response.context["users"])

    def test_non_staff_cannot_list_users(self, client, non_staff_user):
        """Non-staff users should get 403 on the user list."""
        client.force_login(non_staff_user)
        response = client.get("/admin-dashboard/users/")
        assert response.status_code == 403

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Unauthenticated users should be redirected to login on the user list."""
        response = client.get("/admin-dashboard/users/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_staff_can_create_regular_user(self, client, staff_user):
        """Staff users should be able to create a new regular user."""
        client.force_login(staff_user)
        response = client.post(
            "/admin-dashboard/users/new/",
            {
                "username": "novousuario",
                "email": "novo@example.com",
                "is_active": "on",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        assert response.status_code == 302
        user = User.objects.get(username="novousuario")
        assert user.is_staff is False
        assert user.check_password("StrongPass123!")

    def test_staff_can_create_admin_user(self, client, staff_user):
        """Staff users should be able to promote a new user to admin via the is_staff field."""
        client.force_login(staff_user)
        response = client.post(
            "/admin-dashboard/users/new/",
            {
                "username": "novoadmin",
                "email": "admin2@example.com",
                "is_staff": "on",
                "is_active": "on",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        assert response.status_code == 302
        user = User.objects.get(username="novoadmin")
        assert user.is_staff is True

    def test_create_user_password_mismatch_shows_error(self, client, staff_user):
        """Mismatched passwords should re-render the form with an error."""
        client.force_login(staff_user)
        response = client.post(
            "/admin-dashboard/users/new/",
            {
                "username": "novousuario",
                "email": "novo@example.com",
                "password1": "StrongPass123!",
                "password2": "Diferente123!",
            },
        )
        assert response.status_code == 200
        assert not User.objects.filter(username="novousuario").exists()

    def test_non_staff_cannot_create_user(self, client, non_staff_user):
        """Non-staff users should get 403 when creating a user."""
        client.force_login(non_staff_user)
        response = client.post(
            "/admin-dashboard/users/new/",
            {
                "username": "novousuario",
                "email": "novo@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        assert response.status_code == 403

    def test_staff_can_update_user_without_changing_password(self, client, staff_user):
        """Editing a user without filling password fields should keep the old password."""
        target = User.objects.create_user(
            username="editme", email="editme@example.com", password="original123"
        )
        client.force_login(staff_user)
        response = client.post(
            f"/admin-dashboard/users/{target.pk}/",
            {
                "username": "editme",
                "email": "changed@example.com",
                "is_active": "on",
            },
        )
        assert response.status_code == 302
        target.refresh_from_db()
        assert target.email == "changed@example.com"
        assert target.check_password("original123")

    def test_staff_can_reset_user_password(self, client, staff_user):
        """Editing a user with new password fields should update the password."""
        target = User.objects.create_user(
            username="editme", email="editme@example.com", password="original123"
        )
        client.force_login(staff_user)
        response = client.post(
            f"/admin-dashboard/users/{target.pk}/",
            {
                "username": "editme",
                "email": "editme@example.com",
                "is_active": "on",
                "password1": "NewStrongPass123!",
                "password2": "NewStrongPass123!",
            },
        )
        assert response.status_code == 302
        target.refresh_from_db()
        assert target.check_password("NewStrongPass123!")

    def test_staff_can_delete_other_user(self, client, staff_user, non_staff_user):
        """Staff users should be able to delete another user."""
        client.force_login(staff_user)
        response = client.delete(f"/admin-dashboard/users/{non_staff_user.pk}/delete/")
        assert response.status_code == 200
        assert not User.objects.filter(pk=non_staff_user.pk).exists()

    def test_staff_cannot_delete_own_account(self, client, staff_user):
        """Staff users should not be able to delete their own account."""
        client.force_login(staff_user)
        response = client.delete(f"/admin-dashboard/users/{staff_user.pk}/delete/")
        assert response.status_code == 400
        assert User.objects.filter(pk=staff_user.pk).exists()

    def test_non_staff_cannot_delete_user(self, client, non_staff_user, staff_user):
        """Non-staff users should get 403 when deleting a user."""
        client.force_login(non_staff_user)
        response = client.delete(f"/admin-dashboard/users/{staff_user.pk}/delete/")
        assert response.status_code == 403
        assert User.objects.filter(pk=staff_user.pk).exists()
