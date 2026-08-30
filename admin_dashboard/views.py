"""Views for the admin dashboard app."""

import csv
import datetime

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import urlencode
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from ai_assistant.exceptions import AIServiceError
from ai_assistant.services import classify_maintenance_reason
from core.models import HelpArticle
from reservations import calendario, relatorios
from reservations.models import (
    BookingPolicy,
    MaintenanceBlock,
    Reservation,
    ReservationStatus,
)
from reservations.services import admin_cancel_reservation
from services.enums import STATUS_PENDENTES, ServiceRequestStatus
from services.models import ReservationServiceRequest, ServiceType
from services.services import atualizar_situacao
from spaces.models import Attribute, Space, SpaceType

from .forms import (
    AdminUserCreateForm,
    AdminUserUpdateForm,
    AttributeForm,
    BookingPolicyForm,
    HelpArticleForm,
    MaintenanceBlockForm,
    ServiceTypeForm,
    SpaceForm,
    SpaceTypeForm,
)


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin that requires the user to be staff."""

    def test_func(self):
        """Return True if the user is staff."""
        return self.request.user.is_staff


class AdminDashboardView(StaffRequiredMixin, View):
    """Admin dashboard view showing real-time occupancy overview."""

    template_name = "admin_dashboard/index.html"

    def get(self, request):
        """Render the admin dashboard with occupancy metrics and space cards."""
        now = timezone.now()
        today = timezone.localdate(now)
        today_start = timezone.make_aware(datetime.datetime.combine(today, datetime.time.min))
        today_end = timezone.make_aware(
            datetime.datetime.combine(today + datetime.timedelta(days=1), datetime.time.min)
        )

        total_spaces = Space.objects.count()

        # Occupied now: confirmed or checked_in reservations overlapping current time
        occupied_reservation_space_ids = set(
            Reservation.objects.filter(
                space__isnull=False,
                status__in=[ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN],
                start_time__lte=now,
                end_time__gt=now,
            ).values_list("space_id", flat=True)
        )

        # Maintenance now: maintenance blocks overlapping current time
        maintenance_space_ids = set(
            MaintenanceBlock.objects.filter(
                space__isnull=False,
                start_time__lte=now,
                end_time__gt=now,
            ).values_list("space_id", flat=True)
        )

        occupied_now = len(occupied_reservation_space_ids)
        maintenance_now = len(maintenance_space_ids)
        available_now = total_spaces - occupied_now - maintenance_now

        # No-shows today
        no_shows_today = Reservation.objects.filter(
            status=ReservationStatus.NO_SHOW,
            start_time__gte=today_start,
            start_time__lt=today_end,
        ).count()

        # Space cards data
        spaces = Space.objects.all().order_by("name")
        space_cards = []
        for space in spaces:
            if space.id in maintenance_space_ids:
                status = "maintenance"
                status_label = "Manutenção"
                status_class = "border-warning/40 text-warning"
            elif space.id in occupied_reservation_space_ids:
                status = "occupied"
                status_label = "Ocupado"
                status_class = "border-error/40 text-error"
            else:
                status = "free"
                status_label = "Livre"
                status_class = "border-success/40 text-success"

            space_cards.append(
                {
                    "id": space.id,
                    "name": space.name,
                    "capacity": space.capacity,
                    "location": space.location,
                    "is_active": space.is_active,
                    "status": status,
                    "status_label": status_label,
                    "status_class": status_class,
                }
            )

        context = {
            "total_spaces": total_spaces,
            "occupied_now": occupied_now,
            "available_now": available_now,
            "maintenance_now": maintenance_now,
            "no_shows_today": no_shows_today,
            "space_cards": space_cards,
        }

        # HTMX partial refresh
        if request.headers.get("HX-Request") == "true":
            return render(request, "admin_dashboard/_occupancy_grid.html", context)

        return render(request, self.template_name, context)


class AdminSpaceListView(StaffRequiredMixin, ListView):
    """List view for admin space management."""

    model = Space
    template_name = "admin_dashboard/space_list.html"
    context_object_name = "spaces"
    queryset = (
        Space.objects.select_related("space_type")
        .prefetch_related("space_attributes__attribute")
        .order_by("name")
    )


class AdminSpaceCreateView(StaffRequiredMixin, CreateView):
    """Create view for spaces (admin only)."""

    model = Space
    form_class = SpaceForm
    template_name = "admin_dashboard/space_form.html"
    success_url = reverse_lazy("admin_dashboard:space_list")


class AdminSpaceUpdateView(StaffRequiredMixin, UpdateView):
    """Update view for spaces (admin only)."""

    model = Space
    form_class = SpaceForm
    template_name = "admin_dashboard/space_form.html"
    success_url = reverse_lazy("admin_dashboard:space_list")


class AdminSpaceToggleView(StaffRequiredMixin, View):
    """Toggle the is_active status of a space inline (admin only)."""

    def patch(self, request, pk):
        """Toggle is_active and return the updated badge HTML."""
        space = get_object_or_404(Space, pk=pk)
        space.is_active = not space.is_active
        space.save(update_fields=["is_active"])
        return render(request, "admin_dashboard/_space_status_badge.html", {"space": space})


class AdminSpaceTypeListView(StaffRequiredMixin, ListView):
    """List view for space types (admin only)."""

    model = SpaceType
    template_name = "admin_dashboard/space_type_list.html"
    context_object_name = "space_types"

    def get_queryset(self):
        """Return the types with the number of spaces using each one."""
        return SpaceType.objects.annotate(total_espacos=Count("spaces")).order_by(
            "sort_order", "name"
        )


class AdminSpaceTypeCreateView(StaffRequiredMixin, CreateView):
    """Create view for space types (admin only)."""

    model = SpaceType
    form_class = SpaceTypeForm
    template_name = "admin_dashboard/space_type_form.html"
    success_url = reverse_lazy("admin_dashboard:space_type_list")


class AdminSpaceTypeUpdateView(StaffRequiredMixin, UpdateView):
    """Update view for space types (admin only)."""

    model = SpaceType
    form_class = SpaceTypeForm
    template_name = "admin_dashboard/space_type_form.html"
    success_url = reverse_lazy("admin_dashboard:space_type_list")


class AdminAttributeListView(StaffRequiredMixin, ListView):
    """List view for equipment attributes (admin only)."""

    model = Attribute
    template_name = "admin_dashboard/attribute_list.html"
    context_object_name = "attributes"

    def get_queryset(self):
        """Return the attributes with how many active spaces offer each one."""
        return Attribute.objects.annotate(
            total_espacos=Count(
                "space_attributes",
                filter=Q(space_attributes__space__is_active=True),
                distinct=True,
            )
        ).order_by("-is_featured", "sort_order", "name")


class AdminAttributeCreateView(StaffRequiredMixin, CreateView):
    """Create view for equipment attributes (admin only)."""

    model = Attribute
    form_class = AttributeForm
    template_name = "admin_dashboard/attribute_form.html"
    success_url = reverse_lazy("admin_dashboard:attribute_list")


class AdminAttributeUpdateView(StaffRequiredMixin, UpdateView):
    """Update view for equipment attributes (admin only)."""

    model = Attribute
    form_class = AttributeForm
    template_name = "admin_dashboard/attribute_form.html"
    success_url = reverse_lazy("admin_dashboard:attribute_list")


class AdminServiceTypeListView(StaffRequiredMixin, ListView):
    """List view for the service catalog (admin only)."""

    model = ServiceType
    template_name = "admin_dashboard/service_type_list.html"
    context_object_name = "service_types"

    def get_queryset(self):
        """Return the catalog with how many spaces offer each service."""
        return ServiceType.objects.annotate(
            total_espacos=Count("spaces", distinct=True),
            total_pedidos=Count(
                "requests",
                filter=Q(requests__status__in=STATUS_PENDENTES),
                distinct=True,
            ),
        ).order_by("sort_order", "name")


class AdminServiceTypeCreateView(StaffRequiredMixin, CreateView):
    """Create view for service types (admin only)."""

    model = ServiceType
    form_class = ServiceTypeForm
    template_name = "admin_dashboard/service_type_form.html"
    success_url = reverse_lazy("admin_dashboard:service_type_list")


class AdminServiceTypeUpdateView(StaffRequiredMixin, UpdateView):
    """Update view for service types (admin only)."""

    model = ServiceType
    form_class = ServiceTypeForm
    template_name = "admin_dashboard/service_type_form.html"
    success_url = reverse_lazy("admin_dashboard:service_type_list")


class AdminServiceQueueView(StaffRequiredMixin, ListView):
    """The operational queue of service requests.

    É o motivo de ``ReservationServiceRequest`` existir como tabela em vez de
    um booleano por serviço na reserva: sem situação e sem responsável não há
    fila de trabalho, só um aviso de que alguém pediu alguma coisa.

    A ordem é por início da reserva, e não por data do pedido: o que acontece
    primeiro precisa ser resolvido primeiro.
    """

    model = ReservationServiceRequest
    template_name = "admin_dashboard/service_queue.html"
    context_object_name = "requests"
    paginate_by = 30

    def get_queryset(self):
        """Return the requests, filtered by status when asked."""
        queryset = ReservationServiceRequest.objects.select_related(
            "reservation", "reservation__space", "reservation__user", "service_type"
        ).order_by("reservation__start_time")

        situacao = self.request.GET.get("status", "pendentes")
        if situacao == "pendentes":
            return queryset.filter(status__in=STATUS_PENDENTES)
        if situacao in ServiceRequestStatus.values:
            return queryset.filter(status=situacao)
        return queryset

    def get_context_data(self, **kwargs):
        """Add the status filter options and their counts."""
        context = super().get_context_data(**kwargs)
        context["situacao"] = self.request.GET.get("status", "pendentes")
        context["situacoes"] = ServiceRequestStatus.choices
        context["total_pendentes"] = ReservationServiceRequest.objects.filter(
            status__in=STATUS_PENDENTES
        ).count()
        return context


class AdminServiceRequestUpdateView(StaffRequiredMixin, View):
    """Move one service request to another status."""

    def post(self, request, pk):
        """Apply the new status and go back to the queue."""
        pedido = get_object_or_404(ReservationServiceRequest, pk=pk)
        novo = request.POST.get("status", "")
        if novo not in ServiceRequestStatus.values:
            messages.error(request, "Situação inválida.")
        else:
            atualizar_situacao(pedido, novo, request.user)
            messages.success(request, f"{pedido.service_type.name}: {pedido.get_status_display()}.")
        destino = request.POST.get("next") or reverse_lazy("admin_dashboard:service_queue")
        return redirect(destino)


class AdminBookingPolicyView(StaffRequiredMixin, UpdateView):
    """Edit the single booking policy (admin only).

    Não há lista nem criação: a política é uma só. ``get_object`` devolve sempre
    a mesma linha, de modo que a URL não carrega um ``pk`` que poderia apontar
    para uma segunda política inexistente.
    """

    model = BookingPolicy
    form_class = BookingPolicyForm
    template_name = "admin_dashboard/booking_policy_form.html"
    success_url = reverse_lazy("admin_dashboard:booking_policy")

    def get_object(self, queryset=None):
        """Return the singleton policy, creating it if needed."""
        return BookingPolicy.carregar()


class AdminReservationListView(StaffRequiredMixin, ListView):
    """List view for admin reservation management with filtering."""

    model = Reservation
    template_name = "admin_dashboard/reservation_list.html"
    context_object_name = "reservations"
    paginate_by = 25

    def get_queryset(self):
        """Return filtered queryset based on query parameters."""
        queryset = Reservation.objects.select_related("space", "user").order_by("-start_time")

        status_filter = self.request.GET.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        space_filter = self.request.GET.get("space")
        if space_filter:
            queryset = queryset.filter(space_id=space_filter)

        start_date = self.request.GET.get("start_date")
        if start_date:
            try:
                parsed = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
                dt_start = timezone.make_aware(datetime.datetime.combine(parsed, datetime.time.min))
                queryset = queryset.filter(start_time__gte=dt_start)
            except ValueError:
                pass

        end_date = self.request.GET.get("end_date")
        if end_date:
            try:
                parsed = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
                dt_end = timezone.make_aware(datetime.datetime.combine(parsed, datetime.time.max))
                queryset = queryset.filter(start_time__lte=dt_end)
            except ValueError:
                pass

        user_search = self.request.GET.get("user_search")
        if user_search:
            queryset = queryset.filter(user__username__icontains=user_search)

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter options and current filter values to context."""
        context = super().get_context_data(**kwargs)
        context["spaces"] = Space.objects.order_by("name")
        context["status_choices"] = ReservationStatus.choices
        context["current_filters"] = {
            "status": self.request.GET.get("status", ""),
            "space": self.request.GET.get("space", ""),
            "start_date": self.request.GET.get("start_date", ""),
            "end_date": self.request.GET.get("end_date", ""),
            "user_search": self.request.GET.get("user_search", ""),
        }
        return context

    def render_to_response(self, context, **response_kwargs):
        """Return partial template for HTMX filter requests."""
        if self.request.headers.get("HX-Request") == "true":
            return render(
                self.request,
                "admin_dashboard/_reservation_table.html",
                context,
            )
        return super().render_to_response(context, **response_kwargs)


