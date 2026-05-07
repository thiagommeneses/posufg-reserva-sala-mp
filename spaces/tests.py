"""Tests for the spaces app models and API."""

from datetime import datetime, time

import pytest
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus

from .models import Attribute, Space, SpaceAttribute


@pytest.mark.django_db
class TestSpaceModel:
    """Tests for the Space model."""

    def test_create_space(self):
        """Creating a space with valid fields should succeed."""
        space = Space.objects.create(
            name="Conference Room A",
            description="A large conference room",
            capacity=20,
            location="Building 1, Floor 2",
            is_active=True,
        )
        assert space.name == "Conference Room A"
        assert space.description == "A large conference room"
        assert space.capacity == 20
        assert space.location == "Building 1, Floor 2"
        assert space.is_active is True
        assert space.created_at is not None
        assert space.updated_at is not None

    def test_space_str(self):
        """Space __str__ should return the name."""
        space = Space.objects.create(
            name="Meeting Room B",
            capacity=10,
            location="Building 2",
        )
        assert str(space) == "Meeting Room B"

    def test_space_ordering(self):
        """Spaces should be ordered by name."""
        Space.objects.create(name="Zebra Room", capacity=5, location="Z")
        Space.objects.create(name="Alpha Room", capacity=5, location="A")
        spaces = list(Space.objects.all())
        assert spaces[0].name == "Alpha Room"
        assert spaces[1].name == "Zebra Room"

    def test_is_active_default(self):
        """is_active should default to True."""
        space = Space.objects.create(name="Test Room", capacity=5, location="T")
        assert space.is_active is True

    def test_description_optional(self):
        """Description should be optional."""
        space = Space.objects.create(name="No Desc", capacity=5, location="T")
        assert space.description is None


@pytest.mark.django_db
class TestAttributeModel:
    """Tests for the Attribute model."""

    def test_create_attribute(self):
        """Creating an attribute with a name should succeed."""
        attr = Attribute.objects.create(name="TV")
        assert attr.name == "TV"

    def test_attribute_str(self):
        """Attribute __str__ should return the name."""
        attr = Attribute.objects.create(name="Projector")
        assert str(attr) == "Projector"

    def test_attribute_name_unique(self):
        """Attribute names must be unique."""
        Attribute.objects.create(name="Whiteboard")
        with pytest.raises(IntegrityError):
            Attribute.objects.create(name="Whiteboard")

    def test_attribute_ordering(self):
        """Attributes should be ordered by name."""
        Attribute.objects.create(name="Zebra")
        Attribute.objects.create(name="Alpha")
        attrs = list(Attribute.objects.all())
        assert attrs[0].name == "Alpha"
        assert attrs[1].name == "Zebra"


@pytest.mark.django_db
class TestSpaceAttributeModel:
    """Tests for the SpaceAttribute through model."""

    def test_create_space_attribute(self):
        """Linking a space and attribute should succeed."""
        space = Space.objects.create(name="Room", capacity=5, location="L")
        attr = Attribute.objects.create(name="TV")
        space_attr = SpaceAttribute.objects.create(space=space, attribute=attr)
        assert space_attr.space == space
        assert space_attr.attribute == attr
        assert str(space_attr) == "Room — TV"

    def test_space_attribute_unique(self):
        """Duplicate space-attribute pairs should be rejected."""
        space = Space.objects.create(name="Room", capacity=5, location="L")
        attr = Attribute.objects.create(name="TV")
        SpaceAttribute.objects.create(space=space, attribute=attr)
        with pytest.raises(IntegrityError):
            SpaceAttribute.objects.create(space=space, attribute=attr)

    def test_space_related_name(self):
        """Space should access linked attributes via space_attributes."""
        space = Space.objects.create(name="Room", capacity=5, location="L")
        attr = Attribute.objects.create(name="TV")
        SpaceAttribute.objects.create(space=space, attribute=attr)
        assert space.space_attributes.count() == 1
        assert space.space_attributes.first().attribute == attr

    def test_attribute_related_name(self):
        """Attribute should access linked spaces via space_attributes."""
        space = Space.objects.create(name="Room", capacity=5, location="L")
        attr = Attribute.objects.create(name="TV")
        SpaceAttribute.objects.create(space=space, attribute=attr)
        assert attr.space_attributes.count() == 1
        assert attr.space_attributes.first().space == space


@pytest.fixture
def api_client():
    """Provide a DRF API test client."""
    return APIClient()


@pytest.fixture
def regular_user(db):
    """Create a regular (non-admin) test user."""
    return User.objects.create_user(
        username="regular",
        email="regular@example.com",
        password="regularpass123",  # noqa: S106
    )


@pytest.fixture
def admin_user(db):
    """Create an admin test user."""
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123",  # noqa: S106
    )


@pytest.fixture
def space_with_tv(db):
    """Create a space linked to a 'TV' attribute."""
    space = Space.objects.create(
        name="Room with TV",
        capacity=10,
        location="Building A",
    )
    attr = Attribute.objects.create(name="TV")
    SpaceAttribute.objects.create(space=space, attribute=attr)
    return space


@pytest.fixture
def small_space(db):
    """Create a small space with no attributes."""
    return Space.objects.create(
        name="Small Room",
        capacity=4,
        location="Building B",
    )


