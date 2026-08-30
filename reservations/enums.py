"""Enumerations and status groupings for the reservations app.

Kept in a dedicated module (instead of ``reservations.models``) so that
``reservations.validators`` can be imported by the models themselves without
creating a circular import.
"""

from django.db import models


class ReservationStatus(models.TextChoices):
    """Status choices for a reservation.

    Os rótulos estão em português porque são texto de interface: aparecem no
    admin do Django, na API navegável e em qualquer tela que chame
    ``get_status_display``. Estavam em inglês, e por isso a tela de detalhes
    exibia "Confirmed" ao lado de um badge que dizia "Confirmada" — a mesma
    reserva descrita de dois jeitos, um deles no idioma errado.

    Os **valores** continuam em inglês e não podem mudar: são o que está gravado
    no banco e o que a API publica. Traduzi-los quebraria integrações e exigiria
    migração de dados; traduzir os rótulos não muda um byte de dado.
    """

    CONFIRMED = "confirmed", "Confirmada"
    CANCELLED = "cancelled", "Cancelada"
    CHECKED_IN = "checked_in", "Check-in realizado"
    COMPLETED = "completed", "Concluída"
    NO_SHOW = "no_show", "Não compareceu"


#: Statuses that still hold the space: only these block a time slot.
ACTIVE_RESERVATION_STATUSES = (
    ReservationStatus.CONFIRMED,
    ReservationStatus.CHECKED_IN,
)