class AdminCalendarView(StaffRequiredMixin, View):
    """The general calendar of the administration.

    É a mesma máquina de grade do calendário do usuário, alimentada por uma
    busca diferente: aqui as reservas vêm com assunto e com quem reservou,
    porque quem administra a agenda precisa saber a quem ligar quando a sala
    cai. A separação está na camada de busca, não numa condição no template.

    Todo o estado — visão, dia e os três filtros — vive na querystring, como no
    calendário do usuário: assim um horário problemático pode ser enviado por
    link para outra pessoa da administração e abrir exatamente igual.
    """

    template_name = "admin_dashboard/calendar.html"

    def get(self, request):
        """Render the general calendar for the requested view, date and filters."""
        vista = calendario.normalizar_vista(request.GET.get("vista"))
        dia = calendario.data_pedida(request.GET.get("data"))
        filtros = {
            "espaco": self._inteiro(request.GET.get("espaco")),
            "tipo": self._inteiro(request.GET.get("tipo")),
            "local": (request.GET.get("local") or "").strip(),
        }

        contexto = calendario.montar_calendario_geral(vista, dia, **filtros)
        # A grade é a mesma do calendário do usuário; o que muda é o desenho de
        # cada entrada, porque aqui a administração pode ver assunto e pessoa.
        contexto["modelo_de_entrada"] = "admin_dashboard/_calendar_entry.html"
        contexto["filtros"] = filtros
        contexto["ha_filtro"] = any(filtros.values())
        contexto["espacos"] = Space.objects.order_by("name")
        contexto["tipos"] = SpaceType.objects.order_by("name")
        # As localizações vêm dos espaços cadastrados, não de uma lista fixa:
        # uma lista fixa envelheceria no dia em que a administração criasse um
        # andar novo, e ofereceria filtros que não selecionam nada.
        contexto["locais"] = (
            Space.objects.exclude(location="")
            .values_list("location", flat=True)
            .distinct()
            .order_by("location")
        )
        contexto["url_limpar"] = self._url(vista, dia, {})
        contexto["url_anterior"] = self._url(vista, contexto["anterior"], filtros)
        contexto["url_proximo"] = self._url(vista, contexto["proximo"], filtros)
        contexto["url_hoje"] = self._url(vista, contexto["hoje"], filtros)
        for aba in contexto["vistas"]:
            aba["url"] = self._url(aba["chave"], dia, filtros)
        for celula in contexto["celulas"]:
            celula["url_do_dia"] = self._url(calendario.VISTA_DIA, celula["data"], filtros)
        return render(request, self.template_name, contexto)

    @staticmethod
    def _inteiro(bruto):
        """Return the filter as an int, or empty when it is not one.

        Um valor inventado na URL não é erro do usuário: é link velho ou
        endereço editado. Vira "sem filtro", e a tela mostra o calendário
        inteiro em vez de uma página de erro.
        """
        try:
            return int(bruto)
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _url(vista, dia, filtros):
        """Return the calendar URL for a view, date and filter set."""
        parametros = {"vista": vista, "data": dia.isoformat()}
        for chave in ("espaco", "tipo", "local"):
            valor = filtros.get(chave)
            if valor:
                parametros[chave] = valor
        return f"{reverse('admin_dashboard:calendar')}?{urlencode(parametros)}"


