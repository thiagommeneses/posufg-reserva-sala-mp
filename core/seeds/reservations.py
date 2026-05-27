"""Seed sample reservations in pt-BR."""

from datetime import timedelta

from django.utils import timezone

from reservations.models import Reservation, ReservationStatus
from spaces.models import Space

DEFAULT_RESERVATIONS = [
    {
        "username": "maria.silva",
        "space_name": "Sala de Reunião Alfa",
        "start_offset": timedelta(hours=2),
        "end_offset": timedelta(hours=3),
        "status": ReservationStatus.CONFIRMED,
    },
    {
        "username": "joao.santos",
        "space_name": "Sala Focus",
        "start_offset": timedelta(days=-1, hours=10),
        "end_offset": timedelta(days=-1, hours=11),
        "status": ReservationStatus.COMPLETED,
    },
    {
        "username": "ana.costa",
        "space_name": "Sala Executiva",
        "start_offset": timedelta(minutes=-5),
        "end_offset": timedelta(hours=1),
        "status": ReservationStatus.CONFIRMED,
    },
    {
        "username": "joao.santos",
        "space_name": "Sala de Reunião Beta",
        "start_offset": timedelta(days=-1, hours=14),
        "end_offset": timedelta(days=-1, hours=15),
        "status": ReservationStatus.NO_SHOW,
    },
]


def _anchor_now():
    """Return a stable anchor time rounded to the minute."""
    return timezone.now().replace(second=0, microsecond=0)


def seed() -> list[Reservation]:
    """Create sample reservations if they do not exist.

    Returns a list of Reservation instances.
    """
    from django.contrib.auth.models import User

    reservations = []
    now = _anchor_now()

    for res_data in DEFAULT_RESERVATIONS:
        try:
            user = User.objects.get(username=res_data["username"])
            space = Space.objects.get(name=res_data["space_name"])
        except (User.DoesNotExist, Space.DoesNotExist):
            continue

        start_time = now + res_data["start_offset"]
        end_time = now + res_data["end_offset"]

        reservation, created = Reservation.objects.get_or_create(
            user=user,
            space=space,
            start_time=start_time,
            defaults={
                "end_time": end_time,
                "status": res_data["status"],
            },
        )
        if not created:
            reservation.end_time = end_time
            reservation.status = res_data["status"]
            reservation.save()

        reservations.append(reservation)

    return reservations


def flush() -> None:
    """Remove seeded reservations identified by user+space+start_time."""
    from django.contrib.auth.models import User

    now = _anchor_now()
    for res_data in DEFAULT_RESERVATIONS:
        try:
            user = User.objects.get(username=res_data["username"])
            space = Space.objects.get(name=res_data["space_name"])
            start_time = now + res_data["start_offset"]
            Reservation.objects.filter(user=user, space=space, start_time=start_time).delete()
        except (User.DoesNotExist, Space.DoesNotExist):
            pass
