"""Views for the reservations app."""

import datetime

import django_filters
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views import View
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import nome_de_exibicao
from reservations import calendario
from reservations.models import (
    ACTIVE_RESERVATION_STATUSES,
    BookingPolicy,
    MaintenanceBlock,
    Reservation,
    ReservationStatus,
)
from reservations.serializers import MaintenanceBlockSerializer, ReservationSerializer
from reservations.services import (
    OwnershipError,
    atualizar_detalhes,
    cancel_reservation,
    check_in_reservation,
    create_reservation,
    pode_fazer_check_in,
    reschedule_reservation,
)
from reservations.steps import FLUXO_V2, contexto_do_stepper
from reservations.validators import (
    ATTENDEE_COUNT_INVALID_MESSAGE,
    CODIGOS_DE_HORARIO,
    validate_attendee_count,
    validate_reservation_slot,
)
from services.enums import STATUS_PENDENTES, ServiceRequestStatus
from services.services import (
    ServiceNotesRequiredError,
    montar_pedidos,
    servicos_do_espaco,
    sincronizar_servicos,
    solicitar_servicos,
)
from spaces.models import Space


class RescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling a reservation."""

    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    class Meta:
        """Meta options for RescheduleSerializer."""

        fields = ["start_time", "end_time"]


class ReservationFilterSet(django_filters.FilterSet):
    """Filter set for user reservations."""

    start_time__gte = django_filters.DateTimeFilter(field_name="start_time", lookup_expr="gte")
    start_time__lte = django_filters.DateTimeFilter(field_name="start_time", lookup_expr="lte")

    class Meta:
        """Meta options for ReservationFilterSet."""

        model = Reservation
        fields = ["status", "space"]


class MaintenanceBlockViewSet(viewsets.ModelViewSet):
    """ViewSet for creating, listing and deleting maintenance blocks (admin only)."""

    queryset = MaintenanceBlock.objects.all()
    serializer_class = MaintenanceBlockSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        """Automatically set created_by from the request user."""
        serializer.save(created_by=self.request.user)


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for listing and creating reservations."""

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = ReservationFilterSet

    def get_queryset(self):
        """Users see only their own reservations, ordered by start_time descending."""
        return Reservation.objects.filter(user=self.request.user).order_by("-start_time")

    def perform_create(self, serializer):
        """Automatically set user and confirmed status on creation."""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["patch"])
    def cancel(self, request, pk=None):
        """Cancel a reservation."""
        reservation = get_object_or_404(Reservation, pk=pk)
        try:
            cancel_reservation(reservation, request.user)
        except OwnershipError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(reservation)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        """Check in to a reservation."""
        reservation = get_object_or_404(Reservation, pk=pk)
        try:
            check_in_reservation(reservation, request.user)
        except OwnershipError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        response_serializer = self.get_serializer(reservation)
        return Response(response_serializer.data)

    @action(detail=True, methods=["patch"])
    def reschedule(self, request, pk=None):
        """Reschedule a reservation to a new time slot."""
        reservation = get_object_or_404(Reservation, pk=pk)
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reschedule_reservation(
                reservation,
                request.user,
                serializer.validated_data["start_time"],
                serializer.validated_data["end_time"],
            )
        except OwnershipError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        response_serializer = self.get_serializer(reservation)
        return Response(response_serializer.data)


class OccupancyView(APIView):
    """Admin-only view for occupancy overview of all spaces on a given date."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        """Return all spaces with their reservations and maintenance blocks for a date.

        Query Parameters:
            date: Date in YYYY-MM-DD format (required)

        Returns:
            Response with list of spaces including reservations and maintenance blocks.
        """
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Date parameter is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        date_start = timezone.make_aware(datetime.datetime.combine(date, datetime.time.min))
        date_end = timezone.make_aware(
            datetime.datetime.combine(date + datetime.timedelta(days=1), datetime.time.min)
        )

        spaces = Space.objects.all().order_by("name")
        occupancy_data = []

        for space in spaces:
            reservations = Reservation.objects.filter(
                space=space,
                start_time__lt=date_end,
                end_time__gt=date_start,
            ).select_related("user")

            reservation_list = [
                {
                    "id": r.id,
                    "user": r.user.username,
                    "start_time": r.start_time.isoformat().replace("+00:00", "Z"),
                    "end_time": r.end_time.isoformat().replace("+00:00", "Z"),
                    "status": r.status,
                }
                for r in reservations
            ]

            maintenance_blocks = MaintenanceBlock.objects.filter(
                space=space,
                start_time__lt=date_end,
                end_time__gt=date_start,
            )

            block_list = [
                {
                    "id": b.id,
                    "start_time": b.start_time.isoformat().replace("+00:00", "Z"),
                    "end_time": b.end_time.isoformat().replace("+00:00", "Z"),
                    "reason": b.reason,
                }
                for b in maintenance_blocks
            ]

            occupancy_data.append(
                {
                    "id": space.id,
                    "name": space.name,
                    "capacity": space.capacity,
                    "location": space.location,
                    "is_active": space.is_active,
                    "reservations": reservation_list,
                    "maintenance_blocks": block_list,
                }
            )

        return Response(
            {
                "date": date_str,
                "spaces": occupancy_data,
            }
        )


class ReservationListView(LoginRequiredMixin, View):
    """List view for the authenticated user's reservations."""

    template_name = "reservations/reservation_list.html"

    def get(self, request):
        """Render the user's reservations with tab filtering."""
        reservations = Reservation.objects.filter(user=request.user).order_by("-start_time")

        now = timezone.now()

        # Calculate counts for tabs
        active_count = reservations.filter(
            status__in=[ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN],
            end_time__gte=now,
        ).count()

        past_count = reservations.filter(
            models.Q(end_time__lt=now)
            | models.Q(status__in=[ReservationStatus.COMPLETED, ReservationStatus.NO_SHOW]),
        ).count()

        cancelled_count = reservations.filter(
            status=ReservationStatus.CANCELLED,
        ).count()

        # Determine active tab
        active_tab = request.GET.get("tab", "active")
        if active_tab not in ["active", "past", "cancelled"]:
            active_tab = "active"

        # Filter reservations based on tab
        if active_tab == "active":
            filtered_reservations = reservations.filter(
                status__in=[ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN],
                end_time__gte=now,
            )
        elif active_tab == "past":
            filtered_reservations = reservations.filter(
                models.Q(end_time__lt=now)
                | models.Q(
                    status__in=[ReservationStatus.COMPLETED, ReservationStatus.NO_SHOW],
                ),
            )
        else:  # cancelled
            filtered_reservations = reservations.filter(
                status=ReservationStatus.CANCELLED,
            )

        return render(
            request,
            self.template_name,
            {
                "reservations": reservations,
                "filtered_reservations": filtered_reservations,
                "active_tab": active_tab,
                "active_count": active_count,
                "past_count": past_count,
                "cancelled_count": cancelled_count,
            },
        )


