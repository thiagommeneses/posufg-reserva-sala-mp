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
    """Return the reference time for the sample reservations, rounded to the minute."""
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

        # A identidade é (usuário, espaço), não o horário. Os horários derivam de
        # timezone.now() e portanto mudam entre execuções; usá-los como chave faria a
        # segunda execução tentar inserir uma reserva deslocada em alguns minutos, que
        # colide com a primeira na exclusion constraint. Cada par abaixo é único em
        # DEFAULT_RESERVATIONS, o que torna a chave estável.
        reservation, created = Reservation.objects.get_or_create(
            user=user,
            space=space,
            defaults={
                "start_time": start_time,
                "end_time": end_time,
                "status": res_data["status"],
            },
        )
        if not created:
            reservation.start_time = start_time
            reservation.end_time = end_time
            reservation.status = res_data["status"]
            reservation.save(
                update_fields=["start_time", "end_time", "status", "updated_at"],
            )

        reservations.append(reservation)

    return reservations


def flush() -> None:
    """Remove seeded reservations, identified by the same user+space key used to seed."""
    from django.contrib.auth.models import User

    for res_data in DEFAULT_RESERVATIONS:
        try:
            user = User.objects.get(username=res_data["username"])
            space = Space.objects.get(name=res_data["space_name"])
        except (User.DoesNotExist, Space.DoesNotExist):
            continue
        Reservation.objects.filter(user=user, space=space).delete()
