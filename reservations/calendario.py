"""Build the month, week and day grids of the calendar screen.

Como :mod:`reservations.availability`, este módulo **lê** reservas — não decide
nada sobre elas. A diferença é o recorte: ali a pergunta é "o que ainda dá para
reservar neste espaço"; aqui é "o que já está marcado no meu tempo".

A regra que estrutura o arquivo inteiro é a privacidade, e o pacote V2 não a
deixa em aberto:

    "O calendário e listagens compartilhadas não devem expor automaticamente
    assunto/observações de reservas de terceiros."

Há duas maneiras de obedecer. A comum é buscar tudo e esconder no template. A
segura é **não buscar**: as reservas alheias saem do banco por um ``values()``
que não inclui ``title``, ``notes`` nem ``user``. O assunto de terceiro não
chega ao processo, então não há template, fragmento HTMX, mensagem de erro ou
página de debug capaz de vazá-lo. É por isso que existem dois queryset
separados aqui embaixo, e não um só com um ``if`` na hora de imprimir.

Pela mesma razão a entrada de terceiro não carrega ``pk``: não há tela dela
para o usuário abrir, e um identificador guardado no HTML é um convite a
construir uma URL que o servidor teria de recusar depois.
"""

import calendar
import datetime

from django.utils import timezone

from accounts.models import nome_de_exibicao
from reservations.availability import proximo_dia_aberto
from reservations.enums import ACTIVE_RESERVATION_STATUSES, ReservationStatus
from reservations.models import BookingPolicy, MaintenanceBlock, Reservation
from spaces.models import Space

#: As três visões previstas no pacote V2.
VISTA_MES = "mes"
VISTA_SEMANA = "semana"
VISTA_DIA = "dia"
VISTAS = (VISTA_MES, VISTA_SEMANA, VISTA_DIA)

ROTULOS_DE_VISTA = {
    VISTA_MES: "Mês",
    VISTA_SEMANA: "Semana",
    VISTA_DIA: "Dia",
}

#: O que o usuário vê no lugar do assunto de outra pessoa. O pacote V2 nomeia
#: esta palavra; ela não é uma escolha de redação desta camada.
OCUPADO = "Ocupado"
MANUTENCAO = "Manutenção"

TIPO_RESERVA = "reserva"
TIPO_MANUTENCAO = "manutencao"

#: A semana começa no domingo, como nos calendários de parede brasileiros.
PRIMEIRO_DIA_DA_SEMANA = 6

DIAS_CURTOS = ("Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb")
DIAS_LONGOS = (
    "domingo",
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
)
MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def normalizar_vista(bruto):
    """Return a valid view name for whatever came on the querystring.

    Args:
        bruto: O valor recebido, possivelmente ausente ou inventado.

    Returns:
        str: Uma das constantes ``VISTA_*``; ``VISTA_MES`` no que não for.
    """
    if bruto in VISTAS:
        return bruto
    return VISTA_MES


def data_pedida(bruto, *, hoje=None):
    """Return the date the user asked for, falling back to today.

    Uma data inválida não é erro do usuário digitando: é URL editada ou link
    velho. Cair em "hoje" mostra um calendário verdadeiro; uma página de erro
    não mostraria nada.

    Args:
        bruto: Texto ``YYYY-MM-DD`` ou ausente.
        hoje: O dia de referência; ``timezone.localdate()`` quando omitido.

    Returns:
        datetime.date: A data pedida, ou hoje.
    """
    hoje = timezone.localdate() if hoje is None else hoje
    if not bruto:
        return hoje
    try:
        return datetime.date.fromisoformat(bruto)
    except (TypeError, ValueError):
        return hoje


def _inicio_da_semana(dia):
    """Return the Sunday that opens the week containing ``dia``."""
    # ``weekday()`` conta a partir de segunda; domingo é 6. Somando 1 e tirando
    # o resto por 7, domingo vira 0 e a conta fica direta.
    return dia - datetime.timedelta(days=(dia.weekday() + 1) % 7)