class CalendarView(LoginRequiredMixin, View):
    """The user's calendar, in month, week or day.

    Todo o estado da tela — qual visão, qual dia, se a ocupação geral está
    ligada — vive na querystring. Não há JavaScript de calendário aqui: cada
    seta e cada aba é um link, o que faz a tela funcionar no teclado, no leitor
    de tela e no botão "voltar" do navegador sem nenhum código para isso.
    """

    template_name = "reservations/calendar.html"

    def get(self, request):
        """Render the calendar for the requested view and date."""
        vista = calendario.normalizar_vista(request.GET.get("vista"))
        dia = calendario.data_pedida(request.GET.get("data"))
        incluir_ocupacao = request.GET.get("ocupacao") == "1"

        contexto = calendario.montar_calendario(
            request.user,
            vista,
            dia,
            incluir_ocupacao=incluir_ocupacao,
        )
        contexto["url_sem_ocupacao"] = self._url(vista, dia, False)
        contexto["url_com_ocupacao"] = self._url(vista, dia, True)
        contexto["url_anterior"] = self._url(vista, contexto["anterior"], incluir_ocupacao)
        contexto["url_proximo"] = self._url(vista, contexto["proximo"], incluir_ocupacao)
        contexto["url_hoje"] = self._url(vista, contexto["hoje"], incluir_ocupacao)
        for aba in contexto["vistas"]:
            aba["url"] = self._url(aba["chave"], dia, incluir_ocupacao)
        for celula in contexto["celulas"]:
            celula["url_do_dia"] = self._url(
                calendario.VISTA_DIA, celula["data"], incluir_ocupacao
            )
        return render(request, self.template_name, contexto)

    @staticmethod
    def _url(vista, dia, incluir_ocupacao):
        """Return the calendar URL for a given view, date and occupancy flag."""
        parametros = {"vista": vista, "data": dia.isoformat()}
        if incluir_ocupacao:
            parametros["ocupacao"] = "1"
        return f"{reverse('calendar')}?{urlencode(parametros)}"


class ReservationDetailView(LoginRequiredMixin, View):
    """Detail view for a single reservation."""

    template_name = "reservations/reservation_detail.html"

    def get(self, request, pk):
        """Render the reservation detail page with action buttons context."""
        reservation = get_object_or_404(
            # O prefetch é do tipo de serviço, e não só dos pedidos: o template
            # imprime o nome de cada um, e sem isto seria uma consulta por linha.
            Reservation.objects.prefetch_related("service_requests__service_type"),
            pk=pk,
            user=request.user,
        )

        now = timezone.now()

        # Determine which actions are available
        can_cancel = reservation.status in {
            ReservationStatus.CONFIRMED,
            ReservationStatus.CHECKED_IN,
        }

        # A janela de check-in é decidida em reservations.services, junto da regra
        # que a grava — a tela não reimplementa a condição.
        can_check_in = pode_fazer_check_in(reservation, now)

        can_reschedule = reservation.status in {
            ReservationStatus.CONFIRMED,
            ReservationStatus.CHECKED_IN,
        }

        # Editar detalhes tem a mesma condição de reagendar — a reserva precisa
        # estar viva —, mas é decisão separada porque a resposta pode divergir:
        # uma reserva em curso talvez ainda aceite mudar o assunto e já não
        # aceite mudar de horário.
        can_edit = reservation.status in ACTIVE_RESERVATION_STATUSES

        return render(
            request,
            self.template_name,
            {
                "reservation": reservation,
                # O organizador não é campo do formulário: é quem reservou. Nome
                # e lotação saem do perfil, e o perfil pode não existir ainda.
                "organizador": nome_de_exibicao(reservation.user),
                "organizador_lotacao": getattr(
                    getattr(reservation.user, "profile", None), "department", ""
                ),
                "can_cancel": can_cancel,
                "can_check_in": can_check_in,
                "can_reschedule": can_reschedule,
                "can_edit": can_edit,
                # O passo 4 termina aqui: depois de confirmar, o usuário já
                # está "vendo a reserva", e o pacote V2 pede que a mesma tela
                # ofereça o calendário. O dia é calculado no fuso local — a
                # data em UTC de uma reserva das 21h aponta para o dia errado.
                "url_calendario": CalendarView._url(
                    calendario.VISTA_DIA,
                    timezone.localtime(reservation.start_time).date(),
                    False,
                ),
            },
        )


