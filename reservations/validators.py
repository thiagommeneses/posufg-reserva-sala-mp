"""Single source of truth for reservation and maintenance scheduling rules.

Before this module existed, the same overlap rules were re-implemented in
``Reservation.clean()``, in the DRF serializers, in the service layer and in the
admin dashboard forms — four copies that could silently drift apart. Every layer
now delegates here, so a rule is written once and enforced everywhere.

Queries go through the related managers of ``spaces.Space`` (``reservations``
and ``maintenance_blocks``) instead of importing ``reservations.models``. That
keeps this module free of a dependency on the models and therefore importable
by them.

All functions raise :class:`django.core.exceptions.ValidationError` with a
stable ``code``, so callers that need field-level errors (DRF serializers) can
map a code to a field without matching on message text.
"""

from django.core.exceptions import ValidationError

from reservations.enums import ACTIVE_RESERVATION_STATUSES

# Error codes — the stable contract for callers that translate these errors.
SPACE_INACTIVE_CODE = "space_inactive"
INVALID_TIME_RANGE_CODE = "invalid_time_range"
RESERVATION_OVERLAP_CODE = "reservation_overlap"
MAINTENANCE_OVERLAP_CODE = "maintenance_overlap"
MAINTENANCE_RESERVATION_OVERLAP_CODE = "maintenance_reservation_overlap"

SPACE_INACTIVE_MESSAGE = "This space is not available for reservations."
INVALID_TIME_RANGE_MESSAGE = "End time must be after start time."
RESERVATION_OVERLAP_MESSAGE = "This time slot overlaps with an existing reservation."
MAINTENANCE_OVERLAP_MESSAGE = "This time slot overlaps with a maintenance block."
MAINTENANCE_RESERVATION_OVERLAP_MESSAGE = (
    "This maintenance block overlaps with an existing reservation."
)


def active_reservations_overlapping(space, start_time, end_time, *, exclude_pk=None):
    """Return the reservations that still hold ``space`` during the given interval.

    Args:
        space: The Space instance to inspect.
        start_time: Start of the interval being checked.
        end_time: End of the interval being checked.
        exclude_pk: Primary key of a reservation to ignore (used when
            rescheduling, so a reservation does not conflict with itself).

    Returns:
        QuerySet: Overlapping reservations in an active status.
    """
    queryset = space.reservations.filter(
        status__in=ACTIVE_RESERVATION_STATUSES,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset


def maintenance_blocks_overlapping(space, start_time, end_time):
    """Return the maintenance blocks covering ``space`` during the given interval.

    Args:
        space: The Space instance to inspect.
        start_time: Start of the interval being checked.
        end_time: End of the interval being checked.

    Returns:
        QuerySet: Overlapping maintenance blocks.
    """
    return space.maintenance_blocks.filter(
        start_time__lt=end_time,
        end_time__gt=start_time,
    )


def validate_time_range(start_time, end_time):
    """Ensure the interval is well formed.

    Raises:
        ValidationError: If ``end_time`` is not strictly after ``start_time``.
    """
    if end_time <= start_time:
        raise ValidationError(INVALID_TIME_RANGE_MESSAGE, code=INVALID_TIME_RANGE_CODE)


def validate_no_reservation_overlap(space, start_time, end_time, *, exclude_pk=None):
    """Ensure no active reservation already holds the space in the interval.

    Raises:
        ValidationError: If an overlapping active reservation exists.
    """
    if active_reservations_overlapping(space, start_time, end_time, exclude_pk=exclude_pk).exists():
        raise ValidationError(RESERVATION_OVERLAP_MESSAGE, code=RESERVATION_OVERLAP_CODE)


def validate_reservation_slot(
    space,
    start_time,
    end_time,
    *,
    exclude_pk=None,
    require_active_space=True,
):
    """Validate every rule that must hold for a space to be reserved.

    Args:
        space: The Space being reserved.
        start_time: Desired start of the reservation.
        end_time: Desired end of the reservation.
        exclude_pk: Reservation to ignore when checking overlaps (rescheduling).
        require_active_space: Whether an inactive space should be rejected.
            Disabled when rescheduling, so an existing reservation stays
            manageable even if its space was later deactivated.

    Raises:
        ValidationError: If the space is inactive, the interval is invalid, or
            it overlaps an active reservation or a maintenance block.
    """
    if require_active_space and not space.is_active:
        raise ValidationError(SPACE_INACTIVE_MESSAGE, code=SPACE_INACTIVE_CODE)

    validate_time_range(start_time, end_time)
    validate_no_reservation_overlap(space, start_time, end_time, exclude_pk=exclude_pk)

    if maintenance_blocks_overlapping(space, start_time, end_time).exists():
        raise ValidationError(MAINTENANCE_OVERLAP_MESSAGE, code=MAINTENANCE_OVERLAP_CODE)


def validate_maintenance_slot(space, start_time, end_time):
    """Validate every rule that must hold for a maintenance block to be created.

    Args:
        space: The Space being blocked.
        start_time: Desired start of the block.
        end_time: Desired end of the block.

    Raises:
        ValidationError: If the interval is invalid or it would override an
            active reservation.
    """
    validate_time_range(start_time, end_time)

    if active_reservations_overlapping(space, start_time, end_time).exists():
        raise ValidationError(
            MAINTENANCE_RESERVATION_OVERLAP_MESSAGE,
            code=MAINTENANCE_RESERVATION_OVERLAP_CODE,
        )