def dias_da_grade(vista, dia):
    """Return every date the grid of a view displays, in order.

    A grade do mês inclui os dias vizinhos que completam as semanas — eles
    aparecem na tela, então precisam entrar na busca; senão a primeira linha do
    mês mostraria dias vazios que não estão vazios.

    Args:
        vista: Uma das constantes ``VISTA_*``.
        dia: O dia de referência.

    Returns:
        list[datetime.date]: Os dias exibidos.
    """
    if vista == VISTA_DIA:
        return [dia]
    if vista == VISTA_SEMANA:
        primeiro = _inicio_da_semana(dia)
        return [primeiro + datetime.timedelta(days=i) for i in range(7)]
    grade = calendar.Calendar(firstweekday=PRIMEIRO_DIA_DA_SEMANA)
    return list(grade.itermonthdates(dia.year, dia.month))


def _limites(dias):
    """Return the aware datetimes bounding a list of dates, in local time."""
    inicio = timezone.make_aware(datetime.datetime.combine(dias[0], datetime.time.min))
    fim = timezone.make_aware(
        datetime.datetime.combine(dias[-1] + datetime.timedelta(days=1), datetime.time.min)
    )
    return inicio, fim


def _minhas_reservas(user, inicio, fim):
    """Return the viewer's own reservations touching the window, in full.

    Args:
        user: Quem está olhando.
        inicio: Início da janela.
        fim: Fim da janela.

    Returns:
        list[dict]: Entradas prontas para a grade.
    """
    reservas = (
        Reservation.objects.filter(
            user=user,
            status__in=ACTIVE_RESERVATION_STATUSES,
            start_time__lt=fim,
            end_time__gt=inicio,
        )
        .select_related("space")
        .order_by("start_time")
    )
    return [
        {
            "pk": reserva.pk,
            "tipo": TIPO_RESERVA,
            "propria": True,
            "inicio": timezone.localtime(reserva.start_time),
            "fim": timezone.localtime(reserva.end_time),
            "espaco": reserva.space.name,
            "espaco_id": reserva.space_id,
            "rotulo": reserva.title or reserva.space.name,
            "status": reserva.status,
        }
        for reserva in reservas
    ]


def _ocupacao_de_terceiros(user, inicio, fim):
    """Return other people's bookings as anonymous busy blocks.

    O ``values()`` é a proteção, e é deliberadamente curto: sem ``title``, sem
    ``notes``, sem ``user``. O que não é buscado não vaza.

    Args:
        user: Quem está olhando — suas próprias reservas ficam de fora, porque
            já vieram completas pelo outro caminho.
        inicio: Início da janela.
        fim: Fim da janela.

    Returns:
        list[dict]: Entradas anônimas prontas para a grade.
    """
    reservas = (
        Reservation.objects.filter(
            status__in=ACTIVE_RESERVATION_STATUSES,
            start_time__lt=fim,
            end_time__gt=inicio,
        )
        .exclude(user=user)
        .values("start_time", "end_time", "space_id", "space__name")
    )
    entradas = [
        {
            "pk": None,
            "tipo": TIPO_RESERVA,
            "propria": False,
            "inicio": timezone.localtime(reserva["start_time"]),
            "fim": timezone.localtime(reserva["end_time"]),
            "espaco": reserva["space__name"],
            "espaco_id": reserva["space_id"],
            "rotulo": OCUPADO,
            "status": None,
        }
        for reserva in reservas
    ]

    bloqueios = MaintenanceBlock.objects.filter(
        start_time__lt=fim,
        end_time__gt=inicio,
    ).values("start_time", "end_time", "space_id", "space__name")
    entradas += [
        {
            "pk": None,
            "tipo": TIPO_MANUTENCAO,
            "propria": False,
            "inicio": timezone.localtime(bloqueio["start_time"]),
            "fim": timezone.localtime(bloqueio["end_time"]),
            "espaco": bloqueio["space__name"],
            "espaco_id": bloqueio["space_id"],
            "rotulo": MANUTENCAO,
            "status": None,
        }
        for bloqueio in bloqueios
    ]
    return entradas