class _ErroNoPasso3(Exception):  # noqa: N818
    """Carries the already-rendered step 3 response back up the call stack.

    Existe porque ler e validar o passo 3 é a mesma coisa para duas views — a
    da revisão e a da confirmação — e as duas precisam, no erro, devolver o
    formulário com tudo preenchido. Sem isto, a alternativa seria cada view
    repetir a mesma sequência de ``if`` e as duas cópias divergirem.

    O sufixo ``Error`` fica de fora de propósito: isto não é um erro do
    domínio, é o transporte de uma resposta HTTP já pronta.
    """

    def __init__(self, resposta):
        """Store the response the view should return.

        Args:
            resposta: A resposta HTTP já renderizada.
        """
        super().__init__("Formulário do passo 3 recusado.")
        self.resposta = resposta


class _PassoTres(LoginRequiredMixin, View):
    """Shared reading, validation and rendering of step 3.

    O formulário de detalhes é postado por duas telas: ele mesmo (indo para a
    revisão) e a revisão (voltando para correção). Quem valida é sempre este
    código.
    """

    template_name = "reservations/reservation_form.html"

    def _ler(self, request):
        """Read step 3's fields from the POST, without judging them yet.

        Args:
            request: A requisição.

        Returns:
            dict: Os campos como o usuário os enviou, ainda em texto.
        """
        marcados = request.POST.getlist("services")
        return {
            "date_str": request.POST.get("date", "").strip(),
            "start_time_str": request.POST.get("start_time", "").strip(),
            "end_time_str": request.POST.get("end_time", "").strip(),
            "title": request.POST.get("title", "").strip()[:160],
            "notes": request.POST.get("notes", "").strip(),
            "attendee_raw": request.POST.get("attendee_count", "").strip(),
            "servicos_marcados": marcados,
            "detalhamentos": {
                chave: request.POST.get(f"service_notes_{chave}", "").strip() for chave in marcados
            },
        }

    def _renderizar(
        self, request, space, campos, *, erro=None, servico_com_erro=None, erro_de_horario=False
    ):
        """Render step 3 keeping everything the user typed.

        Perder o que já foi preenchido a cada erro é o jeito mais rápido de
        fazer alguém desistir do formulário.

        Args:
            request: A requisição.
            space: O espaço escolhido.
            campos: O resultado de :meth:`_ler`.
            erro: O que deu errado, na linguagem do usuário.
            servico_com_erro: O serviço cujo campo deve receber o foco.
            erro_de_horario: Se o erro é de data/hora, para reabrir o bloco.

        Returns:
            HttpResponse: O passo 3 renderizado.
        """
        contexto = {
            "space": space,
            "error": erro,
            "prefill_date": campos["date_str"],
            "prefill_start_time": campos["start_time_str"],
            "prefill_end_time": campos["end_time_str"],
            "prefill_title": campos["title"],
            "prefill_attendee_count": campos["attendee_raw"],
            "prefill_notes": campos["notes"],
            "servicos_grupos": self._grupos_de_servicos(
                space, campos["servicos_marcados"], campos["detalhamentos"], servico_com_erro
            ),
            "resumo": self._resumo(
                space,
                campos["date_str"],
                campos["start_time_str"],
                campos["end_time_str"],
                campos["attendee_raw"],
            ),
            # Se o que voltou errado foi o horário, o bloco precisa estar
            # aberto: mandar corrigir algo que está escondido é o mesmo que não
            # dizer nada.
            "abrir_horario": not campos["start_time_str"] or erro_de_horario,
        }
        contexto.update(contexto_do_stepper(3, FLUXO_V2))
        return render(request, self.template_name, contexto)

    def _validar(self, request, space, campos):
        """Turn step 3's raw fields into domain values, or reject them.

        Args:
            request: A requisição.
            space: O espaço escolhido.
            campos: O resultado de :meth:`_ler`.

        Returns:
            dict: ``start_time``, ``end_time``, ``attendee_count`` e ``pedidos``.

        Raises:
            _ErroNoPasso3: Com o formulário já renderizado e explicado.
        """
        try:
            start_time = self._parse_datetime(campos["date_str"], campos["start_time_str"])
            end_time = self._parse_datetime(campos["date_str"], campos["end_time_str"])
        except ValueError as exc:
            raise _ErroNoPasso3(
                self._renderizar(
                    request,
                    space,
                    campos,
                    erro="Formato de data ou hora inválido.",
                    erro_de_horario=True,
                )
            ) from exc

        # Participantes é opcional: quem ainda não sabe quantas pessoas vêm não
        # deve ser impedido de reservar a sala por causa disso. Em branco vira
        # ausência — que o banco e ``validate_attendee_count`` já aceitavam
        # desde a Fase 10. Um valor *escrito e inválido*, esse continua sendo
        # erro: a pessoa quis dizer algo e disse errado.
        attendee_count = None
        if campos["attendee_raw"]:
            if not campos["attendee_raw"].isdigit():
                raise _ErroNoPasso3(
                    self._renderizar(request, space, campos, erro=ATTENDEE_COUNT_INVALID_MESSAGE)
                )
            attendee_count = int(campos["attendee_raw"])

        # Os pedidos são montados antes de qualquer escrita: se falta um
        # detalhamento obrigatório, o formulário volta sem que nada tenha sido
        # gravado. Depois da reserva criada, nenhum serviço a derruba.
        try:
            pedidos = montar_pedidos(
                space,
                [(chave, campos["detalhamentos"][chave]) for chave in campos["servicos_marcados"]],
            )
        except ServiceNotesRequiredError as exc:
            raise _ErroNoPasso3(
                self._renderizar(
                    request,
                    space,
                    campos,
                    erro=" ".join(exc.messages),
                    servico_com_erro=exc.service_type,
                )
            ) from exc

        return {
            "start_time": start_time,
            "end_time": end_time,
            "attendee_count": attendee_count,
            "pedidos": pedidos,
        }

    def _recusar_por_regra(self, request, space, campos, exc):
        """Build the step 3 response for a domain rule that said no.

        Args:
            request: A requisição.
            space: O espaço escolhido.
            campos: O resultado de :meth:`_ler`.
            exc: O ``ValidationError`` levantado pelo domínio.

        Returns:
            HttpResponse: O passo 3, com o bloco certo aberto.
        """
        return self._renderizar(
            request,
            space,
            campos,
            erro=str(exc),
            erro_de_horario=getattr(exc, "code", None) in CODIGOS_DE_HORARIO,
        )

    @staticmethod
    def _resumo(space, date_str, start_str, end_str, participantes):
        """Build the persistent summary shown beside the form.

        O pacote V2 pede um resumo presente nos quatro passos, respondendo "o
        que eu já escolhi?" sem obrigar o usuário a voltar para conferir.

        Args:
            space: O espaço escolhido, ou ``None``.
            date_str: Data no formato ``YYYY-MM-DD``, como está no campo.
            start_str: Início no formato ``HH:MM``.
            end_str: Término no formato ``HH:MM``.
            participantes: Quantidade prevista, quando conhecida.

        Returns:
            dict: ``espaco``, ``inicio``, ``fim``, ``participantes`` e
            ``url_do_horario`` — este último ``None`` quando não há espaço,
            porque o passo 2 é a tela de um espaço.
        """

        def _instante(hora):
            """Combine the form's date and time strings, tolerating blanks."""
            if not date_str or not hora:
                return None
            try:
                return datetime.datetime.strptime(f"{date_str} {hora}", "%Y-%m-%d %H:%M")
            except ValueError:
                # A data pode estar pela metade enquanto o usuário digita, e o
                # resumo não é lugar de reportar erro — o formulário reporta.
                return None

        url_do_horario = None
        if space is not None:
            url_do_horario = reverse("space_detail", args=[space.pk])
            if date_str:
                url_do_horario = f"{url_do_horario}?date={date_str}"

        return {
            "espaco": space,
            "inicio": _instante(start_str),
            "fim": _instante(end_str),
            "participantes": participantes,
            "url_do_horario": url_do_horario,
        }

    @staticmethod
    def _grupos_de_servicos(
        space, selecionados=(), detalhamentos=None, com_erro=None, travados=None
    ):
        """Return the services offered in a space, grouped for display.

        Os grupos saem na ordem em que a categoria aparece no catálogo, e não em
        ordem alfabética: quem definiu ``sort_order`` decidiu o que vem antes, e
        reordenar aqui desfaria essa decisão pelas costas.

        Args:
            space: O espaço escolhido, ou ``None``.
            selecionados: Identificadores marcados no formulário.
            detalhamentos: Detalhamentos digitados, por identificador.
            com_erro: O ``ServiceType`` cujo detalhamento faltou, se houver.
            travados: ``{pk: motivo}`` dos pedidos que a administração já
                pegou e que o usuário não pode desmarcar.

        Returns:
            list: ``[{"categoria": str, "itens": [...]}]``; vazio quando o
            espaço não oferece serviço nenhum.
        """
        if space is None:
            return []
        detalhamentos = detalhamentos or {}
        travados = travados or {}
        marcados = {str(identificador) for identificador in selecionados}
        chave_com_erro = str(com_erro.pk) if com_erro is not None else None

        grupos = {}
        for servico in servicos_do_espaco(space):
            chave = str(servico.pk)
            grupos.setdefault(servico.category, []).append(
                {
                    "servico": servico,
                    "marcado": chave in marcados,
                    "detalhamento": detalhamentos.get(chave, ""),
                    "detalhamento_obrigatorio": servico.requires_notes,
                    "com_erro": chave == chave_com_erro,
                    # Um pedido que a administração já pegou aparece marcado e
                    # sem como desmarcar, com o motivo ao lado — e não num aviso
                    # no rodapé, que a pessoa só leria depois de tentar.
                    "travado": servico.pk in travados,
                    "motivo_travado": travados.get(servico.pk, ""),
                }
            )
        return [{"categoria": categoria, "itens": itens} for categoria, itens in grupos.items()]

    @staticmethod
    def _espaco_do_post(request):
        """Return the space the form points at, or ``None`` when it points at none."""
        space_id = request.POST.get("space")
        if not space_id:
            return None
        return get_object_or_404(Space, pk=space_id, is_active=True)

    @staticmethod
    def _parse_datetime(date_str: str, time_str: str) -> datetime.datetime:
        """Combine date and time strings into a timezone-aware datetime in the local zone."""
        if not date_str or not time_str:
            raise ValueError("Missing date or time")
        naive = datetime.datetime.strptime(
            f"{date_str} {time_str}",
            "%Y-%m-%d %H:%M",
        )
        # O usuário digita no fuso local; make_aware traduz para o instante correto.
        return timezone.make_aware(naive)


