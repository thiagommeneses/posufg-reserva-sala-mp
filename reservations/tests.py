"""Tests for the reservations app."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
from reservations.services import auto_release_no_shows
from spaces.models import Space

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def other_user(db):
    """Create another test user."""
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="otherpass123",
    )


@pytest.fixture
def space(db):
    """Create a test space."""
    return Space.objects.create(
        name="Test Room",
        capacity=10,
        location="Floor 1",
    )


@pytest.fixture
def inactive_space(db):
    """Create an inactive test space."""
    return Space.objects.create(
        name="Inactive Room",
        capacity=5,
        location="Floor 2",
        is_active=False,
    )


class TestReservationModel:
    """Tests for the Reservation model."""

    def test_create_reservation(self, db, user, space):
        """Creating a valid reservation should succeed."""
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
        )
        assert reservation.space == space
        assert reservation.user == user
        assert reservation.start_time == start
        assert reservation.end_time == end
        assert reservation.status == ReservationStatus.CONFIRMED
        assert reservation.checked_in_at is None

    def test_reservation_str(self, db, user, space):
        """Reservation __str__ should include space name and times."""
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
        )
        expected = f"{space.name} — {start} to {end}"
        assert str(reservation) == expected

    def test_reservation_ordering(self, db, user, space):
        """Reservations should be ordered by start_time descending."""
        now = timezone.now()
        r1 = Reservation.objects.create(
            space=space,
            user=user,
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
        )
        r2 = Reservation.objects.create(
            space=space,
            user=user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
        )
        reservations = list(Reservation.objects.all())
        assert reservations == [r1, r2]

    def test_default_status_is_confirmed(self, db, user, space):
        """Default status should be confirmed."""
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
        )
        assert reservation.status == ReservationStatus.CONFIRMED

    def test_end_time_before_start_time_raises_validation_error(self, db, user, space):
        """End time before start time should raise ValidationError."""
        start = timezone.now()
        end = start - timedelta(hours=1)
        reservation = Reservation(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
        )
        with pytest.raises(ValidationError, match="End time must be after start time"):
            reservation.clean()

    def test_equal_start_and_end_time_raises_validation_error(self, db, user, space):
        """Equal start and end time should raise ValidationError."""
        start = timezone.now()
        reservation = Reservation(
            space=space,
            user=user,
            start_time=start,
            end_time=start,
        )
        with pytest.raises(ValidationError, match="End time must be after start time"):
            reservation.clean()

    def test_overlapping_confirmed_reservation_raises_validation_error(self, db, user, space):
        """Overlapping confirmed reservation should raise ValidationError on clean."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
        )
        overlapping = Reservation(
            space=space,
            user=user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
        )
        with pytest.raises(ValidationError, match="overlaps with an existing reservation"):
            overlapping.clean()

    def test_overlapping_checked_in_reservation_raises_validation_error(self, db, user, space):
        """Overlapping checked-in reservation should raise ValidationError on clean."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
            status=ReservationStatus.CHECKED_IN,
            checked_in_at=now,
        )
        overlapping = Reservation(
            space=space,
            user=user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
        )
        with pytest.raises(ValidationError, match="overlaps with an existing reservation"):
            overlapping.clean()

    def test_non_overlapping_reservation_is_valid(self, db, user, space):
        """Non-overlapping reservation should be valid."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        non_overlapping = Reservation(
            space=space,
            user=user,
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
        )
        non_overlapping.clean()  # should not raise

    def test_cancelled_reservation_does_not_block(self, db, user, space):
        """Cancelled reservation should not block new reservations."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
            status=ReservationStatus.CANCELLED,
        )
        new_reservation = Reservation(
            space=space,
            user=user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
        )
        new_reservation.clean()  # should not raise

    def test_completed_reservation_does_not_block(self, db, user, space):
        """Completed reservation should not block new reservations."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
            status=ReservationStatus.COMPLETED,
        )
        new_reservation = Reservation(
            space=space,
            user=user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
        )
        new_reservation.clean()  # should not raise

    def test_no_show_reservation_does_not_block(self, db, user, space):
        """No-show reservation should not block new reservations."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
            status=ReservationStatus.NO_SHOW,
        )
        new_reservation = Reservation(
            space=space,
            user=user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
        )
        new_reservation.clean()  # should not raise

    def test_different_space_no_overlap(self, db, user, space):
        """Reservation on different space should not overlap."""
        other_space = Space.objects.create(
            name="Other Room",
            capacity=5,
            location="Floor 2",
        )
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
        )
        other_reservation = Reservation(
            space=other_space,
            user=user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
        )
        other_reservation.clean()  # should not raise

    def test_db_constraint_prevents_overlapping(self, db, user, space):
        """DB-level constraint should prevent overlapping reservations."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
        )
        with pytest.raises(IntegrityError):
            Reservation.objects.create(
                space=space,
                user=user,
                start_time=now + timedelta(hours=1),
                end_time=now + timedelta(hours=3),
            )

    def test_update_reservation_avoids_overlap(self, db, user, space):
        """Updating a reservation to avoid overlap should succeed."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        r2 = Reservation.objects.create(
            space=space,
            user=user,
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
        )
        # Move r2 to not overlap
        r2.start_time = now + timedelta(hours=4)
        r2.end_time = now + timedelta(hours=5)
        r2.clean()
        r2.save()
        assert r2.start_time == now + timedelta(hours=4)


class TestMaintenanceBlockModel:
    """Tests for the MaintenanceBlock model."""

    def test_create_maintenance_block(self, db, user, space):
        """Creating a valid maintenance block should succeed."""
        start = timezone.now()
        end = start + timedelta(hours=2)
        block = MaintenanceBlock.objects.create(
            space=space,
            start_time=start,
            end_time=end,
            reason="Cleaning",
            created_by=user,
        )
        assert block.space == space
        assert block.reason == "Cleaning"
        assert block.created_by == user

    def test_maintenance_block_str(self, db, user, space):
        """MaintenanceBlock __str__ should include space, reason, and times."""
        start = timezone.now()
        end = start + timedelta(hours=2)
        block = MaintenanceBlock.objects.create(
            space=space,
            start_time=start,
            end_time=end,
            reason="Cleaning",
            created_by=user,
        )
        expected = f"{space.name} — Cleaning ({start} to {end})"
        assert str(block) == expected

    def test_maintenance_block_ordering(self, db, user, space):
        """MaintenanceBlocks should be ordered by start_time descending."""
        now = timezone.now()
        b1 = MaintenanceBlock.objects.create(
            space=space,
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
            reason="Block A",
            created_by=user,
        )
        b2 = MaintenanceBlock.objects.create(
            space=space,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            reason="Block B",
            created_by=user,
        )
        blocks = list(MaintenanceBlock.objects.all())
        assert blocks == [b1, b2]

    def test_end_time_before_start_time_raises_validation_error(self, db, user, space):
        """End time before start time should raise ValidationError."""
        start = timezone.now()
        end = start - timedelta(hours=1)
        block = MaintenanceBlock(
            space=space,
            start_time=start,
            end_time=end,
            reason="Bad block",
            created_by=user,
        )
        with pytest.raises(ValidationError, match="End time must be after start time"):
            block.clean()

    def test_overlap_with_confirmed_reservation_raises_validation_error(self, db, user, space):
        """Overlapping a confirmed reservation should raise ValidationError."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
        )
        block = MaintenanceBlock(
            space=space,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
            reason="Maintenance",
            created_by=user,
        )
        with pytest.raises(
            ValidationError,
            match="overlaps with an existing reservation",
        ):
            block.clean()

    def test_overlap_with_checked_in_reservation_raises_validation_error(self, db, user, space):
        """Overlapping a checked-in reservation should raise ValidationError."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
            status=ReservationStatus.CHECKED_IN,
            checked_in_at=now,
        )
        block = MaintenanceBlock(
            space=space,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
            reason="Maintenance",
            created_by=user,
        )
        with pytest.raises(
            ValidationError,
            match="overlaps with an existing reservation",
        ):
            block.clean()

    def test_no_overlap_with_cancelled_reservation(self, db, user, space):
        """Maintenance block should not be blocked by cancelled reservation."""
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
            status=ReservationStatus.CANCELLED,
        )
        block = MaintenanceBlock(
            space=space,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
            reason="Maintenance",
            created_by=user,
        )
        block.clean()  # should not raise

    def test_different_space_no_overlap(self, db, user, space):
        """Maintenance block on different space should not overlap."""
        other_space = Space.objects.create(
            name="Other Room",
            capacity=5,
            location="Floor 2",
        )
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=now,
            end_time=now + timedelta(hours=2),
        )
        block = MaintenanceBlock(
            space=other_space,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
            reason="Maintenance",
            created_by=user,
        )
        block.clean()  # should not raise


class TestReservationStatusChoices:
    """Tests for ReservationStatus choices."""

    def test_all_status_choices_exist(self):
        """All expected status choices should be defined."""
        choices = dict(ReservationStatus.choices)
        assert "confirmed" in choices
        assert "cancelled" in choices
        assert "checked_in" in choices
        assert "completed" in choices
        assert "no_show" in choices

    def test_status_labels(self):
        """Status labels should be human-readable."""
        assert ReservationStatus.CONFIRMED.label == "Confirmed"
        assert ReservationStatus.CANCELLED.label == "Cancelled"
        assert ReservationStatus.CHECKED_IN.label == "Checked In"
        assert ReservationStatus.COMPLETED.label == "Completed"
        assert ReservationStatus.NO_SHOW.label == "No Show"


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
        password="regularpass123",
    )


@pytest.fixture
def admin_user(db):
    """Create an admin (staff) test user."""
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="adminpass123",
        is_staff=True,
    )


class TestReservationApiCreate:
    """Tests for creating reservations via the API."""

    def test_successful_reservation_creation(self, api_client, regular_user, space):
        """Authenticated users should be able to create reservations."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        response = api_client.post(
            "/api/reservations/",
            {
                "space": space.id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code == 201
        assert response.data["space"] == space.id
        assert response.data["status"] == ReservationStatus.CONFIRMED
        assert Reservation.objects.filter(
            space=space,
            user=regular_user,
        ).exists()

    def test_conflict_returns_error(self, api_client, regular_user, space):
        """Overlapping reservations should return 400 with an error message."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=2)
        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.post(
            "/api/reservations/",
            {
                "space": space.id,
                "start_time": (start + timedelta(hours=1)).isoformat(),
                "end_time": (start + timedelta(hours=3)).isoformat(),
            },
        )
        assert response.status_code == 400
        assert "overlaps" in str(response.data).lower()

    def test_inactive_space_is_rejected(self, api_client, regular_user, inactive_space):
        """Reservations on inactive spaces should be rejected."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        response = api_client.post(
            "/api/reservations/",
            {
                "space": inactive_space.id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code == 400
        assert "not available" in str(response.data).lower()

    def test_unauthenticated_request_is_rejected(self, api_client, space):
        """Unauthenticated requests should be rejected."""
        start = timezone.now()
        end = start + timedelta(hours=1)
        response = api_client.post(
            "/api/reservations/",
            {
                "space": space.id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code in (401, 403)

    def test_maintenance_block_overlap_is_rejected(self, api_client, regular_user, space):
        """Reservations overlapping maintenance blocks should be rejected."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=2)
        MaintenanceBlock.objects.create(
            space=space,
            start_time=start,
            end_time=end,
            reason="Cleaning",
            created_by=regular_user,
        )
        response = api_client.post(
            "/api/reservations/",
            {
                "space": space.id,
                "start_time": (start + timedelta(minutes=30)).isoformat(),
                "end_time": (start + timedelta(hours=3)).isoformat(),
            },
        )
        assert response.status_code == 400
        assert "maintenance" in str(response.data).lower()

    def test_end_time_before_start_time_is_rejected(self, api_client, regular_user, space):
        """Reservations with end_time <= start_time should be rejected."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start - timedelta(hours=1)
        response = api_client.post(
            "/api/reservations/",
            {
                "space": space.id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code == 400
        assert "after start" in str(response.data).lower()

    def test_user_sees_only_own_reservations(self, api_client, regular_user, space, user):
        """Users should only see their own reservations in the list."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        Reservation.objects.create(
            space=space,
            user=user,
            start_time=start + timedelta(hours=2),
            end_time=start + timedelta(hours=3),
        )
        response = api_client.get("/api/reservations/")
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["user"] == regular_user.id


class TestReservationApiList:
    """Tests for listing and filtering reservations via the API."""

    def test_list_ordered_by_start_time_descending(self, api_client, regular_user, space):
        """Reservations should be ordered by start_time descending."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        r1 = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
        )
        r2 = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
        )
        response = api_client.get("/api/reservations/")
        assert response.status_code == 200
        assert len(response.data) == 2
        assert response.data[0]["id"] == r2.id
        assert response.data[1]["id"] == r1.id

    def test_filter_by_status(self, api_client, regular_user, space):
        """Filtering by status should return only matching reservations."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        confirmed = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=now,
            end_time=now + timedelta(hours=1),
            status=ReservationStatus.CONFIRMED,
        )
        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
            status=ReservationStatus.CANCELLED,
        )
        response = api_client.get("/api/reservations/?status=confirmed")
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["id"] == confirmed.id

    def test_filter_by_space(self, api_client, regular_user, space):
        """Filtering by space should return only reservations for that space."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        other_space = Space.objects.create(name="Other Room", capacity=5, location="Floor 2")
        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        Reservation.objects.create(
            space=other_space,
            user=regular_user,
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
        )
        response = api_client.get(f"/api/reservations/?space={space.id}")
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["space"] == space.id

    def test_filter_by_date_range(self, api_client, regular_user, space):
        """Filtering by start_time date range should return only matching reservations."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        r1 = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=now + timedelta(days=2),
            end_time=now + timedelta(days=2, hours=1),
        )
        gte = now.isoformat()
        lte = (now + timedelta(days=1)).isoformat()
        response = api_client.get(
            "/api/reservations/",
            {"start_time__gte": gte, "start_time__lte": lte},
        )
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["id"] == r1.id

    def test_unauthenticated_list_is_rejected(self, api_client):
        """Unauthenticated requests to list reservations should be rejected."""
        response = api_client.get("/api/reservations/")
        assert response.status_code in (401, 403)


class TestReservationApiCancel:
    """Tests for cancelling reservations via the API."""

    def test_owner_can_cancel_confirmed_reservation(self, api_client, regular_user, space):
        """Reservation owner should be able to cancel a confirmed reservation."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.patch(f"/api/reservations/{reservation.id}/cancel/")
        assert response.status_code == 200
        assert response.data["status"] == ReservationStatus.CANCELLED
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED

    def test_owner_can_cancel_checked_in_reservation(self, api_client, regular_user, space):
        """Reservation owner should be able to cancel a checked-in reservation."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CHECKED_IN,
            checked_in_at=start,
        )
        response = api_client.patch(f"/api/reservations/{reservation.id}/cancel/")
        assert response.status_code == 200
        assert response.data["status"] == ReservationStatus.CANCELLED
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED

    def test_non_owner_cannot_cancel(self, api_client, regular_user, other_user, space):
        """Non-owners should get 403 when trying to cancel another user's reservation."""
        api_client.force_authenticate(user=other_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.patch(f"/api/reservations/{reservation.id}/cancel/")
        assert response.status_code == 403
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CONFIRMED

    def test_cannot_cancel_already_cancelled_reservation(self, api_client, regular_user, space):
        """Cancelling an already cancelled reservation should return 400."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CANCELLED,
        )
        response = api_client.patch(f"/api/reservations/{reservation.id}/cancel/")
        assert response.status_code == 400
        assert "cancelled" in str(response.data).lower()

    def test_cancelling_frees_up_slot(self, api_client, regular_user, space):
        """After cancellation, the time slot should be available for new reservations."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        api_client.patch(f"/api/reservations/{reservation.id}/cancel/")
        response = api_client.post(
            "/api/reservations/",
            {
                "space": space.id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code == 201


class TestReservationApiReschedule:
    """Tests for rescheduling reservations via the API."""

    def test_successful_reschedule_updates_times(self, api_client, regular_user, space):
        """Owner should be able to reschedule to an available slot."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        original_start = now
        original_end = now + timedelta(hours=1)
        new_start = now + timedelta(hours=2)
        new_end = now + timedelta(hours=3)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=original_start,
            end_time=original_end,
        )
        response = api_client.patch(
            f"/api/reservations/{reservation.id}/reschedule/",
            {
                "start_time": new_start.isoformat(),
                "end_time": new_end.isoformat(),
            },
        )
        assert response.status_code == 200
        assert response.data["start_time"] == new_start.isoformat().replace("+00:00", "Z")
        assert response.data["end_time"] == new_end.isoformat().replace("+00:00", "Z")
        assert response.data["status"] == ReservationStatus.CONFIRMED
        reservation.refresh_from_db()
        assert reservation.start_time == new_start
        assert reservation.end_time == new_end

    def test_reschedule_to_conflicting_slot_is_rejected(self, api_client, regular_user, space):
        """Rescheduling to an overlapping slot should return 400."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
        )
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=now + timedelta(hours=4),
            end_time=now + timedelta(hours=5),
        )
        response = api_client.patch(
            f"/api/reservations/{reservation.id}/reschedule/",
            {
                "start_time": (now + timedelta(hours=2)).isoformat(),
                "end_time": (now + timedelta(hours=4)).isoformat(),
            },
        )
        assert response.status_code == 400
        assert "overlaps" in str(response.data).lower()

    def test_non_owner_cannot_reschedule(self, api_client, regular_user, other_user, space):
        """Non-owners should get 403 when trying to reschedule another user's reservation."""
        api_client.force_authenticate(user=other_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.patch(
            f"/api/reservations/{reservation.id}/reschedule/",
            {
                "start_time": (start + timedelta(hours=2)).isoformat(),
                "end_time": (start + timedelta(hours=3)).isoformat(),
            },
        )
        assert response.status_code == 403

    def test_reschedule_invalid_time_range_is_rejected(self, api_client, regular_user, space):
        """Rescheduling with end_time <= start_time should return 400."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.patch(
            f"/api/reservations/{reservation.id}/reschedule/",
            {
                "start_time": end.isoformat(),
                "end_time": start.isoformat(),
            },
        )
        assert response.status_code == 400
        assert "after start" in str(response.data).lower()

    def test_reschedule_frees_original_slot(self, api_client, regular_user, space):
        """After reschedule, the original slot should be available again."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        original_start = now
        original_end = now + timedelta(hours=1)
        new_start = now + timedelta(hours=2)
        new_end = now + timedelta(hours=3)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=original_start,
            end_time=original_end,
        )
        api_client.patch(
            f"/api/reservations/{reservation.id}/reschedule/",
            {
                "start_time": new_start.isoformat(),
                "end_time": new_end.isoformat(),
            },
        )
        # Original slot should now be available
        response = api_client.post(
            "/api/reservations/",
            {
                "space": space.id,
                "start_time": original_start.isoformat(),
                "end_time": original_end.isoformat(),
            },
        )
        assert response.status_code == 201


class TestReservationApiCheckIn:
    """Tests for checking in to reservations via the API."""

    def test_successful_check_in_within_valid_time_window(self, api_client, regular_user, space):
        """Owner should be able to check in during the valid time window."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        start = now
        end = now + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.post(f"/api/reservations/{reservation.id}/check-in/")
        assert response.status_code == 200
        assert response.data["status"] == ReservationStatus.CHECKED_IN
        assert response.data["checked_in_at"] is not None
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CHECKED_IN
        assert reservation.checked_in_at is not None

    def test_check_in_before_valid_window_is_rejected(self, api_client, regular_user, space):
        """Check-in before the 15-minute window should return 400."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        start = now + timedelta(hours=1)
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.post(f"/api/reservations/{reservation.id}/check-in/")
        assert response.status_code == 400
        assert "check-in" in str(response.data).lower()
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CONFIRMED
        assert reservation.checked_in_at is None

    def test_check_in_on_non_confirmed_reservation_is_rejected(
        self, api_client, regular_user, space
    ):
        """Check-in on a cancelled reservation should return 400."""
        api_client.force_authenticate(user=regular_user)
        now = timezone.now()
        start = now
        end = now + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CANCELLED,
        )
        response = api_client.post(f"/api/reservations/{reservation.id}/check-in/")
        assert response.status_code == 400
        assert "confirmed" in str(response.data).lower()
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED
        assert reservation.checked_in_at is None

    def test_check_in_by_non_owner_is_rejected(self, api_client, regular_user, other_user, space):
        """Non-owners should get 403 when trying to check in to another user's reservation."""
        api_client.force_authenticate(user=other_user)
        now = timezone.now()
        start = now
        end = now + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.post(f"/api/reservations/{reservation.id}/check-in/")
        assert response.status_code == 403
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CONFIRMED
        assert reservation.checked_in_at is None


class TestAutoReleaseNoShows:
    """Tests for the auto-release no-shows service."""

    def test_past_threshold_without_check_in_marked_no_show(self, db, user, space):
        """Confirmed reservation past threshold should be marked no-show."""
        now = timezone.now()
        start = now - timedelta(hours=1)
        end = start + timedelta(hours=2)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CONFIRMED,
        )
        count = auto_release_no_shows(threshold_minutes=15)
        assert count == 1
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.NO_SHOW

    def test_within_threshold_not_marked_no_show(self, db, user, space):
        """Confirmed reservation within threshold should NOT be marked no-show."""
        now = timezone.now()
        start = now - timedelta(minutes=5)
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CONFIRMED,
        )
        count = auto_release_no_shows(threshold_minutes=15)
        assert count == 0
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CONFIRMED

    def test_checked_in_reservation_not_affected(self, db, user, space):
        """Checked-in reservations should not be marked as no-show."""
        now = timezone.now()
        start = now - timedelta(hours=1)
        end = start + timedelta(hours=2)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CHECKED_IN,
            checked_in_at=start,
        )
        count = auto_release_no_shows(threshold_minutes=15)
        assert count == 0
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CHECKED_IN

    def test_cancelled_reservation_not_affected(self, db, user, space):
        """Cancelled reservations should not be marked as no-show."""
        now = timezone.now()
        start = now - timedelta(hours=1)
        end = start + timedelta(hours=2)
        reservation = Reservation.objects.create(
            space=space,
            user=user,
            start_time=start,
            end_time=end,
            status=ReservationStatus.CANCELLED,
        )
        count = auto_release_no_shows(threshold_minutes=15)
        assert count == 0
        reservation.refresh_from_db()
        assert reservation.status == ReservationStatus.CANCELLED


class TestMaintenanceBlockApi:
    """Tests for maintenance block admin API."""

    def test_admin_can_create_maintenance_block(self, api_client, admin_user, space):
        """Admin should be able to create a maintenance block on a free slot."""
        api_client.force_authenticate(user=admin_user)
        start = timezone.now()
        end = start + timedelta(hours=2)
        response = api_client.post(
            "/api/admin/maintenance-blocks/",
            {
                "space": space.id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "reason": "Cleaning",
            },
        )
        assert response.status_code == 201
        assert response.data["space"] == space.id
        assert response.data["reason"] == "Cleaning"
        assert MaintenanceBlock.objects.filter(space=space, reason="Cleaning").exists()

    def test_non_admin_cannot_create_maintenance_block(self, api_client, regular_user, space):
        """Non-admin should get 403 when creating a maintenance block."""
        api_client.force_authenticate(user=regular_user)
        start = timezone.now()
        end = start + timedelta(hours=2)
        response = api_client.post(
            "/api/admin/maintenance-blocks/",
            {
                "space": space.id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "reason": "Cleaning",
            },
        )
        assert response.status_code in (401, 403)

    def test_maintenance_block_overlapping_reservation_is_rejected(
        self, api_client, admin_user, regular_user, space
    ):
        """Maintenance block overlapping a confirmed reservation should return 400."""
        api_client.force_authenticate(user=admin_user)
        start = timezone.now()
        end = start + timedelta(hours=2)
        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )
        response = api_client.post(
            "/api/admin/maintenance-blocks/",
            {
                "space": space.id,
                "start_time": (start + timedelta(minutes=30)).isoformat(),
                "end_time": (start + timedelta(hours=3)).isoformat(),
                "reason": "Cleaning",
            },
        )
        assert response.status_code == 400
        assert "overlaps" in str(response.data).lower()

    def test_maintenance_block_appears_in_availability(self, api_client, admin_user, space):
        """Maintenance block should appear in the space availability check."""
        api_client.force_authenticate(user=admin_user)
        start = timezone.now()
        end = start + timedelta(hours=2)
        MaintenanceBlock.objects.create(
            space=space,
            start_time=start,
            end_time=end,
            reason="Cleaning",
            created_by=admin_user,
        )
        from datetime import date as _date

        today = _date.today()
        response = api_client.get(f"/api/spaces/{space.id}/availability/?date={today.isoformat()}")
        assert response.status_code == 200
        occupied = response.data["occupied"]
        assert any(slot["type"] == "maintenance" for slot in occupied)

    def test_admin_can_list_maintenance_blocks(self, api_client, admin_user, space):
        """Admin should be able to list maintenance blocks."""
        api_client.force_authenticate(user=admin_user)
        MaintenanceBlock.objects.create(
            space=space,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            reason="Cleaning",
            created_by=admin_user,
        )
        response = api_client.get("/api/admin/maintenance-blocks/")
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_non_admin_cannot_list_maintenance_blocks(self, api_client, regular_user):
        """Non-admin should get 403 when listing maintenance blocks."""
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/admin/maintenance-blocks/")
        assert response.status_code in (401, 403)

    def test_admin_can_delete_maintenance_block(self, api_client, admin_user, space):
        """Admin should be able to delete a maintenance block."""
        api_client.force_authenticate(user=admin_user)
        block = MaintenanceBlock.objects.create(
            space=space,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            reason="Cleaning",
            created_by=admin_user,
        )
        response = api_client.delete(f"/api/admin/maintenance-blocks/{block.id}/")
        assert response.status_code == 204
        assert not MaintenanceBlock.objects.filter(id=block.id).exists()