def espacos_filtrados(*, espaco=None, tipo=None, local=None):
    """Return the spaces a general-calendar filter selects.

    O filtro é montado sobre ``Space`` e não sobre ``Reservation`` de propósito:
    é o mesmo conjunto de espaços que precisa valer para as reservas **e** para
    as manutenções. Aplicá-lo duas vezes, uma em cada consulta, é como as duas
    metades da tela acabam discordando.

    Espaços inativos continuam na lista: um espaço desativado ontem pode ter
    reservas marcadas para amanhã, e escondê-las faria a administração
    descobrir o problema pela reclamação de quem apareceu na porta.

    Args:
        espaco: PK de um espaço, ou vazio.
        tipo: PK de um tipo de espaço, ou vazio.
        local: Localização exata, ou vazio.

    Returns:
        QuerySet: Os espaços selecionados.
    """
    espacos = Space.objects.all()
    if espaco:
        espacos = espacos.filter(pk=espaco)
    if tipo:
        espacos = espacos.filter(space_type_id=tipo)
    if local:
        espacos = espacos.filter(location=local)
    return espacos


def _reservas_da_administracao(inicio, fim, espacos):
    """Return every reservation in the window, with the detail staff may see.

    Aqui o assunto e o nome de quem reservou **aparecem** — e isso não
    contradiz a privacidade do calendário do usuário. O pacote V2 separa os
    dois casos na mesma frase: "demais usuários veem ``Ocupado``"; "staff
    autorizado vê conforme necessidade operacional". Quem administra a agenda
    precisa saber a quem ligar quando a sala cai.

    As observações continuam fora: elas são o campo onde as pessoas escrevem
    coisas que não têm relação com a operação da sala, e nenhuma tela de
    calendário precisa delas.

    Args:
        inicio: Início da janela.
        fim: Fim da janela.
        espacos: QuerySet de espaços considerados.

    Returns:
        list[dict]: Entradas prontas para a grade.
    """
    reservas = (
        Reservation.objects.filter(
            status__in=ACTIVE_RESERVATION_STATUSES,
            start_time__lt=fim,
            end_time__gt=inicio,
            space__in=espacos,
        )
        .select_related("space", "user")
        .order_by("start_time")
    )
    return [
        {
            "pk": reserva.pk,
            "tipo": TIPO_RESERVA,
            "propria": False,
            "administrativa": True,
            "inicio": timezone.localtime(reserva.start_time),
            "fim": timezone.localtime(reserva.end_time),
            "espaco": reserva.space.name,
            "espaco_id": reserva.space_id,
            # No Calendário Geral o cartão é encabeçado pelo espaço — é a
            # pergunta de quem administra ocupação. O assunto vem separado e
            # pode estar vazio: reservas antigas não têm um, e repetir o nome
            # da sala no lugar dele imprimia a mesma linha duas vezes.
            "rotulo": reserva.space.name,
            "assunto": reserva.title,
            "pessoa": nome_de_exibicao(reserva.user),
            "status": reserva.status,
            "situacao": ReservationStatus(reserva.status).label,
        }
        for reserva in reservas
    ]


def _manutencoes_da_administracao(inicio, fim, espacos):
    """Return the maintenance blocks in the window, with their reason.

    O motivo aparece porque é texto que a própria administração escreveu, na
    tela de manutenção, para a própria administração ler. É o oposto do assunto
    de uma reserva alheia.

    Args:
        inicio: Início da janela.
        fim: Fim da janela.
        espacos: QuerySet de espaços considerados.

    Returns:
        list[dict]: Entradas prontas para a grade.
    """
    bloqueios = (
        MaintenanceBlock.objects.filter(
            start_time__lt=fim,
            end_time__gt=inicio,
            space__in=espacos,
        )
        .select_related("space")
        .order_by("start_time")
    )
    return [
        {
            "pk": bloqueio.pk,
            "tipo": TIPO_MANUTENCAO,
            "propria": False,
            "administrativa": True,
            "inicio": timezone.localtime(bloqueio.start_time),
            "fim": timezone.localtime(bloqueio.end_time),
            "espaco": bloqueio.space.name,
            "espaco_id": bloqueio.space_id,
            "rotulo": MANUTENCAO,
            "assunto": "",
            "pessoa": "",
            "motivo": bloqueio.reason,
            "status": None,
            "situacao": "",
        }
        for bloqueio in bloqueios
    ]