class ReservationCreateView(_PassoTres):
    """Step 3 of the flow, and the final write that confirms a reservation."""

    def get(self, request):
        """Render the reservation creation form.

        Pre-fills space and start time from query parameters if provided.
        """
        space_id = request.GET.get("space")
        space = get_object_or_404(Space, pk=space_id, is_active=True) if space_id else None

        start_iso = request.GET.get("start", "")
        end_iso = request.GET.get("end", "")
        prefill_date = ""
        prefill_start_time = ""
        prefill_end_time = ""

        if start_iso:
            try:
                # O instante pode chegar em UTC (contrato da API) ou já com o
                # deslocamento local (links da tela de disponibilidade); o
                # formulário fala no fuso do usuário, então converte antes.
                dt = timezone.localtime(
                    datetime.datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                )
                prefill_date = dt.strftime("%Y-%m-%d")
                prefill_start_time = dt.strftime("%H:%M")
                prefill_end_time = self._fim_sugerido(dt, end_iso).strftime("%H:%M")
            except ValueError:
                pass

        participantes = self._pessoas_do_passo_1(request, space)
        context = {
            "space": space,
            "prefill_date": prefill_date,
            "prefill_start_time": prefill_start_time,
            "prefill_end_time": prefill_end_time,
            "prefill_title": "",
            # O passo 1 já perguntou "Quantas pessoas?"; perguntar de novo seria
            # fazer a pessoa repetir o que acabou de dizer.
            "prefill_attendee_count": participantes,
            "prefill_notes": "",
            "servicos_grupos": self._grupos_de_servicos(space),
            "resumo": self._resumo(
                space, prefill_date, prefill_start_time, prefill_end_time, participantes
            ),
            # Quem chegou do passo 2 já decidiu o horário: reabrir o bloco seria
            # pedir para confirmar o que acabou de escolher. Quem chegou sem
            # horário precisa vê-lo aberto, senão a tela não tem saída.
            "abrir_horario": not prefill_start_time,
        }
        context.update(contexto_do_stepper(3, FLUXO_V2))
        return render(request, self.template_name, context)

    @staticmethod
    def _pessoas_do_passo_1(request, space):
        """Return the attendee count carried over from step 1, when usable.

        Args:
            request: A requisição.
            space: O espaço escolhido, se houver.

        Returns:
            int | str: O número aproveitável, ou string vazia.
        """
        bruto = request.GET.get("people", "").strip()
        if not bruto.isdigit():
            return ""
        pessoas = int(bruto)
        if pessoas < 1:
            return ""
        if space and pessoas > space.capacity:
            # Veio de uma busca mais ampla do que este espaço comporta; deixar o
            # campo em branco é melhor do que preenchê-lo com um valor que o
            # próprio formulário vai recusar.
            return ""
        return pessoas

    @staticmethod
    def _fim_sugerido(inicio_local, end_iso):
        """Return the end time to pre-fill the form with.

        Usa o término informado no link quando ele existe; caso contrário, a
        duração mínima da política. Antes desta fase o valor era uma hora fixa
        escrita no código, que não correspondia a nenhuma regra configurada.

        Args:
            inicio_local: O início já convertido para o fuso do usuário.
            end_iso: O término informado na querystring, se houver.

        Returns:
            datetime: O término sugerido, no fuso do usuário.
        """
        if end_iso:
            try:
                return timezone.localtime(
                    datetime.datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                )
            except ValueError:
                pass
        politica = BookingPolicy.carregar()
        return inicio_local + datetime.timedelta(minutes=politica.min_duration_minutes)

    def post(self, request):
        """Confirm the reservation — the final write of the flow.

        Revalida tudo antes de gravar. O passo 4 já mostrou uma revisão, mas
        entre olhar e confirmar cabe uma reserva concorrente: o pacote V2 é
        explícito em exigir revalidação na confirmação, e a
        ``ExclusionConstraint`` do banco é a última linha se até isso empatar.

        No erro devolve o passo 3, e não o passo 4: um conflito ou uma
        capacidade estourada se resolve editando, e mostrar de novo a tela de
        revisão deixaria o usuário sem onde mexer. Nada do que foi preenchido
        se perde.
        """
        space = self._espaco_do_post(request)
        if space is None:
            messages.error(request, "Selecione um espaço antes de reservar.")
            return redirect("space_list")

        campos = self._ler(request)
        try:
            dados = self._validar(request, space, campos)
        except _ErroNoPasso3 as recusa:
            return recusa.resposta

        try:
            reservation = create_reservation(
                request.user,
                space,
                dados["start_time"],
                dados["end_time"],
                title=campos["title"],
                attendee_count=dados["attendee_count"],
                notes=campos["notes"],
            )
        except ValidationError as exc:
            return self._recusar_por_regra(request, space, campos, exc)

        _criados, recusados = solicitar_servicos(reservation, dados["pedidos"])
        messages.success(request, "Reserva criada com sucesso!")
        for _service_type, motivo in recusados:
            # A reserva vale; o serviço é que não coube. Dizer isso em voz alta
            # é a alternativa a deixar o usuário descobrir na hora do evento.
            messages.warning(request, motivo)
        return redirect("reservation_detail", pk=reservation.pk)