class TestSpaceApiList:
    """Tests for listing spaces via the API."""

    def test_list_spaces_authenticated(self, api_client, regular_user, space_with_tv):
        """Authenticated users should receive a list of spaces with attributes."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/spaces/")
        assert response.status_code == 200
        assert len(response.data) >= 1
        space_data = next(s for s in response.data if s["id"] == space_with_tv.id)
        assert "TV" in space_data["attributes"]

    def test_list_spaces_unauthenticated(self, api_client):
        """Unauthenticated requests should be rejected."""
        response = api_client.get("/api/spaces/")
        assert response.status_code in (401, 403)

    def test_filter_by_min_capacity(self, api_client, regular_user, space_with_tv, small_space):
        """Filtering by min_capacity should exclude smaller spaces."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/spaces/?min_capacity=6")
        assert response.status_code == 200
        names = {s["name"] for s in response.data}
        assert "Room with TV" in names
        assert "Small Room" not in names

    def test_filter_by_attributes(self, api_client, regular_user, space_with_tv, small_space):
        """Filtering by attributes should return only matching spaces."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/spaces/?attributes=TV")
        assert response.status_code == 200
        names = {s["name"] for s in response.data}
        assert "Room with TV" in names
        assert "Small Room" not in names

    def test_filter_by_location_case_insensitive(self, api_client, regular_user, space_with_tv):
        """Location filter should be case-insensitive."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/spaces/?location=building a")
        assert response.status_code == 200
        names = {s["name"] for s in response.data}
        assert "Room with TV" in names


class TestSpaceApiRetrieve:
    """Tests for retrieving a single space via the API."""

    def test_retrieve_space_detail(self, api_client, regular_user, space_with_tv):
        """Authenticated users should be able to retrieve space details."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get(f"/api/spaces/{space_with_tv.id}/")
        assert response.status_code == 200
        assert response.data["name"] == "Room with TV"
        assert "TV" in response.data["attributes"]


class TestSpaceApiCreate:
    """Tests for creating spaces via the API."""

    def test_admin_can_create_space(self, api_client, admin_user):
        """Admin users should be able to create new spaces."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/spaces/",
            {
                "name": "New Room",
                "capacity": 20,
                "location": "Building C",
            },
        )
        assert response.status_code == 201
        assert response.data["name"] == "New Room"
        assert Space.objects.filter(name="New Room").exists()

    def test_non_admin_cannot_create_space(self, api_client, regular_user):
        """Non-admin users should be forbidden from creating spaces."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.post(
            "/api/spaces/",
            {
                "name": "New Room",
                "capacity": 20,
                "location": "Building C",
            },
        )
        assert response.status_code == 403


class TestSpaceAvailability:
    """Tests for the space availability endpoint."""

    def test_availability_reflects_reservations(self, api_client, regular_user, space_with_tv):
        """Confirmed reservations should appear as occupied slots."""
        api_client.force_authenticate(user=regular_user)
        today = timezone.now().date()
        start = timezone.make_aware(datetime.combine(today, time(10, 0)))
        end = timezone.make_aware(datetime.combine(today, time(12, 0)))
        Reservation.objects.create(
            space=space_with_tv,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.get(
            f"/api/spaces/{space_with_tv.id}/availability/?date={today.isoformat()}"
        )
        assert response.status_code == 200
        assert response.data["date"] == today.isoformat()
        occupied = response.data["occupied"]
        assert len(occupied) == 1
        assert occupied[0]["type"] == "reservation"
        free = response.data["free"]
        assert len(free) == 2  # midnight-10am and 12pm-midnight

    def test_availability_reflects_maintenance_blocks(
        self,
        api_client,
        regular_user,
        space_with_tv,
    ):
        """Maintenance blocks should appear as occupied slots."""
        api_client.force_authenticate(user=regular_user)
        today = timezone.now().date()
        start = timezone.make_aware(datetime.combine(today, time(14, 0)))
        end = timezone.make_aware(datetime.combine(today, time(15, 0)))
        MaintenanceBlock.objects.create(
            space=space_with_tv,
            start_time=start,
            end_time=end,
            reason="Cleaning",
            created_by=regular_user,
        )
        response = api_client.get(
            f"/api/spaces/{space_with_tv.id}/availability/?date={today.isoformat()}"
        )
        assert response.status_code == 200
        occupied = response.data["occupied"]
        assert len(occupied) == 1
        assert occupied[0]["type"] == "maintenance"

    def test_cancelled_reservation_does_not_block(self, api_client, regular_user, space_with_tv):
        """Cancelled reservations should not appear in occupied slots."""
        api_client.force_authenticate(user=regular_user)
        today = timezone.now().date()
        start = timezone.make_aware(datetime.combine(today, time(10, 0)))
        end = timezone.make_aware(datetime.combine(today, time(12, 0)))
        Reservation.objects.create(
            space=space_with_tv,
            user=regular_user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CANCELLED,
        )
        response = api_client.get(
            f"/api/spaces/{space_with_tv.id}/availability/?date={today.isoformat()}"
        )
        assert response.status_code == 200
        assert response.data["occupied"] == []
        assert len(response.data["free"]) == 1  # entire day free
