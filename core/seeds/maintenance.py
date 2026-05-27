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
    """Return a stable anchor time rounded to the minute."""
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

        block, created = MaintenanceBlock.objects.get_or_create(
            space=space,
            start_time=start_time,
            end_time=end_time,
            defaults={
                "reason": block_data["reason"],
                "created_by": admin,
            },
        )
        if not created:
            block.reason = block_data["reason"]
            block.created_by = admin
            block.save()

        blocks.append(block)

    return blocks


def flush() -> None:
    """Remove seeded maintenance blocks identified by space+start_time+reason."""
    now = _anchor_now()
    for block_data in DEFAULT_BLOCKS:
        try:
            space = Space.objects.get(name=block_data["space_name"])
            start_time = now + block_data["start_offset"]
            MaintenanceBlock.objects.filter(
                space=space, start_time=start_time, reason=block_data["reason"]
            ).delete()
        except Space.DoesNotExist:
            pass