class ReservationReviewView(_PassoTres):
    """Step 4 — review and confirm.

    Uma tela de confiança, não outro formulário: o pacote V2 pede que ela
    mostre o que vai acontecer, com um ``Alterar`` por bloco, e nada mais.

    Só existe como ``POST``. Uma revisão não tem URL própria para abrir de
    novo, porque não há nada gravado para reabrir — o estado inteiro vive no
    formulário, e é por isso que ``Alterar`` volta ao passo 3 por ``formaction``
    e não por link: um ``<a>`` perderia o que a pessoa acabou de escrever.
    """

    template_name_review = "reservations/reservation_review.html"

    def post(self, request):
        """Validate step 3 and show the review, or send the form back explained."""
        space = self._espaco_do_post(request)
        if space is None:
            messages.error(request, "Selecione um espaço antes de reservar.")
            return redirect("space_list")

        campos = self._ler(request)
        try:
            dados = self._validar(request, space, campos)
        except _ErroNoPasso3 as recusa:
            return recusa.resposta

        # A revisão nunca mostra uma reserva impossível. Se o horário já não
        # serve, a pessoa volta a editar agora — e não depois de confirmar.
        try:
            validate_reservation_slot(space, dados["start_time"], dados["end_time"])
            validate_attendee_count(space, dados["attendee_count"])
        except ValidationError as exc:
            return self._recusar_por_regra(request, space, campos, exc)

        contexto = {
            "space": space,
            "campos": campos,
            # O organizador não é campo do formulário: é quem está logado.
            "organizador": nome_de_exibicao(request.user),
            # O resumo aqui serve só para imprimir data e horário já
            # convertidos; a revisão não usa o painel lateral dos passos
            # anteriores, porque a página inteira já é o resumo.
            "resumo": self._resumo(
                space,
                campos["date_str"],
                campos["start_time_str"],
                campos["end_time_str"],
                campos["attendee_raw"],
            ),
            "servicos_pedidos": self._servicos_pedidos(dados["pedidos"]),
            "url_dos_espacos": self._url_dos_espacos(campos),
        }
        contexto.update(contexto_do_stepper(4, FLUXO_V2))
        return render(request, self.template_name_review, contexto)

    @staticmethod
    def _servicos_pedidos(pedidos):
        """Pair each requested service with what the user wrote about it.

        Args:
            pedidos: Pares ``(ServiceType, detalhamento)``.

        Returns:
            list: ``[{"servico": ..., "detalhamento": ...}]``.
        """
        return [{"servico": servico, "detalhamento": texto} for servico, texto in pedidos]

    @staticmethod
    def _url_dos_espacos(campos):
        """Return the step 1 URL carrying the date and headcount already chosen.

        "Alterar" o espaço não pode custar a data que a pessoa escolheu duas
        telas atrás.

        Args:
            campos: O resultado de ``_ler``.

        Returns:
            str: A URL do passo 1.
        """
        url = reverse("space_list")
        parametros = {}
        if campos["date_str"]:
            parametros["date"] = campos["date_str"]
        if campos["attendee_raw"].isdigit():
            parametros["people"] = campos["attendee_raw"]
        return f"{url}?{urlencode(parametros)}" if parametros else url


