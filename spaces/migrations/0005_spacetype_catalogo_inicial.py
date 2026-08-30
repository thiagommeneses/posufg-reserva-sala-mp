"""Seed the initial catalog of space types.

O catálogo sugerido pelo pacote V2. É uma data migration, e não um seed de
demonstração, porque as abas da tela de reserva dependem de existir pelo menos
um tipo — um banco recém-migrado precisa já ter o catálogo.

Idempotente: usa ``get_or_create`` pelo slug, então rodar de novo não duplica.
A reversão só remove os tipos que esta migration criou, e apenas se nenhum
espaço estiver usando — nunca apaga uma classificação feita por um humano.
"""

from django.db import migrations

CATALOGO = [
    ("Sala de Reunião", "sala-de-reuniao", "users", 10),
    ("Auditório", "auditorio", "presentation", 20),
    ("Sala de Treinamento", "sala-de-treinamento", "book", 30),
    ("Espaço Compartilhado", "espaco-compartilhado", "layers", 40),
    ("Sala Executiva", "sala-executiva", "briefcase", 50),
    ("Outro", "outro", "grid", 90),
]


def criar_catalogo(apps, schema_editor):
    """Create the initial space types if they are not there yet."""
    SpaceType = apps.get_model("spaces", "SpaceType")
    for nome, slug, icone, ordem in CATALOGO:
        SpaceType.objects.get_or_create(
            slug=slug,
            defaults={
                "name": nome,
                "icon_name": icone,
                "sort_order": ordem,
                "is_active": True,
            },
        )


def remover_catalogo(apps, schema_editor):
    """Remove the seeded types, keeping any that are already in use."""
    SpaceType = apps.get_model("spaces", "SpaceType")
    slugs = [slug for _, slug, _, _ in CATALOGO]
    SpaceType.objects.filter(slug__in=slugs, spaces__isnull=True).delete()


class Migration(migrations.Migration):
    """Populate the space type catalog."""

    dependencies = [
        ("spaces", "0004_spacetype_space_space_type"),
    ]

    operations = [
        migrations.RunPython(criar_catalogo, remover_catalogo),
    ]
