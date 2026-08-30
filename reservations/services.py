"""Services for the reservations app."""

import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from reservations.models import (
    ACTIVE_RESERVATION_STATUSES,
    BookingPolicy,
    MaintenanceBlock,
    Reservation,
    ReservationStatus,
)
from reservations.validators import (
    RESERVATION_OVERLAP_CODE,
    RESERVATION_OVERLAP_MESSAGE,
    validate_attendee_count,
    validate_reservation_slot,
)

CHECK_IN_WINDOW_MINUTES = 15
#: Tolerância usada quando não há política carregável. A configurável mora em
#: ``BookingPolicy.no_show_threshold_minutes``; esta é só o ponto de partida
#: da migração e o valor padrão do comando de linha.
DEFAULT_NO_SHOW_THRESHOLD_MINUTES = 15


class OwnershipError(Exception):
    """Raised when a user tries to modify a reservation they do not own."""

    pass


def get_availability_for_date(space, date):
    """Return occupied and free time slots for a space on a given date.

    O dia é delimitado no **fuso local** (``settings.TIME_ZONE``), não em UTC:
    uma reserva das 22h em Goiás pertence ao dia em que o usuário a marcou, e não
    ao dia seguinte em UTC. Os instantes devolvidos continuam em UTC com sufixo
    ``Z``, que é o contrato público da API.

    Args:
        space: A Space instance.
        date: A date object representing the day to check.

    Returns:
        dict: {
            "date": str(date),
            "occupied": [
                {"start": ISO8601, "end": ISO8601, "type": "reservation" | "maintenance"}
            ],
            "free": [
                {"start": ISO8601, "end": ISO8601}
            ],
        }
    """
    date_start = _local_day_start(date)
    date_end = _local_day_start(date + datetime.timedelta(days=1))

    reservations = Reservation.objects.filter(
        space=space,
        status__in=ACTIVE_RESERVATION_STATUSES,
        start_time__lt=date_end,
        end_time__gt=date_start,
    )

    maintenance_blocks = MaintenanceBlock.objects.filter(
        space=space,
        start_time__lt=date_end,
        end_time__gt=date_start,
    )

    occupied_intervals = []

    for reservation in reservations:
        occupied_start = max(reservation.start_time, date_start)
        occupied_end = min(reservation.end_time, date_end)
        occupied_intervals.append((occupied_start, occupied_end, "reservation"))

    for block in maintenance_blocks:
        block_start = max(block.start_time, date_start)
        block_end = min(block.end_time, date_end)
        occupied_intervals.append((block_start, block_end, "maintenance"))

    occupied_intervals.sort(key=lambda interval: interval[0])

    merged = []
    for start, end, typ in occupied_intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (
                merged[-1][0],
                max(merged[-1][1], end),
                merged[-1][2],
            )
        else:
            merged.append((start, end, typ))

    occupied = []
    for start, end, typ in merged:
        occupied.append(
            {
                "start": _isoformat(start),
                "end": _isoformat(end),
                "type": typ,
            }
        )

    free = []
    current = date_start

    for start, end, _typ in merged:
        if start > current:
            free.append(
                {
                    "start": _isoformat(current),
                    "end": _isoformat(start),
                }
            )
        current = max(current, end)

    if current < date_end:
        free.append(
            {
                "start": _isoformat(current),
                "end": _isoformat(date_end),
            }
        )

    return {
        "date": str(date),
        "occupied": occupied,
        "free": free,
    }


def cancel_reservation(reservation, user):
    """Cancel a reservation if the user is the owner and status allows it.

    Args:
        reservation: The Reservation instance to cancel.
        user: The user requesting the cancellation.

    Raises:
        ValidationError: If the user is not the owner or the reservation
            cannot be cancelled in its current status.
    """
    if reservation.user != user:
        raise OwnershipError("Você só pode cancelar as suas próprias reservas.")

    if reservation.status not in ACTIVE_RESERVATION_STATUSES:
        raise ValidationError(
            "Só é possível cancelar reservas confirmadas ou com check-in realizado.",
        )

    _marcar_cancelada(reservation)


def _marcar_cancelada(reservation, *, agora=None):
    """Write the cancellation, its timestamp and the service fallout.

    As duas portas de cancelamento — a do dono e a da administração — passam
    por aqui. Duplicar as três linhas foi o que fez ``cancelled_at`` nascer
    torto em tantos sistemas: uma das portas esquece de gravar a data, e o
    relatório passa a contar metade dos cancelamentos.

    Args:
        reservation: A reserva a cancelar.
        agora: O instante registrado; ``timezone.now()`` quando omitido.
    """
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = timezone.now() if agora is None else agora
    reservation.save(update_fields=["status", "cancelled_at", "updated_at"])
    _cancelar_servicos(reservation)


