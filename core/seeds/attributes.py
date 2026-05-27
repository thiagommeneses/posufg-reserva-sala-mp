"""Seed default space attributes in pt-BR."""

from spaces.models import Attribute

DEFAULT_ATTRIBUTES = [
    "Ar-condicionado",
    "Projetor",
    "TV",
    "Webcam",
    "Quadro branco",
    "Videoconferência",
    "Wi-Fi",
]


def seed() -> dict[str, Attribute]:
    """Create default attributes if they do not exist.

    Returns a mapping of attribute name to Attribute instance.
    """
    attributes = {}
    for name in DEFAULT_ATTRIBUTES:
        attribute, _ = Attribute.objects.get_or_create(name=name)
        attributes[name] = attribute
    return attributes


def flush() -> None:
    """Remove seeded attributes (identified by name)."""
    Attribute.objects.filter(name__in=DEFAULT_ATTRIBUTES).delete()