class TestOccupancyApi:
    """Tests for the admin occupancy endpoint."""

    def test_admin_can_view_occupancy(self, api_client, admin_user, regular_user, space):
        """Admin should be able to view occupancy for a given date."""
        api_client.force_authenticate(user=admin_user)
        today = timezone.now().date()

        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
        )

        response = api_client.get(f"/api/admin/occupancy/?date={today.isoformat()}")
        assert response.status_code == 200
        assert response.data["date"] == today.isoformat()
        assert len(response.data["spaces"]) >= 1

        space_data = next(s for s in response.data["spaces"] if s["id"] == space.id)
        assert space_data["name"] == space.name
        assert space_data["capacity"] == space.capacity
        assert space_data["location"] == space.location
        assert len(space_data["reservations"]) == 1
        assert space_data["reservations"][0]["id"] == reservation.id
        assert space_data["reservations"][0]["status"] == ReservationStatus.CONFIRMED

    def test_non_admin_gets_403_on_occupancy(self, api_client, regular_user):
        """Non-admin should get 403 when viewing occupancy."""
        api_client.force_authenticate(user=regular_user)
        today = timezone.now().date()
        response = api_client.get(f"/api/admin/occupancy/?date={today.isoformat()}")
        assert response.status_code in (401, 403)

    def test_occupancy_includes_all_spaces(self, api_client, admin_user, space):
        """Response should include all spaces even if they have no reservations."""
        api_client.force_authenticate(user=admin_user)
        today = timezone.now().date()

        response = api_client.get(f"/api/admin/occupancy/?date={today.isoformat()}")
        assert response.status_code == 200

        space_ids = [s["id"] for s in response.data["spaces"]]
        assert space.id in space_ids

        space_data = next(s for s in response.data["spaces"] if s["id"] == space.id)
        assert space_data["reservations"] == []
        assert space_data["maintenance_blocks"] == []

    def test_occupancy_requires_date_parameter(self, api_client, admin_user):
        """Occupancy endpoint should require date parameter."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/admin/occupancy/")
        assert response.status_code == 400
        assert "date" in str(response.data).lower()

    def test_occupancy_validates_date_format(self, api_client, admin_user):
        """Occupancy endpoint should validate date format."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/admin/occupancy/?date=invalid")
        assert response.status_code == 400
        assert "invalid" in str(response.data).lower()

    def test_occupancy_includes_maintenance_blocks(self, api_client, admin_user, space):
        """Occupancy should include maintenance blocks for the date."""
        api_client.force_authenticate(user=admin_user)
        today = timezone.now().date()

        MaintenanceBlock.objects.create(
            space=space,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=2),
            reason="Cleaning",
            created_by=admin_user,
        )

        response = api_client.get(f"/api/admin/occupancy/?date={today.isoformat()}")
        assert response.status_code == 200

        space_data = next(s for s in response.data["spaces"] if s["id"] == space.id)
        assert len(space_data["maintenance_blocks"]) == 1
        assert space_data["maintenance_blocks"][0]["reason"] == "Cleaning"

    def test_occupancy_shows_reservation_status(self, api_client, admin_user, regular_user, space):
        """Occupancy should distinguish reservation statuses."""
        api_client.force_authenticate(user=admin_user)
        today = timezone.now().date()

        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status=ReservationStatus.CHECKED_IN,
        )

        response = api_client.get(f"/api/admin/occupancy/?date={today.isoformat()}")
        assert response.status_code == 200

        space_data = next(s for s in response.data["spaces"] if s["id"] == space.id)
        assert space_data["reservations"][0]["status"] == ReservationStatus.CHECKED_IN

    def test_occupancy_filters_by_date(self, api_client, admin_user, regular_user, space):
        """Occupancy should only return reservations overlapping the given date."""
        api_client.force_authenticate(user=admin_user)
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
        )

        response = api_client.get(f"/api/admin/occupancy/?date={today.isoformat()}")
        assert response.status_code == 200

        space_data = next(s for s in response.data["spaces"] if s["id"] == space.id)
        assert len(space_data["reservations"]) == 0

        response = api_client.get(f"/api/admin/occupancy/?date={tomorrow.isoformat()}")
        assert response.status_code == 200

        space_data = next(s for s in response.data["spaces"] if s["id"] == space.id)
        assert len(space_data["reservations"]) == 1


