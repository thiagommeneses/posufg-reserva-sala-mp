"""Seed the service catalog suggested by the V2 package.

Os serviços vêm sem espaço vinculado de propósito. Quais salas oferecem café e
quais oferecem apoio audiovisual é uma decisão da administração do MPGO, e
inventá-la aqui faria a tela de reserva oferecer, no primeiro dia, serviços que
ninguém combinou executar. Enquanto ninguém vincular, o passo 3 simplesmente
não mostra serviço nenhum — o que é verdade.

As antecedências são o mesmo caso: começam em zero. Um número inventado ou
recusaria pedidos legítimos ou prometeria o impossível. Quem sabe quantas horas
a copa precisa é a copa.

Idempotente por ``slug``. A reversão só remove serviços que ninguém pediu e que
ninguém vinculou a um espaço — um catálogo já em uso não é desfeito por uma
migration.
"""

from django.db import migrations

#: (nome, slug, categoria, ícone, descrição, exige detalhamento, ordem)
CATALOGO = [
    (
        "Copeira / café e água",
        "copeira",
        "Apoio",
        "sparkles",
        "Serviço de copa durante o encontro.",
        False,
        10,
    ),
    (
        "Apoio audiovisual / TI",
        "apoio-audiovisual",
        "Apoio",
        "presentation",
        "Acompanhamento técnico para projeção, som e computadores.",
        True,
        20,
    ),
    (
        "Videoconferência",
        "videoconferencia",
        "Apoio",
        "video",
        "Preparação e acompanhamento da chamada.",
        True,
        30,
    ),
    (
        "Recepção de convidados",
        "recepcao",
        "Apoio",
        "users",
        "Recepção e encaminhamento de participantes externos.",
        True,
        40,
    ),
    (
        "Configuração da sala",
        "configuracao-da-sala",
        "Preparação",
        "grid",
        "Disposição de mesas e cadeiras conforme o formato do encontro.",
        True,
        50,
    ),
    (
        "Limpeza após término",
        "limpeza",
        "Preparação",
        "clear",
        "Limpeza da sala depois do encerramento.",
        False,
        60,
    ),
    (
        "Recursos de acessibilidade",
        "acessibilidade",
        "Inclusão",
        "help",
        "Apoio para garantir a participação de todos. Não é necessário informar motivo.",
        # Sem detalhamento obrigatório, de propósito: o pacote V2 proíbe coletar
        # motivo médico ou dado sensível para solicitar acessibilidade. Quem
        # quiser descrever o que precisa pode; ninguém é obrigado a justificar.
        False,
        70,
    ),
]


def criar_catalogo(apps, schema_editor):
    """Create the suggested services if they are not there yet."""
    ServiceType = apps.get_model("services", "ServiceType")
    for nome, slug, categoria, icone, descricao, exige_notas, ordem in CATALOGO:
        ServiceType.objects.get_or_create(
            slug=slug,
            defaults={
                "name": nome,
                "category": categoria,
                "icon_name": icone,
                "description": descricao,
                "requires_notes": exige_notas,
                "min_lead_time_hours": 0,
                "is_active": True,
                "sort_order": ordem,
            },
        )


def remover_catalogo(apps, schema_editor):
    """Remove the seeded services, keeping any already in use."""
    ServiceType = apps.get_model("services", "ServiceType")
    slugs = [slug for _, slug, _, _, _, _, _ in CATALOGO]
    ServiceType.objects.filter(slug__in=slugs, requests__isnull=True, spaces__isnull=True).delete()


class Migration(migrations.Migration):
    """Populate the service catalog."""

    dependencies = [
        ("services", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(criar_catalogo, remover_catalogo),
    ]
