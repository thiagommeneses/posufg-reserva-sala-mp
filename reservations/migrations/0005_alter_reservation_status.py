"""Translate the reservation status labels shown in the interface.

Só metadado: ``choices`` não existe no PostgreSQL, então esta migração não
toca em nenhuma linha e não tem o que reverter em dados. Ela existe porque
o Django detecta a mudança de ``choices`` e, sem ela, ``makemigrations``
acusaria alterações pendentes para sempre.

Os valores gravados continuam os mesmos — ``confirmed``, ``cancelled`` e os
demais. O que mudou é o texto que a interface mostra.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Rótulos de ``ReservationStatus`` em português."""

    dependencies = [
        ("reservations", "0004_reservation_attendee_count_reservation_notes_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reservation",
            name="status",
            field=models.CharField(
                choices=[
                    ("confirmed", "Confirmada"),
                    ("cancelled", "Cancelada"),
                    ("checked_in", "Check-in realizado"),
                    ("completed", "Concluída"),
                    ("no_show", "Não compareceu"),
                ],
                default="confirmed",
                max_length=20,
            ),
        ),
    ]