def montar_calendario_geral(
    vista, dia, *, espaco=None, tipo=None, local=None, policy=None, hoje=None
):
    """Assemble the administration's general calendar.

    Args:
        vista: Uma das constantes ``VISTA_*``.
        dia: O dia de referência.
        espaco: PK de um espaço, para filtrar.
        tipo: PK de um tipo de espaço, para filtrar.
        local: Localização exata, para filtrar.
        policy: A política vigente; carregada do banco quando omitida.
        hoje: O dia de hoje; ``timezone.localdate()`` quando omitido.

    Returns:
        dict: Contexto pronto para o template, com ``total_reservas`` e
        ``total_manutencoes`` separados — são duas coisas diferentes para quem
        administra, e somá-las esconderia qual das duas cresceu.
    """
    policy = policy or BookingPolicy.carregar()
    hoje = timezone.localdate() if hoje is None else hoje

    dias = dias_da_grade(vista, dia)
    inicio, fim = _limites(dias)
    espacos = espacos_filtrados(espaco=espaco, tipo=tipo, local=local)

    reservas = _reservas_da_administracao(inicio, fim, espacos)
    manutencoes = _manutencoes_da_administracao(inicio, fim, espacos)

    contexto = _montar(reservas + manutencoes, vista, dia, dias, policy=policy, hoje=hoje)
    contexto["total_reservas"] = len(reservas)
    contexto["total_manutencoes"] = len(manutencoes)
    return contexto


def _distribuir(entradas, dias):
    """Return the entries of each displayed date, keyed by date.

    Uma reserva que atravessa a meia-noite aparece nos dois dias — é o que ela
    faz na vida real, e omiti-la no segundo dia esconderia ocupação verdadeira.

    Args:
        entradas: Todas as entradas da janela.
        dias: Os dias exibidos.

    Returns:
        dict: ``{data: [entradas ordenadas]}``.
    """
    por_dia = {dia: [] for dia in dias}
    for entrada in entradas:
        dia = entrada["inicio"].date()
        ultimo = entrada["fim"].date()
        # O fim exatamente na meia-noite pertence ao dia anterior: uma reserva
        # que termina às 00:00 não ocupa nada do dia que começa ali.
        if entrada["fim"].time() == datetime.time.min and ultimo > dia:
            ultimo -= datetime.timedelta(days=1)
        while dia <= ultimo:
            if dia in por_dia:
                por_dia[dia].append(entrada)
            dia += datetime.timedelta(days=1)
    for lista in por_dia.values():
        lista.sort(key=lambda entrada: (entrada["inicio"], entrada["espaco"]))
    return por_dia


def _celula(data, entradas, *, hoje, mes_de_referencia, policy):
    """Return one day cell of the grid."""
    return {
        "data": data,
        "entradas": entradas,
        "quantidade": len(entradas),
        "hoje": data == hoje,
        # Um domingo vazio e uma terça vazia não são a mesma coisa: numa dá para
        # reservar, na outra o prédio não abre. Sem esta marca a grade mostra as
        # duas iguais, e quem olha conclui que o domingo está livre.
        "fechado": not policy.abre_em(data),
        "no_mes": data.month == mes_de_referencia,
        "fim_de_semana": data.weekday() >= 5,
        "dia_curto": DIAS_CURTOS[(data.weekday() + 1) % 7],
        "dia_longo": DIAS_LONGOS[(data.weekday() + 1) % 7],
    }


