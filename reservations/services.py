"""Services for the reservations app."""

import datetime

from django.core.exceptions import ValidationError
from django.db import models

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus


def get_availability_for_date(space, date):
    """Return occupied and free time slots for a space on a given date.

    Args:
        space: A Space instance.
        date: A date object representing the day to check.

    Returns:
        dict: {
            "date": str(date),
            "occupied": [
                {"start": ISO8601, "end": ISO8601, "type": "reservation" | "maintenance"}
            ],
            "free": [
                {"start": ISO8601, "end": ISO8601}
            ],
        }
    """
    date_start = datetime.datetime.combine(date, datetime.time.min).replace(
        tzinfo=datetime.UTC,
    )
    date_end = date_start + datetime.timedelta(days=1)

    reservations = Reservation.objects.filter(
        space=space,
        status__in=[ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN],
        start_time__lt=date_end,
        end_time__gt=date_start,
    )

    maintenance_blocks = MaintenanceBlock.objects.filter(
        space=space,
        start_time__lt=date_end,
        end_time__gt=date_start,
    )

    occupied_intervals = []

    for reservation in reservations:
        occupied_start = max(reservation.start_time, date_start)
        occupied_end = min(reservation.end_time, date_end)
        occupied_intervals.append((occupied_start, occupied_end, "reservation"))

    for block in maintenance_blocks:
        block_start = max(block.start_time, date_start)
        block_end = min(block.end_time, date_end)
        occupied_intervals.append((block_start, block_end, "maintenance"))

    occupied_intervals.sort(key=lambda interval: interval[0])

    merged = []
    for start, end, typ in occupied_intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (
                merged[-1][0],
                max(merged[-1][1], end),
                merged[-1][2],
            )
        else:
            merged.append((start, end, typ))

    occupied = []
    for start, end, typ in merged:
        occupied.append(
            {
                "start": _isoformat(start),
                "end": _isoformat(end),
                "type": typ,
            }
        )

    free = []
    current = date_start

    for start, end, _typ in merged:
        if start > current:
            free.append(
                {
                    "start": _isoformat(current),
                    "end": _isoformat(start),
                }
            )
        current = max(current, end)

    if current < date_end:
        free.append(
            {
                "start": _isoformat(current),
                "end": _isoformat(date_end),
            }
        )

    return {
        "date": str(date),
        "occupied": occupied,
        "free": free,
    }


def create_reservation(user, space, start_time, end_time):
    """Create a new reservation with conflict validation.

    Args:
        user: The user making the reservation.
        space: The space to reserve.
        start_time: The reservation start time.
        end_time: The reservation end time.

    Returns:
        Reservation: The created reservation.

    Raises:
        ValidationError: If the space is inactive, times are invalid,
            or there is an overlap with existing reservations or maintenance blocks.
    """
    if not space.is_active:
        raise ValidationError("This space is not available for reservations.")

    if end_time <= start_time:
        raise ValidationError("End time must be after start time.")

    overlapping_reservations = Reservation.objects.filter(
        space=space,
        status__in=[ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN],
    ).filter(
        models.Q(start_time__lt=end_time) & models.Q(end_time__gt=start_time),
    )
    if overlapping_reservations.exists():
        raise ValidationError("This time slot overlaps with an existing reservation.")

    overlapping_blocks = MaintenanceBlock.objects.filter(
        space=space,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if overlapping_blocks.exists():
        raise ValidationError("This time slot overlaps with a maintenance block.")

    return Reservation.objects.create(
        space=space,
        user=user,
        start_time=start_time,
        end_time=end_time,
        status=ReservationStatus.CONFIRMED,
    )


def _isoformat(dt):
    """Return ISO 8601 string with Z suffix for UTC datetimes."""
    return dt.isoformat().replace("+00:00", "Z")
