"""Seed default users in pt-BR."""

import os

from django.contrib.auth.models import User

DEFAULT_USERS = [
    {
        "username": "admin",
        "first_name": "Administrador",
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "username": "maria.silva",
        "first_name": "Maria Silva",
        "is_staff": False,
        "is_superuser": False,
    },
    {
        "username": "joao.santos",
        "first_name": "João Santos",
        "is_staff": False,
        "is_superuser": False,
    },
    {
        "username": "ana.costa",
        "first_name": "Ana Costa",
        "is_staff": False,
        "is_superuser": False,
    },
]

DEFAULT_PASSWORD = os.environ.get("SEED_DEFAULT_PASSWORD", "reserva123")


def seed() -> dict[str, User]:
    """Create default users if they do not exist.

    Returns a mapping of username to User instance.
    """
    users = {}
    for user_data in DEFAULT_USERS:
        username = user_data["username"]
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": user_data["first_name"],
                "is_staff": user_data["is_staff"],
                "is_superuser": user_data["is_superuser"],
            },
        )
        if not created:
            user.first_name = user_data["first_name"]
            user.is_staff = user_data["is_staff"]
            user.is_superuser = user_data["is_superuser"]
            user.save()

        user.set_password(DEFAULT_PASSWORD)
        user.save()
        users[username] = user

    return users


def flush() -> None:
    """Remove seeded users (identified by username)."""
    usernames = [u["username"] for u in DEFAULT_USERS]
    User.objects.filter(username__in=usernames).delete()
