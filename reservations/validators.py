"""Single source of truth for reservation and maintenance scheduling rules.

Before this module existed, the same overlap rules were re-implemented in
``Reservation.clean()``, in the DRF serializers, in the service layer and in the
admin dashboard forms — four copies that could silently drift apart. Every layer
now delegates here, so a rule is written once and enforced everywhere.

Queries go through the related managers of ``spaces.Space`` (``reservations``
and ``maintenance_blocks``) instead of importing ``reservations.models``. That
keeps this module free of a dependency on the models and therefore importable
by them.

All functions raise :class:`django.core.exceptions.ValidationError` with a
stable ``code``, so callers that need field-level errors (DRF serializers) can
map a code to a field without matching on message text.
"""

import datetime

from django.core.exceptions import ValidationError
from django.utils import timezone

from reservations.enums import ACTIVE_RESERVATION_STATUSES

# Error codes — the stable contract for callers that translate these errors.
SPACE_INACTIVE_CODE = "space_inactive"
INVALID_TIME_RANGE_CODE = "invalid_time_range"
RESERVATION_OVERLAP_CODE = "reservation_overlap"
MAINTENANCE_OVERLAP_CODE = "maintenance_overlap"
MAINTENANCE_RESERVATION_OVERLAP_CODE = "maintenance_reservation_overlap"
ATTENDEE_COUNT_INVALID_CODE = "attendee_count_invalid"
ATTENDEE_COUNT_OVER_CAPACITY_CODE = "attendee_count_over_capacity"
OUTSIDE_OPERATING_HOURS_CODE = "outside_operating_hours"
CLOSED_DAY_CODE = "closed_day"
DURATION_TOO_SHORT_CODE = "duration_too_short"
DURATION_TOO_LONG_CODE = "duration_too_long"
OUTSIDE_HORIZON_CODE = "outside_horizon"

#: Erros que a pessoa só resolve mexendo em data, início ou término. A interface
#: usa este agrupamento para revelar o bloco de horário ao devolver o
#: formulário: mandar corrigir algo que está escondido é o mesmo que não dizer
#: nada. Fica aqui, e não na view, porque quem acrescenta um ``code`` novo
#: precisa decidir na mesma hora a que grupo ele pertence.
CODIGOS_DE_HORARIO = frozenset(
    {
        INVALID_TIME_RANGE_CODE,
        RESERVATION_OVERLAP_CODE,
        MAINTENANCE_OVERLAP_CODE,
        MAINTENANCE_RESERVATION_OVERLAP_CODE,
        OUTSIDE_OPERATING_HOURS_CODE,
        CLOSED_DAY_CODE,
        DURATION_TOO_SHORT_CODE,
        DURATION_TOO_LONG_CODE,
        OUTSIDE_HORIZON_CODE,
    }
)

#: Mensagens exibidas ao usuário final. Os ``code`` acima são o contrato estável
#: para quem precisa mapear erro → campo; o texto pode ser reescrito livremente.
SPACE_INACTIVE_MESSAGE = "Este espaço não está disponível para reserva."
INVALID_TIME_RANGE_MESSAGE = "O horário de término deve ser posterior ao de início."
RESERVATION_OVERLAP_MESSAGE = "Este horário já está reservado para o espaço escolhido."
MAINTENANCE_OVERLAP_MESSAGE = "Este horário está bloqueado para manutenção."
MAINTENANCE_RESERVATION_OVERLAP_MESSAGE = (
    "Já existe uma reserva neste intervalo. Cancele a reserva antes de bloquear o espaço."
)


ATTENDEE_COUNT_INVALID_MESSAGE = "Informe quantas pessoas devem comparecer."


def _mensagem_acima_da_capacidade(space):
    """Return the over-capacity message naming the space limit."""
    return f"{space.name} comporta até {space.capacity} pessoa{'s' if space.capacity != 1 else ''}."


def validate_attendee_count(space, attendee_count):
    """Ensure the number of attendees fits the space.

    A regra é do domínio, não do formulário: a mesma verificação precisa valer
    para a tela, para a API e para qualquer script que crie reserva. Um número
    ausente é aceito — as reservas anteriores à Fase 10 não têm esse dado, e
    exigir o campo aqui invalidaria o histórico.

    Args:
        space: O espaço reservado.
        attendee_count: Quantas pessoas devem comparecer, ou ``None``.

    Raises:
        ValidationError: Se o número for zero, negativo ou maior que a
            capacidade do espaço.
    """
    if attendee_count is None:
        return
    if attendee_count < 1:
        raise ValidationError(ATTENDEE_COUNT_INVALID_MESSAGE, code=ATTENDEE_COUNT_INVALID_CODE)
    if attendee_count > space.capacity:
        raise ValidationError(
            _mensagem_acima_da_capacidade(space),
            code=ATTENDEE_COUNT_OVER_CAPACITY_CODE,
        )