class _RelatorioBase(StaffRequiredMixin, View):
    """Shared assembly of the report period and its eight blocks.

    A tela e a exportação CSV herdam daqui pelo mesmo motivo que o Calendário
    Geral reaproveita a grade do calendário do usuário: se cada uma montasse os
    próprios números, um dia elas discordariam — e um relatório que discorda do
    próprio arquivo exportado é pior do que não ter exportação.
    """

    def _dados(self, request):
        """Return the period and every metric of it."""
        periodo = relatorios.periodo_pedido(
            request.GET.get("periodo"),
            request.GET.get("de"),
            request.GET.get("ate"),
        )
        politica = BookingPolicy.carregar()
        inicio, fim = periodo["inicio"], periodo["fim"]
        return {
            "periodo": periodo,
            "politica": politica,
            "expediente_minutos": relatorios.minutos_de_expediente(inicio, fim, politica),
            "ocupacao": relatorios.ocupacao_por_espaco(inicio, fim, politica),
            "picos": relatorios.picos(inicio, fim, politica),
            "cancelamentos": relatorios.cancelamentos(inicio, fim),
            "no_shows": relatorios.no_shows(inicio, fim, politica),
            "manutencao": relatorios.downtime_de_manutencao(inicio, fim, politica),
            "servicos": relatorios.servicos(inicio, fim),
            "antecedencia": relatorios.antecedencia(inicio, fim),
            "subutilizacao": relatorios.subutilizacao(inicio, fim),
        }


