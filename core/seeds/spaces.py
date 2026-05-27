"""Seed default spaces in pt-BR with attributes."""

from spaces.models import Attribute, Space, SpaceAttribute

DEFAULT_SPACES = [
    {
        "name": "Sala de Reunião Alfa",
        "location": "2º andar, Bloco A",
        "capacity": 8,
        "attributes": ["Ar-condicionado", "TV", "Videoconferência", "Wi-Fi"],
    },
    {
        "name": "Sala de Reunião Beta",
        "location": "3º andar, Bloco B",
        "capacity": 12,
        "attributes": ["Ar-condicionado", "Projetor", "Quadro branco", "Wi-Fi"],
    },
    {
        "name": "Sala Focus",
        "location": "1º andar, Bloco C",
        "capacity": 4,
        "attributes": ["Ar-condicionado", "Webcam", "Wi-Fi"],
    },
    {
        "name": "Auditório Central",
        "location": "Térreo",
        "capacity": 50,
        "attributes": [
            "Ar-condicionado",
            "Projetor",
            "TV",
            "Videoconferência",
            "Wi-Fi",
        ],
    },
    {
        "name": "Sala Executiva",
        "location": "4º andar, Bloco A",
        "capacity": 6,
        "attributes": [
            "Ar-condicionado",
            "TV",
            "Webcam",
            "Videoconferência",
            "Wi-Fi",
        ],
    },
]


def seed() -> dict[str, Space]:
    """Create default spaces if they do not exist.

    Returns a mapping of space name to Space instance.
    """
    spaces = {}
    for space_data in DEFAULT_SPACES:
        attribute_names = space_data["attributes"]
        space, created = Space.objects.get_or_create(
            name=space_data["name"],
            defaults={
                "location": space_data["location"],
                "capacity": space_data["capacity"],
                "is_active": True,
            },
        )
        if not created:
            space.location = space_data["location"]
            space.capacity = space_data["capacity"]
            space.is_active = True
            space.save()

        for attr_name in attribute_names:
            try:
                attribute = Attribute.objects.get(name=attr_name)
                SpaceAttribute.objects.get_or_create(space=space, attribute=attribute)
            except Attribute.DoesNotExist:
                pass

        spaces[space_data["name"]] = space

    return spaces


def flush() -> None:
    """Remove seeded spaces (identified by name) and their attribute links."""
    space_names = [s["name"] for s in DEFAULT_SPACES]
    SpaceAttribute.objects.filter(space__name__in=space_names).delete()
    Space.objects.filter(name__in=space_names).delete()
