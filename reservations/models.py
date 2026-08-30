"""Models for the reservations app."""

import datetime

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.fields.ranges import RangeOperators
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Func, Q

from reservations.enums import ACTIVE_RESERVATION_STATUSES, ReservationStatus
from reservations.validators import (
    validate_attendee_count,
    validate_maintenance_slot,
    validate_no_reservation_overlap,
    validate_time_range,
)

__all__ = [
    "ACTIVE_RESERVATION_STATUSES",
    "BookingPolicy",
    "MaintenanceBlock",
    "Reservation",
    "ReservationStatus",
    "TstzRange",
]


class BookingPolicy(models.Model):
    """The parameters that govern how reservations are offered.

    Antes desta tabela, "o dia tem 24 horas reserváveis" era uma consequência
    acidental de o cálculo de disponibilidade varrer da meia-noite à meia-noite
    — não uma decisão de ninguém. O resultado aparecia na tela como um único
    botão "00:00 – 00:00".

    Aqui esses parâmetros passam a ser explícitos e editáveis por um
    administrador. A política é global por enquanto; o pacote V2 prevê evoluir
    para uma política por espaço, e por isso o acesso é sempre por
    :meth:`carregar`, nunca por ``pk`` — quando existir política por espaço,
    muda a função, não os chamadores.

    Importante: esta camada decide **o que é oferecido**. O que é *aceito* na
    escrita continua em ``reservations.validators``, e só passa a considerar a
    janela quando ``enforce_window`` estiver ligado.
    """

    #: A política é única. O ``pk`` fixo torna ``carregar()`` barato e impede
    #: que uma segunda linha apareça por acidente e passe a competir com a
    #: primeira.
    PK_UNICO = 1

    opening_time = models.TimeField(
        default=datetime.time(8, 0),
        verbose_name="Abertura",
        help_text="Primeiro horário do dia em que um espaço pode ser reservado.",
    )
    closing_time = models.TimeField(
        default=datetime.time(18, 0),
        verbose_name="Fechamento",
        help_text="Horário em que o último período de reserva termina.",
    )
    slot_minutes = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Incremento",
        help_text="De quantos em quantos minutos os horários são oferecidos.",
    )
    min_duration_minutes = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Duração mínima",
        help_text="Menor reserva possível, em minutos.",
    )
    max_duration_minutes = models.PositiveSmallIntegerField(
        default=240,
        verbose_name="Duração máxima",
        help_text="Maior reserva possível, em minutos.",
    )
    horizon_days = models.PositiveSmallIntegerField(
        default=90,
        verbose_name="Horizonte",
        help_text="Com quantos dias de antecedência é possível reservar.",
    )
    few_slots_threshold = models.PositiveSmallIntegerField(
        default=3,
        verbose_name="Limiar de “poucos horários”",
        help_text="Com esta quantidade de horários livres ou menos, o espaço "
        "é sinalizado como quase cheio.",
    )
    # Os dias de funcionamento entraram como sete booleanos, e não como um
    # ``ArrayField`` de inteiros, por uma razão só: ``[0, 1, 2, 3, 4]`` exige
    # que quem lê saiba se 0 é segunda (convenção do Python) ou domingo
    # (convenção de calendário). Essa ambiguidade já me custou erros nas
    # fases anteriores. ``opens_monday`` não tem como ser lido errado.
    opens_monday = models.BooleanField(default=True, verbose_name="Segunda-feira")
    opens_tuesday = models.BooleanField(default=True, verbose_name="Terça-feira")
    opens_wednesday = models.BooleanField(default=True, verbose_name="Quarta-feira")
    opens_thursday = models.BooleanField(default=True, verbose_name="Quinta-feira")
    opens_friday = models.BooleanField(default=True, verbose_name="Sexta-feira")
    opens_saturday = models.BooleanField(default=False, verbose_name="Sábado")
    opens_sunday = models.BooleanField(default=False, verbose_name="Domingo")

    enforce_window = models.BooleanField(
        default=False,
        verbose_name="Recusar reservas fora da janela",
        help_text="Quando ligado, uma reserva fora do horário de funcionamento "
        "ou fora dos limites de duração é recusada na gravação — inclusive "
        "pela API. Deixe desligado até revisar as reservas já existentes.",
    )
    release_no_shows = models.BooleanField(
        default=False,
        verbose_name="Liberar reservas sem check-in",
        help_text="Quando ligado, uma reserva confirmada sem check-in é marcada "
        "como não comparecida depois da tolerância abaixo, e o espaço volta a "
        "ficar livre. Deixe desligado até a rotina de check-in estar no hábito "
        "de quem reserva — caso contrário, reservas legítimas serão liberadas.",
    )
    no_show_threshold_minutes = models.PositiveSmallIntegerField(
        default=15,
        verbose_name="Tolerância para o check-in",
        help_text="Quantos minutos depois do início a reserva ainda espera pelo "
        "check-in antes de ser liberada.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for BookingPolicy."""

        verbose_name = "Política de reserva"
        verbose_name_plural = "Política de reserva"

    def __str__(self):
        """Return a short description of the operating window."""
        return f"{self.opening_time:%H:%M} – {self.closing_time:%H:%M}, de {self.slot_minutes} min"

    @classmethod
    def carregar(cls):
        """Return the single policy row, creating it with the defaults if needed.

        Returns:
            BookingPolicy: A política vigente.
        """
        politica, _ = cls.objects.get_or_create(pk=cls.PK_UNICO)
        return politica

    def save(self, *args, **kwargs):
        """Force the singleton primary key before saving."""
        self.pk = self.PK_UNICO
        super().save(*args, **kwargs)

    #: Os campos de dia, na ordem de ``datetime.date.weekday()`` — segunda é 0.
    #: A lista existe para que a conversão entre "o campo" e "o número do dia"
    #: aconteça num lugar só.
    CAMPOS_DE_DIA = (
        "opens_monday",
        "opens_tuesday",
        "opens_wednesday",
        "opens_thursday",
        "opens_friday",
        "opens_saturday",
        "opens_sunday",
    )

    def dias_abertos(self):
        """Return the weekdays the building opens, as ``weekday()`` numbers.

        Returns:
            frozenset[int]: Segunda é 0, domingo é 6.
        """
        return frozenset(
            indice for indice, campo in enumerate(self.CAMPOS_DE_DIA) if getattr(self, campo)
        )

    def abre_em(self, date):
        """Return whether the building opens on a given date.

        Args:
            date: O dia.

        Returns:
            bool: ``True`` quando o prédio abre nesse dia da semana.
        """
        return getattr(self, self.CAMPOS_DE_DIA[date.weekday()])

    def clean(self):
        """Reject parameter combinations that would produce no bookable slot."""
        super().clean()
        erros = {}
        if not self.dias_abertos():
            # Sem nenhum dia aberto o sistema inteiro para: nenhuma tela ofereceria
            # horário e nenhuma reserva passaria. É configuração que não tem como
            # ser o que a pessoa quis dizer.
            erros["opens_monday"] = (
                "Escolha pelo menos um dia da semana; sem nenhum, nada pode ser reservado."
            )
        if self.closing_time <= self.opening_time:
            erros["closing_time"] = "O fechamento deve ser depois da abertura."
        if not self.slot_minutes:
            erros["slot_minutes"] = "O incremento deve ser de pelo menos 1 minuto."
        if self.min_duration_minutes and self.max_duration_minutes:
            if self.min_duration_minutes > self.max_duration_minutes:
                erros["max_duration_minutes"] = "A duração máxima não pode ser menor que a mínima."
        if self.slot_minutes and self.min_duration_minutes % self.slot_minutes:
            erros["min_duration_minutes"] = (
                "A duração mínima precisa ser um múltiplo do incremento, "
                "senão nenhum horário oferecido servirá."
            )
        if not self.horizon_days:
            erros["horizon_days"] = "O horizonte deve ser de pelo menos 1 dia."
        if erros:
            raise ValidationError(erros)


class TstzRange(Func):
    """PostgreSQL tstzrange function for exclusion constraints."""

    function = "tstzrange"
    output_field = DateTimeRangeField()


class ReservationQuerySet(models.QuerySet):
    """Queries about reservations that more than one caller needs to agree on."""

    def canceladas_entre(self, inicio, fim):
        """Return the cancellations that fall in a window, by the best date available.

        Há duas leituras possíveis de "cancelamentos no período", e desde que
        ``cancelled_at`` existe o sistema tem as duas ao mesmo tempo:

        * as canceladas **depois** desta coluna existir têm a data do
          cancelamento, e entram no período em que o cancelamento aconteceu;
        * as canceladas **antes** têm ``cancelled_at`` nulo — e vão continuar
          tendo, porque não há de onde tirar a data sem inventá-la. Para essas,
          a única âncora verdadeira é o horário da reserva, e a pergunta que a
          contagem responde vira "quanta sala foi liberada neste período".

        As duas leituras convivem no mesmo número, e é por isso que
        :meth:`resumo_de_cancelamentos` devolve as parcelas separadas: somá-las
        sem dizer que são coisas diferentes seria esconder a diferença.

        Args:
            inicio: Início da janela, ciente do fuso.
            fim: Fim da janela, ciente do fuso.

        Returns:
            QuerySet: As reservas canceladas que caem na janela.
        """
        return self.filter(status=ReservationStatus.CANCELLED).filter(
            Q(cancelled_at__gte=inicio, cancelled_at__lt=fim)
            | Q(cancelled_at__isnull=True, start_time__gte=inicio, start_time__lt=fim)
        )

    def resumo_de_cancelamentos(self, inicio, fim):
        """Return the cancellation counts in a window, split by which date was used.

        Args:
            inicio: Início da janela, ciente do fuso.
            fim: Fim da janela, ciente do fuso.

        Returns:
            dict: ``total``, ``por_ocorrencia`` (com data de cancelamento) e
            ``sem_data`` (contadas pelo horário da reserva).
        """
        canceladas = self.canceladas_entre(inicio, fim)
        sem_data = canceladas.filter(cancelled_at__isnull=True).count()
        com_data = canceladas.filter(cancelled_at__isnull=False).count()
        return {
            "total": com_data + sem_data,
            "por_ocorrencia": com_data,
            "sem_data": sem_data,
        }


class Reservation(models.Model):
    """A reservation of a space by a user for a specific time slot."""

    space = models.ForeignKey(
        "spaces.Space",
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    # Os três campos abaixo entraram na Fase 10 e são opcionais no banco de
    # propósito: as reservas que já existem não têm assunto nem número de
    # participantes, e inventar um valor para elas seria criar dado falso. O
    # formulário da web exige assunto e participantes para as novas; a API
    # mantém o contrato antigo, em que eram desnecessários.
    title = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Assunto",
        help_text="Como esta reserva aparece para você e para a administração.",
    )
    attendee_count = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name="Participantes",
        help_text="Quantas pessoas devem comparecer.",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Observações",
        help_text="Qualquer coisa que a administração precise saber. Opcional.",
    )
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus,
        default=ReservationStatus.CONFIRMED,
    )
    checked_in_at = models.DateTimeField(blank=True, null=True)
    # Quando o cancelamento aconteceu — não confundir com o horário da reserva
    # cancelada. Fica nulo nas reservas canceladas antes desta coluna existir, e
    # continua nulo: ``updated_at`` é ``auto_now`` e se move a cada gravação, de
    # modo que usá-lo para preencher o histórico inventaria datas com cara de
    # verdadeiras. Quem lê o campo precisa tratar o nulo — ver
    # ``Reservation.objects.canceladas_entre``.
    cancelled_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Cancelada em",
        help_text="Quando o cancelamento foi registrado.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReservationQuerySet.as_manager()

    class Meta:
        """Meta options for Reservation."""

        ordering = ["-start_time"]
        constraints = [
            ExclusionConstraint(
                name="exclude_overlapping_reservations",
                expressions=[
                    (F("space"), RangeOperators.EQUAL),
                    (TstzRange(F("start_time"), F("end_time")), RangeOperators.OVERLAPS),
                ],
                condition=Q(
                    status__in=[
                        ReservationStatus.CONFIRMED,
                        ReservationStatus.CHECKED_IN,
                    ],
                ),
            ),
        ]

    def __str__(self):
        """Return a human-readable description of the reservation."""
        return f"{self.space.name} — {self.start_time} to {self.end_time}"

    def clean(self):
        """Validate the reservation data.

        Delegates to :mod:`reservations.validators` so the rules stay identical
        to the ones applied by the service layer and by the API serializers.
        """
        super().clean()
        validate_time_range(self.start_time, self.end_time)
        validate_attendee_count(self.space, self.attendee_count)

        if self.status in ACTIVE_RESERVATION_STATUSES:
            validate_no_reservation_overlap(
                self.space,
                self.start_time,
                self.end_time,
                exclude_pk=self.pk,
            )


class MaintenanceBlock(models.Model):
    """A maintenance block that prevents reservations for a space."""

    space = models.ForeignKey(
        "spaces.Space",
        on_delete=models.CASCADE,
        related_name="maintenance_blocks",
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    reason = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="maintenance_blocks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for MaintenanceBlock."""

        ordering = ["-start_time"]

    def __str__(self):
        """Return a human-readable description of the block."""
        return f"{self.space.name} — {self.reason} ({self.start_time} to {self.end_time})"

    def clean(self):
        """Validate the maintenance block data."""
        super().clean()
        validate_maintenance_slot(self.space, self.start_time, self.end_time)