def _recortar(entrada, data):
    """Return the entry as it is lived on one specific day.

    Uma reserva que começa às 22h e vai até as 2h da manhã seguinte aparece em
    dois dias, e em cada um deles ocupa um pedaço diferente. Sem este recorte, o
    dia de amanhã acharia que algo começa às 22h — e a grade de horas do dia
    seria montada em volta de uma hora que não existe ali.

    Args:
        entrada: A entrada original.
        data: O dia sendo exibido.

    Returns:
        dict: Uma cópia com ``inicio_no_dia``, ``fim_no_dia`` e as marcas
        ``vem_de_ontem`` / ``segue_amanha``.
    """
    abertura = timezone.make_aware(datetime.datetime.combine(data, datetime.time.min))
    virada = abertura + datetime.timedelta(days=1)
    recorte = dict(entrada)
    recorte["vem_de_ontem"] = entrada["inicio"] < abertura
    recorte["segue_amanha"] = entrada["fim"] > virada
    recorte["inicio_no_dia"] = max(entrada["inicio"], abertura)
    recorte["fim_no_dia"] = min(entrada["fim"], virada)
    return recorte


def _faixa_de_horas(entradas, policy):
    """Return the hours the day view must show.

    Começa na janela de funcionamento, mas estica para caber o que estiver fora
    dela: uma reserva antiga feita sob outra política continua existindo, e um
    calendário que a esconde por causa do horário atual mente sobre o dia.

    Args:
        entradas: As entradas do dia, já recortadas por :func:`_recortar`.
        policy: A política vigente.

    Returns:
        list[int]: As horas cheias exibidas, em ordem.
    """
    primeira = policy.opening_time.hour
    ultima = policy.closing_time.hour
    if policy.closing_time.minute:
        ultima += 1
    for entrada in entradas:
        primeira = min(primeira, entrada["inicio_no_dia"].hour)
        fim = entrada["fim_no_dia"]
        # Fim exatamente na virada: 24 não é hora exibível, e a linha das 23
        # já cobre esse pedaço.
        if fim.date() > entrada["inicio_no_dia"].date():
            ultima = 24
        else:
            ultima = max(ultima, fim.hour + (1 if fim.minute else 0))
    ultima = max(ultima, primeira + 1)
    return list(range(primeira, min(ultima, 24)))


def _titulo(vista, dia, dias):
    """Return the heading that names what is on screen."""
    if vista == VISTA_DIA:
        nome_do_dia = DIAS_LONGOS[(dia.weekday() + 1) % 7].capitalize()
        return f"{nome_do_dia}, {dia.day} de {MESES[dia.month - 1]}"
    if vista == VISTA_SEMANA:
        primeiro, ultimo = dias[0], dias[-1]
        if primeiro.month == ultimo.month:
            return f"{primeiro.day} a {ultimo.day} de {MESES[primeiro.month - 1]}"
        return (
            f"{primeiro.day} de {MESES[primeiro.month - 1]} a "
            f"{ultimo.day} de {MESES[ultimo.month - 1]}"
        )
    return f"{MESES[dia.month - 1].capitalize()} de {dia.year}"


def _passo(vista, dia):
    """Return the previous and next reference dates for the navigation."""
    if vista == VISTA_DIA:
        return dia - datetime.timedelta(days=1), dia + datetime.timedelta(days=1)
    if vista == VISTA_SEMANA:
        return dia - datetime.timedelta(days=7), dia + datetime.timedelta(days=7)
    primeiro = dia.replace(day=1)
    anterior = primeiro - datetime.timedelta(days=1)
    ultimo_dia = calendar.monthrange(dia.year, dia.month)[1]
    proximo = primeiro.replace(day=ultimo_dia) + datetime.timedelta(days=1)
    return anterior.replace(day=1), proximo