def _mensagem_fora_do_horario(policy):
    """Return the out-of-hours message naming the configured window."""
    return f"As reservas acontecem entre {policy.opening_time:%H:%M} e {policy.closing_time:%H:%M}."


def dias_por_extenso(policy):
    """Return the open weekdays as a phrase people actually say.

    "de segunda-feira a sexta-feira" quando os dias são corridos, "apenas
    quarta-feira" quando é um só, "segunda-feira, quarta-feira e sexta-feira"
    quando há buracos.

    Vive aqui, e não na tela de Ajuda que também precisa da frase, porque a
    mensagem de erro e a resposta da Ajuda têm de dizer exatamente a mesma
    coisa. Duas cópias da mesma frase divergem no dia em que alguém corrigir
    uma delas.

    Args:
        policy: A política vigente.

    Returns:
        str: A lista de dias em linguagem corrente, sem ponto final.
    """
    from reservations.availability import DIAS_DA_SEMANA

    indices = sorted(policy.dias_abertos())
    nomes = [DIAS_DA_SEMANA[indice] for indice in indices]
    if len(nomes) == 1:
        return f"apenas {nomes[0]}"
    if indices == list(range(indices[0], indices[-1] + 1)):
        # Dias corridos — "de segunda-feira a sexta-feira" é como as pessoas
        # dizem, e é o caso comum.
        return f"de {nomes[0]} a {nomes[-1]}"
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


def _mensagem_dia_fechado(policy, date):
    """Return the closed-day message, naming the days the building does open.

    A frase diz quais dias abrem, e não só que este fecha: quem pediu domingo
    precisa saber para onde ir, e "o prédio não abre no domingo" deixa a pessoa
    adivinhando se o sábado serve.
    """
    from reservations.availability import DIAS_DA_SEMANA

    fechado = DIAS_DA_SEMANA[date.weekday()]
    lista = dias_por_extenso(policy)
    return f"{fechado.capitalize()} não é dia de funcionamento. As reservas acontecem {lista}."


def _mensagem_curta_demais(policy):
    """Return the too-short message naming the configured minimum."""
    return f"A reserva deve ter no mínimo {policy.min_duration_minutes} minutos."


def _mensagem_longa_demais(policy):
    """Return the too-long message naming the configured maximum."""
    return f"A reserva deve ter no máximo {policy.max_duration_minutes} minutos."


def _mensagem_fora_do_horizonte(policy):
    """Return the out-of-horizon message naming the configured horizon."""
    return f"Só é possível reservar com até {policy.horizon_days} dias de antecedência."


