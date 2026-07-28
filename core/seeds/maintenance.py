"""Seed sample maintenance blocks in pt-BR."""

from datetime import timedelta

from django.utils import timezone

from reservations.models import MaintenanceBlock
from spaces.models import Space

DEFAULT_BLOCKS = [
    {
        "space_name": "Auditório Central",
        "reason": "Limpeza pós-evento",
        "start_offset": timedelta(days=1, hours=8),
        "end_offset": timedelta(days=1, hours=10),
    },
    {
        "space_name": "Sala de Reunião Beta",
        "reason": "Manutenção do ar-condicionado",
        "start_offset": timedelta(days=7, hours=14),
        "end_offset": timedelta(days=7, hours=16),
    },
]


def _anchor_now():
    """Return the reference time for the sample blocks, rounded to the minute."""
    return timezone.now().replace(second=0, microsecond=0)


def seed() -> list[MaintenanceBlock]:
    """Create sample maintenance blocks if they do not exist.

    Returns a list of MaintenanceBlock instances.
    """
    from django.contrib.auth.models import User

    blocks = []
    now = _anchor_now()

    for block_data in DEFAULT_BLOCKS:
        try:
            space = Space.objects.get(name=block_data["space_name"])
            admin = User.objects.get(username="admin")
        except (Space.DoesNotExist, User.DoesNotExist):
            continue

        start_time = now + block_data["start_offset"]
        end_time = now + block_data["end_offset"]

        # Identidade por (espaço, motivo), pelo mesmo motivo dos seeds de reserva: os
        # horários derivam de timezone.now() e mudam a cada execução. Aqui não existe
        # exclusion constraint, então usar o horário como chave não quebrava — apenas
        # duplicava os bloqueios em silêncio a cada nova execução.
        block, created = MaintenanceBlock.objects.get_or_create(
            space=space,
            reason=block_data["reason"],
            defaults={
                "start_time": start_time,
                "end_time": end_time,
                "created_by": admin,
            },
        )
        if not created:
            block.start_time = start_time
            block.end_time = end_time
            block.created_by = admin
            block.save(
                update_fields=["start_time", "end_time", "created_by", "updated_at"],
            )

        blocks.append(block)

    return blocks


def flush() -> None:
    """Remove seeded maintenance blocks, identified by the same space+reason key."""
    for block_data in DEFAULT_BLOCKS:
        try:
            space = Space.objects.get(name=block_data["space_name"])
        except Space.DoesNotExist:
            continue
        MaintenanceBlock.objects.filter(space=space, reason=block_data["reason"]).delete()