@pytest.mark.django_db
class TestReservationCreateView:
    """Tests for the user-facing reservation creation page."""

    def test_get_renders_form_with_space_pre_selected(self, client, regular_user, space):
        """GET should render form with space pre-selected from query param."""
        client.force_login(regular_user)
        response = client.get(f"/reservations/new/?space={space.id}")
        assert response.status_code == 200
        assert "reservations/reservation_form.html" in [t.name for t in response.templates]
        assert response.context["space"] == space

    def test_get_prefills_start_time_from_query(self, client, regular_user, space):
        """GET should prefill date and time from start query parameter."""
        client.force_login(regular_user)
        response = client.get(f"/reservations/new/?space={space.id}&start=2025-12-25T10:00:00Z")
        assert response.status_code == 200
        assert response.context["prefill_date"] == "2025-12-25"
        assert response.context["prefill_start_time"] == "10:00"
        assert response.context["prefill_end_time"] == "11:00"

    def test_valid_post_creates_reservation_and_redirects(self, client, regular_user, space):
        """Valid POST should create reservation and redirect."""
        client.force_login(regular_user)
        response = client.post(
            "/reservations/new/",
            {
                "space": space.id,
                "date": "2025-12-25",
                "start_time": "10:00",
                "end_time": "12:00",
            },
        )
        assert response.status_code == 302
        assert Reservation.objects.filter(
            space=space,
            user=regular_user,
            start_time__year=2025,
            start_time__month=12,
            start_time__day=25,
        ).exists()

    def test_conflicting_post_renders_form_with_error(self, client, regular_user, space):
        """POST with conflicting time should re-render form with error."""
        from datetime import datetime

        from django.utils import timezone

        start = timezone.make_aware(datetime(2025, 12, 25, 10, 0))
        end = timezone.make_aware(datetime(2025, 12, 25, 12, 0))
        Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )

        client.force_login(regular_user)
        response = client.post(
            "/reservations/new/",
            {
                "space": space.id,
                "date": "2025-12-25",
                "start_time": "11:00",
                "end_time": "13:00",
            },
        )
        assert response.status_code == 200
        assert "reservations/reservation_form.html" in [t.name for t in response.templates]
        assert response.context["error"]

    def test_unauthenticated_user_redirected_to_login(self, client, space):
        """Unauthenticated users should be redirected to login."""
        response = client.get(f"/reservations/new/?space={space.id}")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_post_inactive_space_returns_404(self, client, regular_user, inactive_space):
        """POST with inactive space should return 404."""
        client.force_login(regular_user)
        response = client.post(
            "/reservations/new/",
            {
                "space": inactive_space.id,
                "date": "2025-12-25",
                "start_time": "10:00",
                "end_time": "12:00",
            },
        )
        assert response.status_code == 404

    def test_post_invalid_date_renders_error(self, client, regular_user, space):
        """POST with invalid date format should show error."""
        client.force_login(regular_user)
        response = client.post(
            "/reservations/new/",
            {
                "space": space.id,
                "date": "invalid-date",
                "start_time": "10:00",
                "end_time": "12:00",
            },
        )
        assert response.status_code == 200
        assert "Formato de data ou hora inválido" in response.context["error"]