class ReservationEditView(_PassoTres):
    """Back from the review to step 3, with everything still filled in.

    Só ``POST``, e de propósito: o que traz a pessoa de volta é o conteúdo do
    formulário da revisão, não uma URL. Um ``GET`` aqui não teria o que
    mostrar, e é para isso que existe ``GET /reservations/new/``.

    Não valida nada. A pessoa clicou em "Alterar" justamente porque quer
    mexer — recebê-la com uma mensagem de erro sobre o que ela já decidiu
    corrigir seria ruído.
    """

    def post(self, request):
        """Re-render step 3 from the review's hidden fields."""
        space = self._espaco_do_post(request)
        if space is None:
            messages.error(request, "Selecione um espaço antes de reservar.")
            return redirect("space_list")
        return self._renderizar(request, space, self._ler(request))


class ReservationDetailsEditView(_PassoTres):
    """Edit what an existing reservation is about, after it was created.

    Reaproveita o passo 3 no que ele tem de reutilizável — o seletor de
    serviços, a montagem dos pedidos, a validação de detalhamento — mas **não**
    é um passo do fluxo: não tem stepper, não tem revisão e não passa pela
    criação. É a mesma pergunta ("do que se trata?") feita depois.

    Data, hora e espaço ficam de fora de propósito. Mudar quando ou onde é
    disputar a agenda com outras pessoas, e para isso existe ``Reagendar``, com
    revalidação completa. Aqui nada compete com ninguém.
    """

    template_name = "reservations/reservation_details_edit.html"

    def get(self, request, pk):
        """Render the edit form filled with what the reservation says today."""
        reservation = self._reserva_editavel(request, pk)
        if not isinstance(reservation, Reservation):
            return reservation

        pedidos_atuais = list(reservation.service_requests.select_related("service_type"))
        campos = {
            "title": reservation.title,
            "attendee_raw": str(reservation.attendee_count or ""),
            "notes": reservation.notes,
            "servicos_marcados": [str(pedido.service_type_id) for pedido in pedidos_atuais],
            "detalhamentos": {
                str(pedido.service_type_id): pedido.notes for pedido in pedidos_atuais
            },
        }
        return render(request, self.template_name, self._contexto(reservation, campos))

    def post(self, request, pk):
        """Save the new details and bring the service requests in line."""
        reservation = self._reserva_editavel(request, pk)
        if not isinstance(reservation, Reservation):
            return reservation

        campos = self._ler(request)
        try:
            pedidos = montar_pedidos(
                reservation.space,
                [(chave, campos["detalhamentos"][chave]) for chave in campos["servicos_marcados"]],
            )
        except ServiceNotesRequiredError as exc:
            return render(
                request,
                self.template_name,
                self._contexto(
                    reservation,
                    campos,
                    erro=" ".join(exc.messages),
                    servico_com_erro=exc.service_type,
                ),
            )

        attendee_count = None
        if campos["attendee_raw"]:
            if not campos["attendee_raw"].isdigit():
                return render(
                    request,
                    self.template_name,
                    self._contexto(reservation, campos, erro=ATTENDEE_COUNT_INVALID_MESSAGE),
                )
            attendee_count = int(campos["attendee_raw"])

        try:
            atualizar_detalhes(
                reservation,
                request.user,
                title=campos["title"],
                attendee_count=attendee_count,
                notes=campos["notes"],
            )
        except OwnershipError as exc:
            messages.error(request, str(exc))
            return redirect("reservation_detail", pk=pk)
        except ValidationError as exc:
            return render(
                request, self.template_name, self._contexto(reservation, campos, erro=str(exc))
            )

        resultado = sincronizar_servicos(reservation, pedidos)
        messages.success(request, "Reserva atualizada.")
        for _service_type, motivo in resultado["recusados"] + resultado["mantidos"]:
            # O que não pôde ser feito é dito em voz alta: o silêncio aqui faria
            # a pessoa acreditar que desmarcou algo que continua na fila.
            messages.warning(request, motivo)
        return redirect("reservation_detail", pk=pk)

    def _reserva_editavel(self, request, pk):
        """Return the reservation, or the redirect that explains why not.

        Args:
            request: A requisição.
            pk: O identificador da reserva.

        Returns:
            Reservation | HttpResponse: A reserva, ou o redirecionamento pronto.
        """
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)
        if reservation.status not in ACTIVE_RESERVATION_STATUSES:
            messages.error(
                request, "Só é possível editar reservas confirmadas ou com check-in realizado."
            )
            return redirect("reservation_detail", pk=pk)
        return reservation

    def _contexto(self, reservation, campos, *, erro=None, servico_com_erro=None):
        """Build the template context for the edit screen.

        Args:
            reservation: A reserva editada.
            campos: Os campos como estão no formulário.
            erro: O que deu errado, se algo deu.
            servico_com_erro: O serviço cujo campo deve receber o foco.

        Returns:
            dict: Contexto do template.
        """
        pedidos_travados = self._pedidos_travados(reservation)
        travados = {
            pedido.service_type_id: (
                f"Já está com a administração ({pedido.get_status_display().lower()}). "
                "Fale com ela para cancelar."
            )
            for pedido in pedidos_travados
        }
        return {
            "reservation": reservation,
            "space": reservation.space,
            "error": erro,
            "prefill_title": campos["title"],
            "prefill_attendee_count": campos["attendee_raw"],
            "prefill_notes": campos["notes"],
            "servicos_grupos": self._grupos_de_servicos(
                reservation.space,
                # Os travados entram sempre marcados: não há como desmarcá-los,
                # então a tela não pode mostrá-los desmarcados nem por um
                # instante.
                list(campos["servicos_marcados"]) + [str(pk) for pk in travados],
                campos["detalhamentos"],
                servico_com_erro,
                travados,
            ),
            "pedidos_travados": pedidos_travados,
        }

    @staticmethod
    def _pedidos_travados(reservation):
        """Return the requests the administration already picked up.

        A tela precisa dizer, antes de a pessoa tentar, que desmarcar aquele
        item não vai adiantar — e por quê.

        Args:
            reservation: A reserva editada.

        Returns:
            list: Pedidos que não saem por desmarcar.
        """
        return [
            pedido
            for pedido in reservation.service_requests.select_related("service_type")
            if pedido.status in STATUS_PENDENTES and pedido.status != ServiceRequestStatus.REQUESTED
        ]


