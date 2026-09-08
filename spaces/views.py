"""Views for the spaces app."""

import datetime

import django_filters
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import DetailView, ListView
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ai_assistant.exceptions import AIServiceError
from ai_assistant.services import extract_room_search_filters
from reservations.availability import (
    STATUS_DE_HORARIO,
    agrupar_por_periodo,
    contexto_temporal,
    data_dentro_do_horizonte,
    duracao_valida,
    duracoes_oferecidas,
    espacos_equivalentes,
    gerar_slots,
    horarios_proximos,
    marcar_cabimento,
    resumo_em_lote,
    rotulo_de_duracao,
)
from reservations.models import BookingPolicy
from reservations.services import get_availability_for_date
from reservations.steps import FLUXO_V2, contexto_do_stepper

from .models import Attribute, Space, SpaceType
from .serializers import SpaceSerializer


class SpaceFilterSet(django_filters.FilterSet):
    """Filter set for searching spaces by attributes and capacity."""

    min_capacity = django_filters.NumberFilter(field_name="capacity", lookup_expr="gte")
    max_capacity = django_filters.NumberFilter(field_name="capacity", lookup_expr="lte")
    attributes = django_filters.CharFilter(method="filter_attributes")
    location = django_filters.CharFilter(field_name="location", lookup_expr="icontains")
    space_type = django_filters.CharFilter(field_name="space_type__slug")

    class Meta:
        """Meta options for SpaceFilterSet."""

        model = Space
        fields = ["is_active", "location", "space_type"]

    def filter_attributes(self, queryset, _name, value):
        """Filter spaces that have all specified attributes."""
        if not value:
            return queryset
        attr_names = [v.strip() for v in value.split(",") if v.strip()]
        for attr_name in attr_names:
            queryset = queryset.filter(space_attributes__attribute__name=attr_name)
        return queryset.distinct()


class SpaceViewSet(viewsets.ModelViewSet):
    """ViewSet for listing, retrieving, creating and updating spaces."""

    queryset = Space.objects.select_related("space_type").prefetch_related(
        "space_attributes__attribute"
    )
    serializer_class = SpaceSerializer
    filterset_class = SpaceFilterSet

    def get_permissions(self):
        """Restrict write operations to admin users."""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["get"], url_path="availability")
    def availability(self, request, pk=None):
        """Return occupied and free time slots for a space on a given date."""
        space = self.get_object()
        date_str = request.query_params.get("date")

        if not date_str:
            raise ValidationError({"date": "This parameter is required."})

        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValidationError({"date": "Invalid date format. Use YYYY-MM-DD."}) from exc

        data = get_availability_for_date(space, date)
        return Response(data)