class AdminReportsView(_RelatorioBase):
    """The reports screen.

    Sem biblioteca de gráficos: as barras são divs com largura proporcional. O
    pacote V2 pede que gráfico responda pergunta real, e a única pergunta aqui
    que uma tabela responde mal é "a que horas o prédio enche" — que uma barra
    horizontal responde de relance e sem 300 KB de JavaScript.
    """

    template_name = "admin_dashboard/reports.html"

    def get(self, request):
        """Render every metric of the chosen period."""
        contexto = self._dados(request)
        contexto["presets"] = [
            {
                "chave": chave,
                "rotulo": rotulo,
                "atual": chave == contexto["periodo"]["preset"],
                "url": f"{reverse('admin_dashboard:reports')}?{urlencode({'periodo': chave})}",
            }
            for chave, rotulo in relatorios.PRESETS
        ]
        # O pico máximo normaliza as barras. Sem ele, um dia de duas reservas
        # desenharia a mesma barra de um dia de vinte.
        contexto["pico_maximo"] = max(
            [linha["reservas"] for linha in contexto["picos"]["por_hora"]] or [0]
        )
        contexto["pico_maximo_dia"] = max(
            [linha["reservas"] for linha in contexto["picos"]["por_dia_da_semana"]] or [0]
        )
        # ``request.GET.urlencode()``, e não ``urlencode(request.GET)``: o
        # segundo trata o QueryDict como um dicionário comum e serializa cada
        # valor como lista, produzindo ``periodo=%5B%277%27%5D``. O link
        # continuava funcionando — e devolvia o período **padrão**, porque o
        # valor não casava com preset nenhum. O arquivo saía de outro recorte
        # que o da tela, sem erro em lugar nenhum.
        # As taxas saem da camada de cálculo como fração (0–1). O template
        # tentava virar percentual anexando um "0" depois do ``floatformat`` —
        # truque que quebra em silêncio: 0,0142 virava "0,00%" na coluna, e no
        # ``width`` produzia ``0,014300%``, que é CSS inválido; o navegador
        # ignorava a largura e **toda** barra ficava cheia. Quem lê a tela via
        # sete espaços 100% ocupados com 0,00% escrito ao lado.
        #
        # O percentual passa a ser calculado aqui, e a largura sai formatada
        # com ponto — que é o separador decimal do CSS, independente do idioma
        # da interface.
        def com_percentual(linhas):
            """Add ``percentual`` (0–100) and a CSS-safe ``largura`` to each row."""
            for linha in linhas:
                taxa = linha["taxa"]
                linha["percentual"] = taxa * 100
                linha["largura"] = f"{min(taxa * 100, 100):.2f}"
            return linhas

        com_percentual(contexto["ocupacao"])
        com_percentual(contexto["subutilizacao"])
        com_percentual(contexto["manutencao"])
        for chave in ("cancelamentos", "no_shows"):
            contexto[chave] = {**contexto[chave], "percentual": contexto[chave]["taxa"] * 100}

        contexto["url_csv"] = (
            f"{reverse('admin_dashboard:reports_csv')}?{request.GET.urlencode()}"
        )
        return render(request, self.template_name, contexto)