@pytest.mark.django_db
class TestReservationListView:
    """Tests for the user-facing reservation list page."""

    def test_authenticated_user_sees_own_reservations(self, client, regular_user, space):
        """Authenticated users should see their own reservations."""
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )

        client.force_login(regular_user)
        response = client.get("/reservations/")
        assert response.status_code == 200
        assert "reservations/reservation_list.html" in [t.name for t in response.templates]
        assert reservation in response.context["reservations"]

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Unauthenticated users should be redirected to login."""
        response = client.get("/reservations/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url


@pytest.mark.django_db
class TestReservationDetailView:
    """Tests for the user-facing reservation detail page."""

    def test_owner_can_view_detail(self, client, regular_user, space):
        """Reservation owner should be able to view detail."""
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )

        client.force_login(regular_user)
        response = client.get(f"/reservations/{reservation.id}/")
        assert response.status_code == 200
        assert "reservations/reservation_detail.html" in [t.name for t in response.templates]
        assert response.context["reservation"] == reservation

    def test_non_owner_gets_404(self, client, regular_user, other_user, space):
        """Non-owner should get 404 when viewing another user's reservation."""
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=other_user,
            start_time=start,
            end_time=end,
        )

        client.force_login(regular_user)
        response = client.get(f"/reservations/{reservation.id}/")
        assert response.status_code == 404

    def test_unauthenticated_user_redirected_to_login(self, client, regular_user, space):
        """Unauthenticated users should be redirected to login."""
        start = timezone.now()
        end = start + timedelta(hours=1)
        reservation = Reservation.objects.create(
            space=space,
            user=regular_user,
            start_time=start,
            end_time=end,
        )

        response = client.get(f"/reservations/{reservation.id}/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url