def active_reservations_overlapping(space, start_time, end_time, *, exclude_pk=None):
    """Return the reservations that still hold ``space`` during the given interval.

    Args:
        space: The Space instance to inspect.
        start_time: Start of the interval being checked.
        end_time: End of the interval being checked.
        exclude_pk: Primary key of a reservation to ignore (used when
            rescheduling, so a reservation does not conflict with itself).

    Returns:
        QuerySet: Overlapping reservations in an active status.
    """
    queryset = space.reservations.filter(
        status__in=ACTIVE_RESERVATION_STATUSES,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset


def maintenance_blocks_overlapping(space, start_time, end_time):
    """Return the maintenance blocks covering ``space`` during the given interval.

    Args:
        space: The Space instance to inspect.
        start_time: Start of the interval being checked.
        end_time: End of the interval being checked.

    Returns:
        QuerySet: Overlapping maintenance blocks.
    """
    return space.maintenance_blocks.filter(
        start_time__lt=end_time,
        end_time__gt=start_time,
    )


def validate_time_range(start_time, end_time):
    """Ensure the interval is well formed.

    Raises:
        ValidationError: If ``end_time`` is not strictly after ``start_time``.
    """
    if end_time <= start_time:
        raise ValidationError(INVALID_TIME_RANGE_MESSAGE, code=INVALID_TIME_RANGE_CODE)


def validate_no_reservation_overlap(space, start_time, end_time, *, exclude_pk=None):
    """Ensure no active reservation already holds the space in the interval.

    Raises:
        ValidationError: If an overlapping active reservation exists.
    """
    if active_reservations_overlapping(space, start_time, end_time, exclude_pk=exclude_pk).exists():
        raise ValidationError(RESERVATION_OVERLAP_MESSAGE, code=RESERVATION_OVERLAP_CODE)


def validate_booking_policy(start_time, end_time, policy=None):
    """Ensure the interval respects the configured booking policy.

    Só faz alguma coisa quando ``BookingPolicy.enforce_window`` está ligado. O
    padrão é desligado de propósito: ligar a regra numa base que já tem reservas
    fora da janela transformaria o reagendamento dessas reservas num erro, e
    essa é uma decisão do administrador, não desta camada.

    Args:
        start_time: Início desejado.
        end_time: Término desejado.
        policy: A política vigente; carregada do banco quando omitida.

    Raises:
        ValidationError: Se a reserva estiver fora do horário de funcionamento,
            fora dos limites de duração ou além do horizonte de agendamento.
    """
    # Import tardio: ``reservations.models`` importa este módulo, então importar
    # os modelos aqui no topo fecharia o ciclo.
    from reservations.models import BookingPolicy

    policy = policy or BookingPolicy.carregar()
    if not policy.enforce_window:
        return

    inicio_local = timezone.localtime(start_time)
    fim_local = timezone.localtime(end_time)

    # O dia da semana vem antes do horário porque é a recusa mais informativa:
    # dizer "fora do horário de funcionamento" para quem pediu domingo às 10h
    # faria a pessoa tentar 11h, e 12h, e continuar errando.
    if not policy.abre_em(inicio_local.date()):
        raise ValidationError(
            _mensagem_dia_fechado(policy, inicio_local.date()), code=CLOSED_DAY_CODE
        )

    if inicio_local.time() < policy.opening_time or fim_local.time() > policy.closing_time:
        raise ValidationError(_mensagem_fora_do_horario(policy), code=OUTSIDE_OPERATING_HOURS_CODE)

    duracao = (end_time - start_time).total_seconds() / 60
    if duracao < policy.min_duration_minutes:
        raise ValidationError(_mensagem_curta_demais(policy), code=DURATION_TOO_SHORT_CODE)
    if duracao > policy.max_duration_minutes:
        raise ValidationError(_mensagem_longa_demais(policy), code=DURATION_TOO_LONG_CODE)

    limite = timezone.localdate() + datetime.timedelta(days=policy.horizon_days)
    if inicio_local.date() > limite:
        raise ValidationError(_mensagem_fora_do_horizonte(policy), code=OUTSIDE_HORIZON_CODE)


def validate_reservation_slot(
    space,
    start_time,
    end_time,
    *,
    exclude_pk=None,
    require_active_space=True,
):
    """Validate every rule that must hold for a space to be reserved.

    Args:
        space: The Space being reserved.
        start_time: Desired start of the reservation.
        end_time: Desired end of the reservation.
        exclude_pk: Reservation to ignore when checking overlaps (rescheduling).
        require_active_space: Whether an inactive space should be rejected.
            Disabled when rescheduling, so an existing reservation stays
            manageable even if its space was later deactivated.

    Raises:
        ValidationError: If the space is inactive, the interval is invalid, or
            it overlaps an active reservation or a maintenance block.
    """
    if require_active_space and not space.is_active:
        raise ValidationError(SPACE_INACTIVE_MESSAGE, code=SPACE_INACTIVE_CODE)

    validate_time_range(start_time, end_time)
    validate_booking_policy(start_time, end_time)
    validate_no_reservation_overlap(space, start_time, end_time, exclude_pk=exclude_pk)

    if maintenance_blocks_overlapping(space, start_time, end_time).exists():
        raise ValidationError(MAINTENANCE_OVERLAP_MESSAGE, code=MAINTENANCE_OVERLAP_CODE)


def validate_maintenance_slot(space, start_time, end_time):
    """Validate every rule that must hold for a maintenance block to be created.

    Args:
        space: The Space being blocked.
        start_time: Desired start of the block.
        end_time: Desired end of the block.

    Raises:
        ValidationError: If the interval is invalid or it would override an
            active reservation.
    """
    validate_time_range(start_time, end_time)

    if active_reservations_overlapping(space, start_time, end_time).exists():
        raise ValidationError(
            MAINTENANCE_RESERVATION_OVERLAP_MESSAGE,
            code=MAINTENANCE_RESERVATION_OVERLAP_CODE,
        )