class AdminReportsCsvView(_RelatorioBase):
    """The same numbers, as a file.

    Separador ponto e vírgula e decimal com vírgula, com BOM UTF-8: quem abre
    este arquivo abre no Excel em português, e o CSV do padrão — vírgula como
    separador, ponto como decimal — cai tudo numa coluna só e com acento
    quebrado. É desvio deliberado do RFC 4180 em favor de o arquivo funcionar
    na mão de quem pediu.
    """

    def get(self, request):
        """Return one CSV with every block, sectioned."""
        dados = self._dados(request)
        periodo = dados["periodo"]

        resposta = HttpResponse(content_type="text/csv; charset=utf-8")
        nome = f"relatorio-{periodo['primeiro_dia']:%Y%m%d}-a-{periodo['ultimo_dia']:%Y%m%d}.csv"
        resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
        # O BOM é o que faz o Excel reconhecer UTF-8 em vez de latin-1.
        resposta.write("\ufeff")
        escritor = csv.writer(resposta, delimiter=";")

        def numero(valor, casas=1):
            """Format a number the way a Brazilian spreadsheet expects it."""
            if valor is None:
                return ""
            return f"{valor:.{casas}f}".replace(".", ",")

        escritor.writerow(["Relatório de uso dos espaços"])
        escritor.writerow(["Período", periodo["rotulo"]])
        escritor.writerow(
            [
                "De",
                f"{periodo['primeiro_dia']:%d/%m/%Y}",
                "Até",
                f"{periodo['ultimo_dia']:%d/%m/%Y}",
            ]
        )
        escritor.writerow(
            ["Expediente no período (min por espaço)", numero(dados["expediente_minutos"], 0)]
        )
        escritor.writerow([])

        escritor.writerow(["Ocupação por espaço"])
        escritor.writerow(
            ["Espaço", "Minutos ocupados", "Minutos disponíveis", "Ocupação (%)", "Reservas"]
        )
        for linha in dados["ocupacao"]:
            escritor.writerow(
                [
                    linha["espaco"].name,
                    numero(linha["minutos_ocupados"], 0),
                    numero(linha["minutos_disponiveis"], 0),
                    numero(linha["taxa"] * 100),
                    linha["reservas"],
                ]
            )
        escritor.writerow([])

        escritor.writerow(["Picos por hora"])
        escritor.writerow(["Hora", "Reservas"])
        for linha in dados["picos"]["por_hora"]:
            escritor.writerow([linha["rotulo"], linha["reservas"]])
        escritor.writerow([])

        escritor.writerow(["Picos por dia da semana"])
        escritor.writerow(["Dia", "Reservas"])
        for linha in dados["picos"]["por_dia_da_semana"]:
            escritor.writerow([linha["rotulo"], linha["reservas"]])
        escritor.writerow([])

        cancel = dados["cancelamentos"]
        escritor.writerow(["Cancelamentos"])
        escritor.writerow(["Total", cancel["total"]])
        escritor.writerow(["Com data de cancelamento", cancel["por_ocorrencia"]])
        escritor.writerow(["Sem data (contados pelo horário da reserva)", cancel["sem_data"]])
        escritor.writerow(["Reservas marcadas no período", cancel["marcadas_no_periodo"]])
        escritor.writerow(["Taxa (%)", numero(cancel["taxa"] * 100)])
        escritor.writerow([])

        faltas = dados["no_shows"]
        escritor.writerow(["Não comparecimentos"])
        escritor.writerow(["Total", faltas["total"]])
        escritor.writerow(["Taxa (%)", numero(faltas["taxa"] * 100)])
        escritor.writerow(
            [
                "Liberação automática ligada",
                "sim" if faltas["regra_ligada"] else "não — sem ela nada marca no-show",
            ]
        )
        escritor.writerow([])

        escritor.writerow(["Manutenção (parada dentro do expediente)"])
        escritor.writerow(["Espaço", "Minutos", "Do expediente (%)", "Bloqueios"])
        for linha in dados["manutencao"]:
            escritor.writerow(
                [
                    linha["espaco"],
                    numero(linha["minutos"], 0),
                    numero(linha["taxa"] * 100, 2),
                    linha["bloqueios"],
                ]
            )
        escritor.writerow([])

        escritor.writerow(["Serviços solicitados"])
        escritor.writerow(["Serviço", "Total", "Situações"])
        for linha in dados["servicos"]:
            situacoes = ", ".join(
                f"{rotulo}: {qtd}" for rotulo, qtd in linha["por_situacao"].items()
            )
            escritor.writerow([linha["servico"], linha["total"], situacoes])
        escritor.writerow([])

        antec = dados["antecedencia"]
        escritor.writerow(["Antecedência da reserva"])
        escritor.writerow(["Média (horas)", numero(antec["media_horas"])])
        escritor.writerow(["Mediana (horas)", numero(antec["mediana_horas"])])
        escritor.writerow(["Reservas consideradas", antec["amostra"]])
        escritor.writerow([])

        escritor.writerow(["Uso da capacidade"])
        escritor.writerow(
            [
                "Espaço",
                "Capacidade",
                "Média de participantes",
                "Uso da capacidade (%)",
                "Com informação",
                "Reservas",
            ]
        )
        for linha in dados["subutilizacao"]:
            escritor.writerow(
                [
                    linha["espaco"],
                    linha["capacidade"],
                    numero(linha["media_participantes"]),
                    numero(linha["taxa"] * 100),
                    linha["com_informacao"],
                    linha["total"],
                ]
            )
        return resposta