def _cancelar_servicos(reservation):
    """Cancel the pending service requests of a cancelled reservation.

    Import tardio: ``services`` depende de ``reservations``, e importar de volta
    no topo fecharia o ciclo. Sem esta chamada, cancelar a reserva deixaria a
    copa preparando café para uma reunião que não vai acontecer.

    Args:
        reservation: A reserva cancelada.
    """
    from services.services import cancelar_pedidos_da_reserva

    cancelar_pedidos_da_reserva(reservation)


def atualizar_detalhes(reservation, user, *, title, attendee_count, notes):
    """Change what a reservation is about, without touching when it happens.

    Assunto, participantes e observações descrevem o encontro; data, hora e
    espaço são o compromisso com a agenda. Mudar os primeiros não disputa nada
    com ninguém e por isso não passa por revalidação de conflito — mudar os
    segundos é o que ``reschedule_reservation`` faz, com toda a validação.

    A capacidade continua sendo verificada: subir de 4 para 40 participantes
    numa sala de 8 é um erro do mesmo tipo que criar a reserva assim.

    Args:
        reservation: A reserva a alterar.
        user: Quem está pedindo a alteração.
        title: O novo assunto.
        attendee_count: O novo número de participantes, ou ``None``.
        notes: As novas observações.

    Returns:
        Reservation: A reserva atualizada.

    Raises:
        OwnershipError: Se quem pede não é o dono.
        ValidationError: Se a reserva já está encerrada ou o número não cabe.
    """
    if reservation.user != user:
        raise OwnershipError("Você só pode editar as suas próprias reservas.")

    if reservation.status not in ACTIVE_RESERVATION_STATUSES:
        raise ValidationError(
            "Só é possível editar reservas confirmadas ou com check-in realizado.",
        )

    # A capacidade é do espaço atual, e não do que ele era: se a sala foi
    # reconfigurada para menos lugares, o número precisa caber no que existe
    # hoje.
    validate_attendee_count(reservation.space, attendee_count)

    reservation.title = title
    reservation.attendee_count = attendee_count
    reservation.notes = notes
    reservation.save(update_fields=["title", "attendee_count", "notes", "updated_at"])
    return reservation


def reschedule_reservation(reservation, user, start_time, end_time):
    """Reschedule a reservation to a new time slot.

    Args:
        reservation: The Reservation instance to reschedule.
        user: The user requesting the reschedule.
        start_time: The new reservation start time.
        end_time: The new reservation end time.

    Returns:
        Reservation: The updated reservation.

    Raises:
        ValidationError: If the user is not the owner, times are invalid,
            or there is an overlap with existing reservations or maintenance blocks.
    """
    if reservation.user != user:
        raise OwnershipError("Você só pode reagendar as suas próprias reservas.")

    # An existing reservation stays manageable even if its space was later
    # deactivated, so the active-space rule does not apply here.
    validate_reservation_slot(
        reservation.space,
        start_time,
        end_time,
        exclude_pk=reservation.pk,
        require_active_space=False,
    )

    reservation.start_time = start_time
    reservation.end_time = end_time
    reservation.status = ReservationStatus.CONFIRMED
    reservation.save(update_fields=["start_time", "end_time", "status", "updated_at"])
    return reservation


def pode_fazer_check_in(reservation, agora=None):
    """Return whether a reservation is inside its check-in window right now.

    A regra é a mesma que ``check_in_reservation`` aplica na hora de gravar.
    Existe aqui em separado porque a interface precisa saber, *antes* de
    oferecer o botão, se ele vai funcionar — e porque essa pergunta é feita em
    mais de uma tela. Duas cópias da mesma condição divergiriam.

    Args:
        reservation: A reserva.
        agora: O instante considerado; ``timezone.now()`` quando omitido.

    Returns:
        bool: ``True`` se o check-in seria aceito agora.
    """
    if reservation.status != ReservationStatus.CONFIRMED:
        return False
    agora = timezone.now() if agora is None else agora
    inicio_da_janela = reservation.start_time - datetime.timedelta(minutes=CHECK_IN_WINDOW_MINUTES)
    return inicio_da_janela <= agora <= reservation.end_time


def check_in_reservation(reservation, user):
    """Check in to a reservation.

    Args:
        reservation: The Reservation instance to check in to.
        user: The user requesting the check-in.

    Returns:
        Reservation: The updated reservation.

    Raises:
        OwnershipError: If the user is not the reservation owner.
        ValidationError: If the reservation is not confirmed or the current
            time is outside the valid check-in window.
    """
    if reservation.user != user:
        raise OwnershipError("Você só pode fazer check-in nas suas próprias reservas.")

    if reservation.status != ReservationStatus.CONFIRMED:
        raise ValidationError("Só é possível fazer check-in em reservas confirmadas.")

    now = timezone.now()
    check_in_start = reservation.start_time - datetime.timedelta(
        minutes=CHECK_IN_WINDOW_MINUTES,
    )
    if not (check_in_start <= now <= reservation.end_time):
        raise ValidationError(
            "O check-in fica disponível de 15 minutos antes do início até o horário de término.",
        )

    reservation.status = ReservationStatus.CHECKED_IN
    reservation.checked_in_at = now
    reservation.save(update_fields=["status", "checked_in_at", "updated_at"])
    return reservation