class ReservationCancelView(LoginRequiredMixin, View):
    """View for canceling a reservation via web interface."""

    def post(self, request, pk):
        """Cancel the reservation and redirect with success message."""
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

        try:
            cancel_reservation(reservation, request.user)
            messages.success(request, "Reserva cancelada com sucesso!")
        except OwnershipError:
            messages.error(request, "Você não tem permissão para cancelar esta reserva.")
        except ValidationError as exc:
            messages.error(request, str(exc))

        # Check if this is an HTMX request
        if request.headers.get("HX-Request"):
            return render(
                request,
                "reservations/reservation_detail.html",
                {
                    "reservation": reservation,
                    "can_cancel": False,
                    "can_check_in": False,
                    "can_reschedule": False,
                },
            )

        return redirect("reservation_detail", pk=pk)


class ReservationCheckInView(LoginRequiredMixin, View):
    """View for checking in to a reservation via web interface."""

    def post(self, request, pk):
        """Check in to the reservation and redirect with success message."""
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

        try:
            check_in_reservation(reservation, request.user)
            messages.success(request, "Check-in realizado com sucesso!")
        except OwnershipError:
            messages.error(request, "Você não tem permissão para fazer check-in nesta reserva.")
        except ValidationError as exc:
            messages.error(request, str(exc))

        # Check if this is an HTMX request
        if request.headers.get("HX-Request"):
            return render(
                request,
                "reservations/reservation_detail.html",
                {
                    "reservation": reservation,
                    "can_cancel": reservation.status
                    in {ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN},
                    "can_check_in": False,
                    "can_reschedule": reservation.status
                    in {ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN},
                },
            )

        return redirect("reservation_detail", pk=pk)