class AdminReservationCancelView(StaffRequiredMixin, View):
    """Cancel any reservation (admin only)."""

    def post(self, request, pk):
        """Cancel the reservation and return the updated row HTML."""
        reservation = get_object_or_404(Reservation, pk=pk)
        try:
            admin_cancel_reservation(reservation)
        except ValidationError as exc:
            return HttpResponse(
                f'<span class="text-error text-sm">{exc.message}</span>',
                status=400,
            )

        if request.headers.get("HX-Request") == "true":
            return render(
                request,
                "admin_dashboard/_reservation_row.html",
                {"reservation": reservation},
            )

        return render(request, "admin_dashboard/reservation_list.html")


class AdminMaintenanceListView(StaffRequiredMixin, ListView):
    """List view for admin maintenance block management."""

    model = MaintenanceBlock
    template_name = "admin_dashboard/maintenance_list.html"
    context_object_name = "maintenance_blocks"
    queryset = MaintenanceBlock.objects.select_related("space").order_by("-start_time")


class AdminMaintenanceCreateView(StaffRequiredMixin, CreateView):
    """Create view for maintenance blocks (admin only)."""

    model = MaintenanceBlock
    form_class = MaintenanceBlockForm
    template_name = "admin_dashboard/maintenance_form.html"
    success_url = reverse_lazy("admin_dashboard:maintenance_list")

    def form_valid(self, form):
        """Set created_by to the current user before saving."""
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class AdminMaintenanceClassifyView(StaffRequiredMixin, View):
    """Classify a free-text maintenance reason into a category via AI (admin only)."""

    def post(self, request):
        """Call the AI classification service and return a suggestion partial."""
        reason = request.POST.get("reason", "").strip()
        if not reason:
            return render(
                request,
                "admin_dashboard/_maintenance_ai_suggestion.html",
                {"ai_error": "Descreva o motivo antes de pedir a sugestão da IA."},
            )

        try:
            classification = classify_maintenance_reason(reason)
        except AIServiceError as exc:
            return render(
                request,
                "admin_dashboard/_maintenance_ai_suggestion.html",
                {
                    "ai_error": exc.user_message,
                    "ai_error_detail": exc.technical_detail,
                },
            )

        return render(
            request,
            "admin_dashboard/_maintenance_ai_suggestion.html",
            {"classification": classification},
        )