def _montar(entradas, vista, dia, dias, *, policy, hoje):
    """Turn a flat list of entries into the grid the templates read.

    Esta parte não sabe **de quem** são as entradas, e é por isso que serve aos
    dois calendários: o do usuário, onde as alheias já chegaram anônimas, e o
    Calendário Geral do admin, onde chegam completas. A decisão de privacidade
    é tomada antes, na busca — aqui já é tarde para tomá-la, e por isso ela não
    é tomada aqui.

    Args:
        entradas: As entradas já montadas.
        vista: Uma das constantes ``VISTA_*``.
        dia: O dia de referência.
        dias: Os dias exibidos, como devolvidos por :func:`dias_da_grade`.
        policy: A política vigente.
        hoje: O dia de hoje.

    Returns:
        dict: Contexto pronto para o template.
    """
    por_dia = _distribuir(entradas, dias)
    anterior, proximo = _passo(vista, dia)

    celulas = [
        _celula(data, por_dia[data], hoje=hoje, mes_de_referencia=dia.month, policy=policy)
        for data in dias
    ]

    contexto = {
        "vista": vista,
        "vistas": [
            {"chave": chave, "rotulo": ROTULOS_DE_VISTA[chave], "atual": chave == vista}
            for chave in VISTAS
        ],
        "dia": dia,
        "hoje": hoje,
        "titulo": _titulo(vista, dia, dias),
        "anterior": anterior,
        "proximo": proximo,
        "dias_da_semana": [
            {"curto": DIAS_CURTOS[i], "longo": DIAS_LONGOS[i].capitalize()} for i in range(7)
        ],
        "total": len(entradas),
        "celulas": celulas,
        # Qual partial desenha uma entrada. O calendário do usuário e o
        # Calendário Geral mostram coisas diferentes dentro da mesma grade;
        # trocar o partial é mais honesto do que encher o mesmo arquivo de
        # ``{% if e_admin %}``, que é como uma tela acaba vazando na outra.
        "modelo_de_entrada": "reservations/_calendar_entry.html",
    }

    if vista == VISTA_MES:
        contexto["semanas"] = [celulas[i : i + 7] for i in range(0, len(celulas), 7)]
    elif vista == VISTA_DIA:
        celula = celulas[0]
        recortadas = [_recortar(entrada, dia) for entrada in celula["entradas"]]
        celula = {**celula, "entradas": recortadas}
        contexto["celula"] = celula
        contexto["fechado"] = celula["fechado"]
        if celula["fechado"]:
            contexto["proximo_aberto"] = proximo_dia_aberto(dia, policy)
        contexto["horas"] = [
            {
                "hora": hora,
                "rotulo": f"{hora:02d}:00",
                "entradas": [
                    entrada for entrada in recortadas if entrada["inicio_no_dia"].hour == hora
                ],
            }
            for hora in _faixa_de_horas(recortadas, policy)
        ]
    return contexto


def montar_calendario(user, vista, dia, *, incluir_ocupacao=False, policy=None, hoje=None):
    """Assemble the personal calendar of one user.

    Args:
        user: Quem está olhando.
        vista: Uma das constantes ``VISTA_*``.
        dia: O dia de referência.
        incluir_ocupacao: Quando verdadeiro, acrescenta a ocupação de terceiros
            — sempre anônima — e as manutenções.
        policy: A política vigente; carregada do banco quando omitida.
        hoje: O dia de hoje; ``timezone.localdate()`` quando omitido.

    Returns:
        dict: Contexto pronto para o template.
    """
    policy = policy or BookingPolicy.carregar()
    hoje = timezone.localdate() if hoje is None else hoje

    dias = dias_da_grade(vista, dia)
    inicio, fim = _limites(dias)

    entradas = _minhas_reservas(user, inicio, fim)
    proprias = len(entradas)
    if incluir_ocupacao:
        entradas += _ocupacao_de_terceiros(user, inicio, fim)

    contexto = _montar(entradas, vista, dia, dias, policy=policy, hoje=hoje)
    contexto["incluir_ocupacao"] = incluir_ocupacao
    contexto["total_proprias"] = proprias
    return contexto