class ReservationRescheduleView(LoginRequiredMixin, View):
    """View for rescheduling a reservation via web interface."""

    template_name = "reservations/reservation_reschedule.html"

    def get(self, request, pk):
        """Render the reschedule form."""
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

        # Only allow rescheduling confirmed or checked-in reservations
        if reservation.status not in {
            ReservationStatus.CONFIRMED,
            ReservationStatus.CHECKED_IN,
        }:
            messages.error(request, "Esta reserva não pode ser reagendada.")
            return redirect("reservation_detail", pk=pk)

        # ``localtime`` porque o banco devolve o instante em UTC e o formulário
        # fala no fuso do usuário. Sem isto uma reserva das 14:00 em Goiás abria
        # o reagendamento marcando 17:00, e quem apenas confirmasse a tela
        # moveria a própria reserva três horas para a frente.
        inicio = timezone.localtime(reservation.start_time)
        fim = timezone.localtime(reservation.end_time)
        context = {
            "reservation": reservation,
            "prefill_date": inicio.strftime("%Y-%m-%d"),
            "prefill_start_time": inicio.strftime("%H:%M"),
            "prefill_end_time": fim.strftime("%H:%M"),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        """Process the reschedule form."""
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)

        date_str = request.POST.get("date", "").strip()
        start_time_str = request.POST.get("start_time", "").strip()
        end_time_str = request.POST.get("end_time", "").strip()

        try:
            start_time = self._parse_datetime(date_str, start_time_str)
            end_time = self._parse_datetime(date_str, end_time_str)
        except ValueError:
            context = {
                "reservation": reservation,
                "error": "Formato de data ou hora inválido.",
                "prefill_date": date_str,
                "prefill_start_time": start_time_str,
                "prefill_end_time": end_time_str,
            }
            return render(request, self.template_name, context)

        try:
            reschedule_reservation(reservation, request.user, start_time, end_time)
            messages.success(request, "Reserva reagendada com sucesso!")
            return redirect("reservation_detail", pk=pk)
        except OwnershipError:
            messages.error(request, "Você não tem permissão para reagendar esta reserva.")
            return redirect("reservation_detail", pk=pk)
        except ValidationError as exc:
            context = {
                "reservation": reservation,
                "error": str(exc),
                "prefill_date": date_str,
                "prefill_start_time": start_time_str,
                "prefill_end_time": end_time_str,
            }
            return render(request, self.template_name, context)

    @staticmethod
    def _parse_datetime(date_str: str, time_str: str) -> datetime.datetime:
        """Combine date and time strings into a timezone-aware datetime in the local zone."""
        if not date_str or not time_str:
            raise ValueError("Missing date or time")
        naive = datetime.datetime.strptime(
            f"{date_str} {time_str}",
            "%Y-%m-%d %H:%M",
        )
        # O usuário digita no fuso local; make_aware traduz para o instante correto.
        return timezone.make_aware(naive)