class AdminMaintenanceDeleteView(StaffRequiredMixin, View):
    """Delete a maintenance block (admin only)."""

    def delete(self, request, pk):
        """Delete the maintenance block and return empty response for HTMX."""
        block = get_object_or_404(MaintenanceBlock, pk=pk)
        block.delete()
        if request.headers.get("HX-Request") == "true":
            return HttpResponse("", status=200)
        return HttpResponse("", status=200)


class AdminUserListView(StaffRequiredMixin, ListView):
    """List view for admin user management."""

    model = User
    template_name = "admin_dashboard/user_list.html"
    context_object_name = "users"
    queryset = User.objects.all().order_by("username")


class AdminUserCreateView(StaffRequiredMixin, CreateView):
    """Create view for users (admin only)."""

    model = User
    form_class = AdminUserCreateForm
    template_name = "admin_dashboard/user_form.html"
    success_url = reverse_lazy("admin_dashboard:user_list")


class AdminUserUpdateView(StaffRequiredMixin, UpdateView):
    """Update view for users (admin only)."""

    model = User
    form_class = AdminUserUpdateForm
    template_name = "admin_dashboard/user_form.html"
    success_url = reverse_lazy("admin_dashboard:user_list")


class AdminUserDeleteView(StaffRequiredMixin, View):
    """Delete a user (admin only)."""

    def delete(self, request, pk):
        """Delete the user, refusing to let an admin delete their own account."""
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            return HttpResponse(
                '<span class="text-error text-sm">Você não pode remover sua própria conta.</span>',
                status=400,
            )
        user.delete()
        return HttpResponse("", status=200)