class SpaceListView(LoginRequiredMixin, ListView):
    """List view for spaces with filtering capabilities."""

    model = Space
    template_name = "spaces/space_list.html"
    context_object_name = "spaces"

    def get_queryset(self):
        """Filter spaces based on query parameters."""
        queryset = (
            Space.objects.filter(is_active=True)
            .select_related("space_type")
            .prefetch_related("space_attributes__attribute")
        )

        # A aba escolhida vale também para a busca com IA: o usuário já disse em
        # que categoria quer procurar, e a IA não deveria desfazer isso.
        tipo = self.request.GET.get("type", "").strip()
        if tipo:
            queryset = queryset.filter(space_type__slug=tipo)

        ai_query = self.request.GET.get("ai_query", "").strip()
        if ai_query:
            return self._filter_by_ai_query(queryset, ai_query)

        # "Quantas pessoas?" é a pergunta humana; capacidade mínima e máxima são
        # a tradução dela para o banco. O formulário só emite ``people``, mas
        # ``min_capacity``/``max_capacity`` continuam aceitos: são o contrato da
        # API e podem estar em links que alguém guardou.
        queryset = self._filtrar_por_capacidade(queryset)

        # Filter by attributes (AND entre todos os selecionados)
        attr_names = self._selected_attribute_names()
        if attr_names:
            for attr_name in attr_names:
                queryset = queryset.filter(space_attributes__attribute__name=attr_name)
            queryset = queryset.distinct()

        # Filter by location (case-insensitive)
        location = self.request.GET.get("location")
        if location:
            queryset = queryset.filter(location__icontains=location)

        return queryset.order_by("name")

    def _filtrar_por_capacidade(self, queryset):
        """Apply the people/capacity filters.

        Args:
            queryset: O queryset em construção.

        Returns:
            QuerySet: Restrito pela capacidade pedida.
        """
        pessoas = self._pessoas()
        if pessoas:
            queryset = queryset.filter(capacity__gte=pessoas)

        for parametro, lookup in [("min_capacity", "gte"), ("max_capacity", "lte")]:
            bruto = self.request.GET.get(parametro)
            if not bruto:
                continue
            try:
                queryset = queryset.filter(**{f"capacity__{lookup}": int(bruto)})
            except ValueError:
                continue
        return queryset

    def _pessoas(self):
        """Return how many people the user said they need, or ``None``.

        Um valor sem sentido — texto, zero, negativo — é ignorado em vez de
        virar erro: o campo é um auxílio de busca, não um formulário de reserva.

        Returns:
            int | None: A quantidade informada, quando utilizável.
        """
        bruto = self.request.GET.get("people", "").strip()
        if not bruto:
            return None
        try:
            pessoas = int(bruto)
        except ValueError:
            return None
        return pessoas if pessoas > 0 else None

    def _selected_attribute_names(self):
        """Return the attribute names selected in the request, without duplicates.

        Os checkboxes do formulário enviam um ``attributes`` por item marcado, então
        ``getlist`` é obrigatório — ``get`` devolveria apenas o último e o filtro
        silenciosamente ignoraria os demais. A forma separada por vírgula continua
        aceita porque é o contrato da API e pode estar em links salvos.

        Returns:
            list[str]: Nomes de atributo na ordem em que foram informados.
        """
        names = []
        for raw in self.request.GET.getlist("attributes"):
            for name in raw.split(","):
                name = name.strip()
                if name and name not in names:
                    names.append(name)
        return names

    def _filter_by_ai_query(self, queryset, ai_query):
        """Interpret a natural-language search via the AI service and filter spaces.

        Stores ``ai_summary`` or ``ai_error`` on the instance for get_context_data.
        """
        try:
            filters = extract_room_search_filters(ai_query, contexto_temporal())
        except AIServiceError as exc:
            self.ai_error = exc.user_message
            self.ai_error_detail = exc.technical_detail
            return queryset.none()

        self.ai_summary = filters["summary"]
        # A capacidade inferida volta para o campo "Quantas pessoas?": o usuário
        # vê o que a IA entendeu e pode corrigir sem reescrever a frase inteira.
        self.ai_people = filters.get("min_capacity")
        self.ai_location = filters.get("location") or ""
        self.ai_attributes = list(filters["attributes"])
        self.ai_date = filters.get("date")
        self.ai_start_time = filters.get("start_time")
        self.ai_duration = filters.get("duration_minutes")
        # O que a IA devolveu e a regra recusou é dito em voz alta. Descartar em
        # silêncio deixaria o resumo prometendo uma data que a tela não mostra.
        self.ai_avisos = list(filters.get("avisos") or [])
        if filters.get("min_capacity"):
            queryset = queryset.filter(capacity__gte=filters["min_capacity"])
        if filters.get("max_capacity"):
            queryset = queryset.filter(capacity__lte=filters["max_capacity"])
        if filters["location"]:
            queryset = queryset.filter(location__icontains=filters["location"])
        for attribute_name in filters["attributes"]:
            queryset = queryset.filter(space_attributes__attribute__name__icontains=attribute_name)

        return queryset.distinct().order_by("name")

    def get_context_data(self, **kwargs):
        """Add filter options and selected filters to context."""
        context = super().get_context_data(**kwargs)
        # Os equipamentos vêm separados em duas listas: os de destaque, que ficam
        # visíveis, e o resto, que fica atrás de "mais equipamentos". Sem nenhum
        # destaque marcado, `destacados` é vazio e a tela lista todos como antes.
        atributos = list(Attribute.objects.all())
        selecionados = self._selected_attribute_names()
        outros = [a for a in atributos if not a.is_featured]
        # Ordenado por categoria para que o ``regroup`` do template funcione.
        # Com todas as categorias em branco vira um grupo só, sem cabeçalho.
        outros.sort(key=lambda a: (a.category, a.sort_order, a.name))
        context["attributes"] = atributos
        context["featured_attributes"] = [a for a in atributos if a.is_featured]
        context["other_attributes"] = outros
        # Um filtro marcado que ficou escondido atrás do "mais equipamentos"
        # seria um resultado inexplicável: a seção abre sozinha nesse caso.
        context["has_hidden_selection"] = any(a.name in selecionados for a in outros)
        # Depois de uma busca com IA, os checkboxes mostram o que ela entendeu.
        # Assim a pessoa vê a interpretação e ajusta clicando, em vez de
        # reescrever a frase inteira.
        exibidos = selecionados or getattr(self, "ai_attributes", [])
        context["selected_attributes"] = exibidos
        context["filtros_avancados_ativos"] = len(exibidos) + (
            1 if self.request.GET.get("location", "").strip() else 0
        )
        context["min_capacity"] = self.request.GET.get("min_capacity", "")
        context["max_capacity"] = self.request.GET.get("max_capacity", "")
        # O campo mostra o que o usuário digitou; se ele não digitou nada e a
        # busca com IA inferiu um número, mostra o número inferido.
        pessoas = self._pessoas()
        context["people"] = pessoas or getattr(self, "ai_people", None) or ""
        context["location"] = self.request.GET.get("location", "") or getattr(
            self, "ai_location", ""
        )
        context["ai_query"] = self.request.GET.get("ai_query", "")
        context["ai_summary"] = getattr(self, "ai_summary", "")
        context["ai_avisos"] = getattr(self, "ai_avisos", [])
        context["ai_error"] = getattr(self, "ai_error", "")
        context["ai_error_detail"] = getattr(self, "ai_error_detail", "")
        context["is_htmx"] = self.request.headers.get("HX-Request") == "true"
        context["space_types"] = SpaceType.objects.filter(is_active=True)
        context["selected_type"] = self.request.GET.get("type", "")
        context["query_sem_tipo"] = self._querystring_sem("type")

        # Resumo de disponibilidade para a data escolhida. São duas consultas no
        # total, independentemente de quantos cartões a página tiver: uma
        # consulta por cartão seria o N+1 que o pacote V2 proíbe.
        policy = BookingPolicy.carregar()
        data = self._data_selecionada(policy)
        inicio, duracao = self._horario_pedido(policy)
        espacos = list(context["spaces"])
        resumo = resumo_em_lote(espacos, data, policy, inicio=inicio, duracao_minutos=duracao)
        # O resumo é anexado a cada espaço porque o template Django não indexa
        # dicionário por variável. A lista precisa ser materializada antes: um
        # queryset seria reavaliado na iteração do template e o atributo se
        # perderia.
        for espaco in espacos:
            espaco.resumo_disponibilidade = resumo.get(espaco.pk)
        context["spaces"] = espacos
        context["object_list"] = espacos
        hoje = timezone.localdate()
        context["policy"] = policy
        context["selected_date"] = data
        context["hoje"] = hoje
        context["data_e_hoje"] = data == hoje
        context["data_maxima"] = hoje + datetime.timedelta(days=policy.horizon_days)
        context["availability_summary"] = resumo
        context["horario_pedido"] = inicio
        context["duracao_pedida"] = duracao
        context["querystring_sem_horario"] = self._querystring_sem_horario()
        # O cartão precisa saber que o rótulo já fala de um horário exato, para
        # não emendar "hoje" depois de "Disponível no horário".
        context["rotulo_e_de_horario"] = inicio is not None
        context["STATUS_DE_HORARIO"] = STATUS_DE_HORARIO

        # Seleção do passo 1. É estado de servidor, não de navegador: o espaço
        # escolhido viaja na querystring, então recarregar a página, voltar pelo
        # histórico ou compartilhar o link preserva a escolha.
        selecionado = self._espaco_selecionado(espacos)
        context["espaco_selecionado"] = selecionado
        if selecionado:
            selecionado.resumo_disponibilidade = resumo.get(selecionado.pk)
        context["querystring_sem_espaco"] = self._querystring_sem("space")
        sugerido = self._sugestao_para_confirmar(espacos)
        context["sugerir_confirmacao"] = sugerido
        context["querystring_descartar_sugestao"] = self._querystring_descartar_sugestao()

        # Etapa 1 do fluxo de reserva: escolher o espaço.
        context.update(contexto_do_stepper(1, FLUXO_V2))
        return context

    def _sugestao_para_confirmar(self, espacos):
        """Return the single AI match that still needs an explicit confirmation.

        A unique result is not a reservation yet: the person still chooses
        whether to continue or stay on the list. Manual filters, already
        chosen rooms and a dismissed suggestion stay out of the dialog.

        Args:
            espacos: The spaces currently listed.

        Returns:
            Space | None: The room to propose, when the conditions hold.
        """
        if not self.request.GET.get("ai_query", "").strip():
            return None
        if self.request.GET.get("space", "").strip():
            return None
        if self.request.GET.get("descartar_sugestao") == "1":
            return None
        if len(espacos) != 1:
            return None
        return espacos[0]

    def _querystring_descartar_sugestao(self):
        """Return the current querystring plus the dismissal flag.

        Returns:
            str: The encoded querystring.
        """
        parametros = self.request.GET.copy()
        parametros["descartar_sugestao"] = "1"
        return parametros.urlencode()

    def _horario_pedido(self, policy):
        """Return the requested time window, from the URL or from the AI.

        O horário não tem campo próprio na barra de controles — o pacote V2 pede
        Data, Pessoas e Filtros, e mais nada. Ele chega pela busca com IA ou por
        um link, e a tela mostra um chip removível para que a pessoa possa
        desfazer sem editar a URL.

        Args:
            policy: A política vigente.

        Returns:
            tuple: ``(início, duração em minutos)``; ``(None, None)`` quando não
            há horário pedido.
        """
        bruto = self.request.GET.get("start", "").strip()
        inicio = None
        if bruto:
            try:
                candidato = datetime.datetime.strptime(bruto, "%H:%M").time()
            except ValueError:
                candidato = None
            if candidato and policy.opening_time <= candidato < policy.closing_time:
                inicio = candidato
        if inicio is None:
            inicio = getattr(self, "ai_start_time", None)
        if inicio is None:
            return None, None

        duracao = None
        bruto_duracao = self.request.GET.get("duration", "").strip()
        if bruto_duracao.isdigit():
            candidata = int(bruto_duracao)
            if policy.min_duration_minutes <= candidata <= policy.max_duration_minutes:
                duracao = candidata
        if duracao is None:
            duracao = getattr(self, "ai_duration", None)
        return inicio, duracao

    def _querystring_sem_horario(self):
        """Return the querystring without the time window.

        Returns:
            str: A querystring restante, já com ``&`` no fim quando não vazia.
        """
        parametros = self.request.GET.copy()
        for chave in ["start", "duration", "ai_query"]:
            parametros.pop(chave, None)
        codificada = parametros.urlencode()
        return f"{codificada}&" if codificada else ""

    def _espaco_selecionado(self, espacos):
        """Return the space chosen in ``?space=``, when it is still on the list.

        Se o espaço escolhido sair do resultado — o usuário apertou o filtro
        depois de escolher —, a seleção cai. Manter no resumo um espaço que não
        está mais na lista deixaria a tela contradizendo a si mesma.

        Args:
            espacos: Os espaços exibidos.

        Returns:
            Space | None: O selecionado, se ainda visível.
        """
        bruto = self.request.GET.get("space", "").strip()
        if not bruto.isdigit():
            return None
        escolhido = int(bruto)
        return next((espaco for espaco in espacos if espaco.pk == escolhido), None)

    def _data_selecionada(self, policy):
        """Return the date the availability summary refers to.

        Uma data inválida ou fora do horizonte cai em hoje, em vez de gerar
        erro: o seletor é um auxílio de busca, não o formulário de reserva — a
        data definitiva é confirmada no passo 2.

        Args:
            policy: A política vigente.

        Returns:
            date: A data efetivamente considerada.
        """
        hoje = timezone.localdate()
        # A data inferida pela busca com IA vence a que estava na tela: quem
        # escreveu "amanhã" acabou de dizer qual data quer. Sem menção a tempo,
        # o campo escondido do formulário preserva a escolha anterior.
        inferida = getattr(self, "ai_date", None)
        if inferida and data_dentro_do_horizonte(inferida, policy, hoje=hoje):
            return inferida

        bruto = self.request.GET.get("date", "").strip()
        if not bruto:
            return hoje
        try:
            escolhida = datetime.datetime.strptime(bruto, "%Y-%m-%d").date()
        except ValueError:
            return hoje
        if not data_dentro_do_horizonte(escolhida, policy, hoje=hoje):
            return hoje
        return escolhida

    def _querystring_sem(self, chave):
        """Return the current querystring without one key.

        As abas trocam apenas o tipo: data, pessoas, filtros e a busca com IA
        precisam sobreviver ao clique, senão o usuário refaz tudo a cada aba.

        Args:
            chave: O parâmetro a remover.

        Returns:
            str: A querystring restante, já com ``&`` no fim quando não vazia.
        """
        parametros = self.request.GET.copy()
        parametros.pop(chave, None)
        codificada = parametros.urlencode()
        return f"{codificada}&" if codificada else ""

    def get_template_names(self):
        """Return the fragment template for HTMX requests.

        O fragmento traz os cartões **e** o resumo da seleção, este último com
        ``hx-swap-oob``: os dois ficam em pontos distantes da página, e sem a
        troca fora de banda o resumo continuaria mostrando o espaço anterior.
        """
        if self.request.headers.get("HX-Request") == "true":
            return ["spaces/_space_list_fragment.html"]
        return [self.template_name]


class SpaceDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a space showing info and availability calendar."""

    model = Space
    template_name = "spaces/space_detail.html"
    context_object_name = "space"

    def get_queryset(self):
        """Prefetch related attributes for the space."""
        return (
            Space.objects.filter(is_active=True)
            .select_related("space_type")
            .prefetch_related("space_attributes__attribute")
        )

    def get_context_data(self, **kwargs):
        """Add availability data and selected date to context."""
        context = super().get_context_data(**kwargs)
        space = self.get_object()

        # Get date from query param or default to today
        date_str = self.request.GET.get("date")
        # timezone.localdate() respeita TIME_ZONE; datetime.date.today() usaria o
        # fuso do sistema operacional (UTC no contêiner) e, das 21h à meia-noite
        # em Goiás, abriria a tela já no dia seguinte.
        hoje = timezone.localdate()
        if date_str:
            try:
                selected_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                selected_date = hoje
        else:
            selected_date = hoje

        policy = BookingPolicy.carregar()
        context["policy"] = policy
        context["selected_date"] = selected_date
        # Os pedaços vêm do incremento configurado. Antes desta fase a tela
        # mostrava a janela inteira como um único botão — num dia vazio, o
        # literal "00:00 – 00:00".
        slots = gerar_slots(space, selected_date, policy)

        # A duração é escolhida *antes* do horário: assim cada botão do grid
        # significa "reservar das 9h às 10h30", e não "reservar os trinta
        # minutos das 9h". Quem não escolhe está pedindo o menor compromisso
        # possível, que é a duração mínima da política.
        duracao = duracao_valida(self.request.GET.get("duration"), policy) or (
            policy.min_duration_minutes
        )
        context["duracao_escolhida"] = duracao
        context["duracoes_oferecidas"] = duracoes_oferecidas(policy)
        context["rotulo_da_duracao"] = rotulo_de_duracao(duracao)

        slots = marcar_cabimento(slots, duracao)
        context["slots"] = slots
        context["grupos_de_slots"] = agrupar_por_periodo(slots)
        context["tem_horario_livre"] = any(slot["disponivel"] for slot in slots)
        context["cabe_algum"] = any(slot["cabe"] for slot in slots)
        # A legenda só menciona "não cabe" quando o estado existe na tela.
        # Com a duração mínima ele nunca acontece, e explicar um estado
        # ausente é ruído.
        context["tem_nao_cabe"] = any(slot["disponivel"] and not slot["cabe"] for slot in slots)
        context["hoje"] = hoje
        context["data_maxima"] = hoje + datetime.timedelta(days=policy.horizon_days)
        context["is_htmx"] = self.request.headers.get("HX-Request") == "true"

        context.update(self._contexto_do_horario_pedido(space, selected_date, slots, policy))

        # Etapa 2 do fluxo de reserva: data e horário.
        context.update(contexto_do_stepper(2, FLUXO_V2))
        return context

    def _contexto_do_horario_pedido(self, space, date, slots, policy):
        """Return what the screen needs when the user arrived asking for a time.

        Quem chega do passo 1 com um horário em mente precisa de uma de duas
        respostas: "é esse aqui" ou "esse não dá, mas estes sim". Dizer apenas
        "indisponível" devolveria o problema para o usuário.

        Args:
            space: O espaço exibido.
            date: O dia selecionado.
            slots: Os pedaços do dia.
            policy: A política vigente.

        Returns:
            dict: Contexto com o horário pedido, se cabe, e as alternativas.
        """
        vazio = {
            "horario_pedido": None,
            "duracao_pedida": None,
            "horario_disponivel": None,
            "horarios_alternativos": [],
            "espacos_alternativos": [],
        }

        bruto = self.request.GET.get("start", "").strip()
        if not bruto:
            return vazio
        try:
            pedido = datetime.datetime.strptime(bruto, "%H:%M").time()
        except ValueError:
            return vazio
        if not (policy.opening_time <= pedido < policy.closing_time):
            return vazio

        duracao = duracao_valida(self.request.GET.get("duration"), policy)

        alvo = timezone.make_aware(datetime.datetime.combine(date, pedido))
        fim = alvo + datetime.timedelta(minutes=duracao or policy.min_duration_minutes)
        tocados = [slot for slot in slots if slot["inicio"] < fim and slot["fim"] > alvo]
        disponivel = bool(tocados) and all(slot["disponivel"] for slot in tocados)

        contexto = dict(vazio)
        contexto["horario_pedido"] = pedido
        contexto["duracao_pedida"] = duracao
        contexto["horario_disponivel"] = disponivel
        if not disponivel:
            contexto["horarios_alternativos"] = horarios_proximos(slots, alvo)
            contexto["espacos_alternativos"] = espacos_equivalentes(
                space, date, pedido, policy, duracao_minutos=duracao
            )
        return contexto

    def get_template_names(self):
        """Return partial template for HTMX requests."""
        if self.request.headers.get("HX-Request") == "true":
            return ["spaces/_availability.html"]
        return [self.template_name]
