"""Tests for the reservations app."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
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
