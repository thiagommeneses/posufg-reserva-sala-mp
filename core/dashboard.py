"""What the user's home screen shows, and why each piece is there.

O pacote V2 é explícito sobre o que **não** vai aqui: "sem KPI de vaidade".
Contar quantas reservas alguém já fez não ajuda ninguém a reservar uma sala.
Então esta tela responde três perguntas práticas, nesta ordem:

1. Tenho algo agora ou logo mais? → :func:`proxima_reserva`
2. O que vem depois? → :func:`proximas_reservas`
3. Quero repetir algo que já fiz. → :func:`espacos_para_repetir`

Mais um quarto bloco, ``Informações Úteis``, que não é conteúdo escrito à mão:
sai da política de reserva vigente. Se um administrador mudar o horário de
funcionamento, o texto da tela muda junto — não há como ele envelhecer.
"""

from django.db.models import Max

from reservations.enums import ACTIVE_RESERVATION_STATUSES, ReservationStatus
from reservations.models import Reservation

#: Quantas reservas futuras listar além da próxima. A tela é um resumo; quem
#: quer a lista inteira vai em "Minhas Reservas".
LIMITE_DE_PROXIMAS = 4

#: Quantos espaços oferecer em "Reservar novamente".
LIMITE_DE_REPETICOES = 3


def _reservas_futuras(user, agora):
    """Return the user's still-valid reservations, soonest first.

    Args:
        user: O usuário.
        agora: O instante de referência.

    Returns:
        QuerySet: Reservas ativas que ainda não terminaram.
    """
    return (
        Reservation.objects.filter(
            user=user,
            status__in=ACTIVE_RESERVATION_STATUSES,
            end_time__gt=agora,
        )
        .select_related("space", "space__space_type")
        .order_by("start_time")
    )


def proxima_reserva(user, agora):
    """Return the reservation the user needs to care about right now.

    "Próxima" inclui a que já começou e ainda não terminou: durante a reunião,
    o que interessa é ela, não a de amanhã.

    Args:
        user: O usuário.
        agora: O instante de referência.

    Returns:
        Reservation | None: A reserva mais iminente, se houver.
    """
    return _reservas_futuras(user, agora).first()


def proximas_reservas(user, agora, limite=LIMITE_DE_PROXIMAS):
    """Return the reservations after the most imminent one.

    Args:
        user: O usuário.
        agora: O instante de referência.
        limite: Quantas listar.

    Returns:
        list[Reservation]: As seguintes, já sem a primeira.
    """
    return list(_reservas_futuras(user, agora)[1 : limite + 1])


def espacos_para_repetir(user, limite=LIMITE_DE_REPETICOES):
    """Return the spaces the user actually used, most recent first.

    Só entram espaços de reservas que **aconteceram** — canceladas e
    não comparecimentos ficam de fora. Oferecer "reservar novamente" a partir de
    uma reserva que o usuário cancelou seria sugerir de volta o que ele
    descartou.

    Espaços inativos também ficam de fora: o atalho levaria a uma tela que
    recusaria a reserva.

    Args:
        user: O usuário.
        limite: Quantos espaços devolver.

    Returns:
        list[Space]: Espaços ordenados pelo uso mais recente.
    """
    concluidas = (
        Reservation.objects.filter(
            user=user,
            status__in=[ReservationStatus.COMPLETED, ReservationStatus.CHECKED_IN],
            space__is_active=True,
        )
        .values("space")
        .annotate(ultimo_uso=Max("start_time"))
        .order_by("-ultimo_uso")[:limite]
    )

    ids = [linha["space"] for linha in concluidas]
    if not ids:
        return []

    from spaces.models import Space

    espacos = {
        espaco.pk: espaco
        for espaco in Space.objects.filter(pk__in=ids).select_related("space_type")
    }
    return [espacos[pk] for pk in ids if pk in espacos]


def informacoes_uteis(policy):
    """Return the practical rules the user needs, straight from the policy.

    Cada item aqui é uma regra que o sistema realmente aplica **agora**.

    O no-show ficou de fora, mas a razão mudou e vale corrigir o registro: o
    agendador passou a existir como serviço próprio (``manage.py agendador``),
    então a liberação acontece de verdade quando ``release_no_shows`` está
    ligado. O motivo de não estar neste cartão é outro — a resposta honesta
    depende de a regra estar ligada ou não, e um par rótulo/valor não tem onde
    dizer isso. Quem dá a resposta completa, nos dois casos, é a tela de Ajuda
    (:func:`core.ajuda.perguntas_frequentes`).

    Args:
        policy: A política de reserva vigente.

    Returns:
        list[dict]: Itens com ``rotulo``, ``valor`` e ``icone``.
    """
    from reservations.services import CHECK_IN_WINDOW_MINUTES

    return [
        {
            "rotulo": "Horário de funcionamento",
            "valor": f"{policy.opening_time:%H:%M} às {policy.closing_time:%H:%M}",
            "icone": "clock",
        },
        {
            "rotulo": "Duração da reserva",
            "valor": (f"de {policy.min_duration_minutes} a {policy.max_duration_minutes} minutos"),
            "icone": "sliders",
        },
        {
            "rotulo": "Antecedência máxima",
            "valor": f"{policy.horizon_days} dias",
            "icone": "calendar",
        },
        {
            "rotulo": "Check-in",
            "valor": (
                f"de {CHECK_IN_WINDOW_MINUTES} minutos antes do início até o horário de término"
            ),
            "icone": "check",
        },
    ]