class AdminHelpArticleListView(StaffRequiredMixin, ListView):
    """The institutional half of the help screen, as an editable list.

    A metade factual da Ajuda — horários, duração, check-in, no-show — não
    aparece aqui e não deve aparecer: ela é derivada da política a cada
    requisição. Se estivesse nesta lista, seria uma segunda cópia das regras,
    editável e livre para divergir daquilo que o sistema realmente faz.
    """

    model = HelpArticle
    template_name = "admin_dashboard/help_article_list.html"
    context_object_name = "blocos"

    def get_queryset(self):
        """Return every block, published or not, in display order."""
        return HelpArticle.objects.order_by("sort_order", "title")


class AdminHelpArticleCreateView(StaffRequiredMixin, CreateView):
    """Create view for help blocks (admin only)."""

    model = HelpArticle
    form_class = HelpArticleForm
    template_name = "admin_dashboard/help_article_form.html"
    success_url = reverse_lazy("admin_dashboard:help_article_list")


class AdminHelpArticleUpdateView(StaffRequiredMixin, UpdateView):
    """Update view for help blocks (admin only)."""

    model = HelpArticle
    form_class = HelpArticleForm
    template_name = "admin_dashboard/help_article_form.html"
    success_url = reverse_lazy("admin_dashboard:help_article_list")


class AdminHelpArticleDeleteView(StaffRequiredMixin, View):
    """Delete a help block.

    Apagar é POST, nunca GET: um link que apaga ao ser visitado é apagado por
    prefetch de navegador, por crawler e por quem clicou sem querer.
    """

    def post(self, request, pk):
        """Delete the block and return to the list."""
        bloco = get_object_or_404(HelpArticle, pk=pk)
        titulo = bloco.title
        bloco.delete()
        messages.success(request, f"Bloco “{titulo}” removido.")
        return redirect("admin_dashboard:help_article_list")
