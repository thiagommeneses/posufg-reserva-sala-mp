"""Create the single booking policy row with the default parameters.

A política precisa existir antes da primeira tela: ``BookingPolicy.carregar()``
cria a linha sob demanda, mas deixar isso acontecer no primeiro acesso faria a
criação depender de qual requisição chega primeiro — inclusive uma requisição
somente-leitura. Criar aqui torna o estado inicial explícito e igual em todos os
ambientes.

Os valores são os ``default`` do modelo, repetidos de propósito: uma migration
descreve o estado do banco naquele momento e não deve mudar de comportamento
quando alguém alterar um default do modelo no futuro.

``enforce_window`` fica desligado. Ligar significa recusar reservas fora da
janela, e essa decisão exige olhar as reservas já existentes — é do
administrador, não desta migration.
"""

import datetime

from django.db import migrations

PK_UNICO = 1

PADRAO = {
    "opening_time": datetime.time(8, 0),
    "closing_time": datetime.time(18, 0),
    "slot_minutes": 30,
    "min_duration_minutes": 30,
    "max_duration_minutes": 240,
    "horizon_days": 90,
    "few_slots_threshold": 3,
    "enforce_window": False,
}


def criar_politica(apps, schema_editor):
    """Create the policy row if it is not there yet."""
    BookingPolicy = apps.get_model("reservations", "BookingPolicy")
    BookingPolicy.objects.get_or_create(pk=PK_UNICO, defaults=PADRAO)


def remover_politica(apps, schema_editor):
    """Remove the policy row only if it still holds the default values.

    Uma política editada por um administrador não pode ser apagada por uma
    reversão de migration.
    """
    BookingPolicy = apps.get_model("reservations", "BookingPolicy")
    BookingPolicy.objects.filter(pk=PK_UNICO, **PADRAO).delete()


class Migration(migrations.Migration):
    """Seed the booking policy."""

    dependencies = [
        ("reservations", "0002_bookingpolicy"),
    ]

    operations = [
        migrations.RunPython(criar_politica, remover_politica),
    ]