def create_reservation(
    user, space, start_time, end_time, *, title="", attendee_count=None, notes=""
):
    """Create a new reservation with conflict validation.

    Args:
        user: The user making the reservation.
        space: The space to reserve.
        start_time: The reservation start time.
        end_time: The reservation end time.
        title: O assunto da reserva. Opcional aqui: o formulário da web o exige,
            mas o contrato da API é anterior a este campo.
        attendee_count: Quantas pessoas devem comparecer, quando informado.
        notes: Observações para a administração.

    Returns:
        Reservation: The created reservation.

    Raises:
        ValidationError: If the space is inactive, times are invalid,
            the attendee count does not fit the space, or there is an overlap
            with existing reservations or maintenance blocks.
    """
    validate_reservation_slot(space, start_time, end_time)
    validate_attendee_count(space, attendee_count)

    try:
        with transaction.atomic():
            return Reservation.objects.create(
                space=space,
                user=user,
                start_time=start_time,
                end_time=end_time,
                title=title,
                attendee_count=attendee_count,
                notes=notes,
                status=ReservationStatus.CONFIRMED,
            )
    except IntegrityError as exc:
        # Last line of defence: the database exclusion constraint wins any race
        # that slipped past the checks above.
        #
        # O ``code`` vai junto porque este erro é indistinguível, para quem
        # chama, do sobreposição detectada na validação — e a interface decide
        # o que revelar olhando o código, não a mensagem.
        raise ValidationError(RESERVATION_OVERLAP_MESSAGE, code=RESERVATION_OVERLAP_CODE) from exc


def admin_cancel_reservation(reservation):
    """Cancel any reservation regardless of owner (admin only).

    Args:
        reservation: The Reservation instance to cancel.

    Raises:
        ValidationError: If the reservation cannot be cancelled in its
            current status.
    """
    if reservation.status not in ACTIVE_RESERVATION_STATUSES:
        raise ValidationError(
            "Só é possível cancelar reservas confirmadas ou com check-in realizado.",
        )

    _marcar_cancelada(reservation)


def auto_release_no_shows(threshold_minutes=None, *, agora=None, respeitar_politica=True):
    """Mark confirmed reservations as no-show once the tolerance has passed.

    Libera o espaço de quem reservou e não apareceu. É a única rotina do sistema
    que muda o estado de uma reserva sem ninguém pedir, e por isso vem
    **desligada**: ``BookingPolicy.release_no_shows`` precisa ser ligado por um
    administrador. Enquanto não for, a função não faz nada e devolve zero.

    A razão de vir desligada é a mesma de ``enforce_window``: numa casa onde o
    check-in ainda não é hábito, ligar isto cancelaria reservas legítimas de
    gente que estava na sala.

    Args:
        threshold_minutes: A tolerância, em minutos. Quando omitida, vem da
            política — que é onde o administrador a configura.
        agora: O instante considerado; ``timezone.now()`` quando omitido.
        respeitar_politica: Só ``False`` em uso administrativo explícito, quando
            alguém roda a liberação à mão sabendo que a regra está desligada.

    Returns:
        int: Quantas reservas foram marcadas como não comparecidas.
    """
    policy = BookingPolicy.carregar()
    if respeitar_politica and not policy.release_no_shows:
        return 0

    if threshold_minutes is None:
        threshold_minutes = policy.no_show_threshold_minutes

    agora = timezone.now() if agora is None else agora
    cutoff = agora - datetime.timedelta(minutes=threshold_minutes)

    overdue = Reservation.objects.filter(
        status=ReservationStatus.CONFIRMED,
        start_time__lt=cutoff,
    )

    released_count = 0
    for reservation in overdue:
        reservation.status = ReservationStatus.NO_SHOW
        reservation.save(update_fields=["status", "updated_at"])
        released_count += 1

    return released_count


def _local_day_start(date):
    """Return the aware datetime for midnight of ``date`` in the local timezone.

    Usar o fuso local (e não UTC) é o que faz o "dia" da disponibilidade
    corresponder ao dia que o usuário enxerga no calendário.
    """
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time.min))


def _isoformat(dt):
    """Return ISO 8601 string in UTC with a ``Z`` suffix.

    A conversão explícita para UTC mantém o contrato da API estável mesmo quando
    o datetime de origem está no fuso local.
    """
    return dt.astimezone(datetime.UTC).isoformat().replace("+00:00", "Z")
