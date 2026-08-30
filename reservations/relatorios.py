"""Derive the administration's report metrics from what actually happened.

Como :mod:`reservations.availability` e :mod:`reservations.calendario`, este
módulo só **lê**. A diferença é a pergunta: ali é "o que dá para reservar" e "o
que está marcado"; aqui é "o que este prédio andou fazendo".

Três decisões estruturam o arquivo, e as três existem porque a alternativa
produz número errado com cara de certo:

1. **Ocupação é minuto dentro da janela, não minuto de reserva.** Uma reserva
   das 7h às 19h sob expediente de 8h–18h ocupa dez horas, não doze — senão a
   taxa passa de 100% e ninguém entende por quê. O recorte vale para os três
   lados: a janela do dia, os dias em que o prédio abre e as bordas do período.

2. **Contagem e duração são coisas diferentes.** Cancelamento e no-show são
   eventos: contam-se. Ocupação e manutenção são tempo: somam-se em minutos.
   Misturar as duas é como um relatório passa a dizer que um espaço com uma
   reserva de oito horas é menos usado que outro com três de meia hora.

3. **O que não é medido é dito.** Duas métricas dependem de coisas que o
   sistema pode não estar fazendo — o no-show depende de uma rotina que vem
   desligada, e a subutilização depende de um campo que reservas antigas não
   têm. As duas devolvem, junto com o número, o que sustenta esse número. Um
   "0 no-shows" que na verdade quer dizer "ninguém está medindo" é pior do que
   não mostrar nada.
"""

import datetime
import statistics
from collections import defaultdict

from django.db.models import Count

from reservations.enums import ReservationStatus
from reservations.models import BookingPolicy, MaintenanceBlock, Reservation
from services.models import ReservationServiceRequest
from spaces.models import Space

#: Situações que ocuparam ou vão ocupar o espaço de fato.
#:
#: ``COMPLETED`` entra por causa do histórico: nenhum caminho da aplicação
#: grava esse status hoje — uma reserva que aconteceu e terminou continua
#: ``CONFIRMED`` para sempre —, mas há linhas assim na base semeada, e
#: descartá-las faria o relatório perder ocupação verdadeira.
#:
#: ``NO_SHOW`` fica de fora de propósito: o espaço esteve reservado, mas não
#: foi usado. Contá-lo como ocupação transformaria desperdício em produtividade,
#: que é exatamente o que a métrica existe para revelar.
STATUS_QUE_OCUPAM = (
    ReservationStatus.CONFIRMED,
    ReservationStatus.CHECKED_IN,
    ReservationStatus.COMPLETED,
)

DIAS_DA_SEMANA_CURTOS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


def _minutos(inicio, fim):
    """Return the whole minutes between two datetimes, never negative."""
    return max(0.0, (fim - inicio).total_seconds() / 60)


def janelas_abertas(inicio, fim, policy=None):
    """Return the operating windows inside a period, one per open day.

    É a base do denominador de toda métrica de tempo. Um dia em que o prédio
    não abre simplesmente não produz janela — nem no numerador, nem no
    denominador —, e é isso que impede a ocupação de parecer baixa só porque o
    período tinha domingos.

    Args:
        inicio: Início do período, ciente do fuso.
        fim: Fim do período, ciente do fuso (exclusivo).
        policy: A política vigente; carregada do banco quando omitida.

    Returns:
        list[tuple]: Pares ``(início, fim)`` já recortados ao período.
    """
    from django.utils import timezone

    policy = policy or BookingPolicy.carregar()
    janelas = []
    dia = timezone.localtime(inicio).date()
    ultimo = timezone.localtime(fim - datetime.timedelta(microseconds=1)).date()
    while dia <= ultimo:
        if policy.abre_em(dia):
            abre = timezone.make_aware(datetime.datetime.combine(dia, policy.opening_time))
            fecha = timezone.make_aware(datetime.datetime.combine(dia, policy.closing_time))
            recorte_inicio = max(abre, inicio)
            recorte_fim = min(fecha, fim)
            if recorte_fim > recorte_inicio:
                janelas.append((recorte_inicio, recorte_fim))
        dia += datetime.timedelta(days=1)
    return janelas


def minutos_de_expediente(inicio, fim, policy=None):
    """Return how many minutes one space could have been used in a period.

    Args:
        inicio: Início do período.
        fim: Fim do período.
        policy: A política vigente; carregada do banco quando omitida.

    Returns:
        float: Minutos de expediente no período, por espaço.
    """
    return sum(_minutos(abre, fecha) for abre, fecha in janelas_abertas(inicio, fim, policy))


def _minutos_dentro_das_janelas(intervalos, janelas):
    """Return how many minutes of some intervals fall inside the open windows.

    O recorte é o coração da ocupação: sem ele, uma reserva que começa antes de
    o prédio abrir soma minutos que o denominador não tem, e a taxa estoura os
    100%.

    Args:
        intervalos: Iterável de pares ``(início, fim)``.
        janelas: As janelas de funcionamento, como devolvidas por
            :func:`janelas_abertas`.

    Returns:
        float: Total de minutos na interseção.
    """
    total = 0.0
    for comeco, termino in intervalos:
        for abre, fecha in janelas:
            if comeco < fecha and termino > abre:
                total += _minutos(max(comeco, abre), min(termino, fecha))
    return total


def ocupacao_por_espaco(inicio, fim, policy=None, *, espacos=None):
    """Return how much of the available time each space was booked for.

    Args:
        inicio: Início do período.
        fim: Fim do período.
        policy: A política vigente; carregada do banco quando omitida.
        espacos: Espaços considerados; todos, quando omitido. Inativos entram:
            um espaço desativado ontem ocupou tempo real até ontem, e omiti-lo
            faria o total do período encolher sem explicação.

    Returns:
        list[dict]: Um item por espaço, com ``espaco``, ``minutos_ocupados``,
        ``minutos_disponiveis``, ``taxa`` (0–1) e ``reservas``, ordenado da
        maior taxa para a menor.
    """
    policy = policy or BookingPolicy.carregar()
    janelas = janelas_abertas(inicio, fim, policy)
    disponiveis = sum(_minutos(abre, fecha) for abre, fecha in janelas)
    espacos = list(Space.objects.all() if espacos is None else espacos)

    reservas = Reservation.objects.filter(
        status__in=STATUS_QUE_OCUPAM,
        start_time__lt=fim,
        end_time__gt=inicio,
        space__in=espacos,
    ).values_list("space_id", "start_time", "end_time")

    por_espaco = defaultdict(list)
    for space_id, comeco, termino in reservas:
        por_espaco[space_id].append((comeco, termino))

    linhas = []
    for espaco in espacos:
        intervalos = por_espaco.get(espaco.pk, [])
        ocupados = _minutos_dentro_das_janelas(intervalos, janelas)
        # ``reservas`` conta só as que entraram nos minutos. Contar todas as que
        # tocam o período faria a coluna discordar da coluna do lado: um espaço
        # com quatro reservas de fim de semana apareceria com "4 reservas" e
        # zero minuto, e quem dividisse um pelo outro concluiria qualquer coisa.
        contadas = sum(
            1 for intervalo in intervalos if _minutos_dentro_das_janelas([intervalo], janelas)
        )
        linhas.append(
            {
                "espaco": espaco,
                "minutos_ocupados": ocupados,
                "minutos_disponiveis": disponiveis,
                "taxa": (ocupados / disponiveis) if disponiveis else 0.0,
                "reservas": contadas,
            }
        )
    linhas.sort(key=lambda linha: (-linha["taxa"], linha["espaco"].name))
    return linhas


def picos(inicio, fim, policy=None):
    """Return when the building is busiest, by hour and by weekday.

    Conta **reservas sobrepostas** a cada hora, e não reservas que começam
    naquela hora: uma reunião das 9h às 12h ocupa três horas do prédio, e
    contá-la só nas 9h faria o meio da manhã parecer vazio.

    Args:
        inicio: Início do período.
        fim: Fim do período.
        policy: A política vigente; carregada do banco quando omitida.

    Returns:
        dict: ``por_hora`` (lista de ``{hora, rotulo, reservas}`` cobrindo a
        janela de funcionamento) e ``por_dia_da_semana`` (lista de
        ``{dia, rotulo, reservas}``, só com os dias em que o prédio abre).
    """
    from django.utils import timezone

    policy = policy or BookingPolicy.carregar()
    reservas = Reservation.objects.filter(
        status__in=STATUS_QUE_OCUPAM,
        start_time__lt=fim,
        end_time__gt=inicio,
    ).values_list("start_time", "end_time")

    horas = defaultdict(int)
    dias = defaultdict(int)
    for comeco, termino in reservas:
        # O recorte não precisa de guarda contra intervalo vazio: a consulta já
        # exigiu sobreposição com o período, e a reserva tem fim depois do
        # início por constraint do banco.
        comeco = max(timezone.localtime(comeco), timezone.localtime(inicio))
        termino = min(timezone.localtime(termino), timezone.localtime(fim))
        dias[comeco.weekday()] += 1
        # Cada hora cheia tocada pela reserva recebe um ponto.
        cursor = comeco.replace(minute=0, second=0, microsecond=0)
        while cursor < termino:
            if policy.abre_em(cursor.date()):
                horas[cursor.hour] += 1
            cursor += datetime.timedelta(hours=1)

    # A faixa começa na abertura e vai até o fechamento, mas estica para caber
    # o que estiver fora dela: reservas antigas, feitas sob outra política,
    # continuam sendo horas de uso do prédio, e escondê-las faria o pico
    # aparecer no lugar errado.
    primeira = min(policy.opening_time.hour, min(horas, default=policy.opening_time.hour))
    # ``ultima`` é exclusiva: fechando às 18h, a última linha é a das 17h, que
    # é o pedaço 17–18. O ``+ 1`` só vale para hora com reserva; aplicá-lo ao
    # próprio fechamento acrescentaria uma linha 18:00 que não existe.
    fechamento = policy.closing_time.hour + (1 if policy.closing_time.minute else 0)
    ultima = max(fechamento, (max(horas) + 1) if horas else fechamento)
    faixa = range(primeira, ultima)
    return {
        "por_hora": [
            {"hora": hora, "rotulo": f"{hora:02d}:00", "reservas": horas.get(hora, 0)}
            for hora in faixa
        ],
        "por_dia_da_semana": [
            {
                "dia": indice,
                "rotulo": DIAS_DA_SEMANA_CURTOS[indice],
                "reservas": dias.get(indice, 0),
            }
            for indice in sorted(policy.dias_abertos())
        ],
    }


def cancelamentos(inicio, fim):
    """Return the cancellation counts of a period, split by which date was used.

    A divisão vem de :meth:`ReservationQuerySet.resumo_de_cancelamentos` e não
    é detalhe de implementação: as duas parcelas respondem a perguntas
    diferentes — quando alguém desistiu, e quanta sala foi liberada — e o
    relatório precisa poder dizer de que o total é feito.

    Args:
        inicio: Início do período.
        fim: Fim do período.

    Returns:
        dict: ``total``, ``por_ocorrencia``, ``sem_data`` e ``taxa`` sobre as
        reservas do período.
    """
    resumo = Reservation.objects.resumo_de_cancelamentos(inicio, fim)
    marcadas = Reservation.objects.filter(start_time__lt=fim, end_time__gt=inicio).count()
    resumo["marcadas_no_periodo"] = marcadas
    resumo["taxa"] = (resumo["total"] / marcadas) if marcadas else 0.0
    return resumo


def no_shows(inicio, fim, policy=None):
    """Return the no-show count of a period, and whether anything measures it.

    O ``regra_ligada`` viaja junto com o número porque sem ele o número mente
    por omissão: com ``release_no_shows`` desligado — que é o padrão —, nada no
    sistema marca no-show, e o relatório mostraria zero como se fosse boa
    notícia. Zero por não haver faltas e zero por não haver medição são
    resultados opostos.

    Args:
        inicio: Início do período.
        fim: Fim do período.
        policy: A política vigente; carregada do banco quando omitida.

    Returns:
        dict: ``total``, ``taxa``, ``marcadas_no_periodo`` e ``regra_ligada``.
    """
    policy = policy or BookingPolicy.carregar()
    total = Reservation.objects.filter(
        status=ReservationStatus.NO_SHOW,
        start_time__gte=inicio,
        start_time__lt=fim,
    ).count()
    marcadas = Reservation.objects.filter(start_time__gte=inicio, start_time__lt=fim).count()
    return {
        "total": total,
        "marcadas_no_periodo": marcadas,
        "taxa": (total / marcadas) if marcadas else 0.0,
        "regra_ligada": policy.release_no_shows,
    }


def downtime_de_manutencao(inicio, fim, policy=None):
    """Return how much operating time each space lost to maintenance.

    Recortado pela janela como a ocupação: um bloqueio da meia-noite às 6h não
    tira nada do expediente, e contá-lo como downtime faria a manutenção
    noturna — que é a bem planejada — parecer o pior problema do prédio.

    Args:
        inicio: Início do período.
        fim: Fim do período.
        policy: A política vigente; carregada do banco quando omitida.

    Returns:
        list[dict]: ``espaco``, ``minutos``, ``taxa`` e ``bloqueios``, ordenado
        do maior downtime para o menor, sem os espaços que não pararam.
    """
    policy = policy or BookingPolicy.carregar()
    janelas = janelas_abertas(inicio, fim, policy)
    disponiveis = sum(_minutos(abre, fecha) for abre, fecha in janelas)

    bloqueios = (
        MaintenanceBlock.objects.filter(start_time__lt=fim, end_time__gt=inicio)
        .select_related("space")
        .values_list("space_id", "space__name", "start_time", "end_time")
    )
    por_espaco = defaultdict(list)
    nomes = {}
    for space_id, nome, comeco, termino in bloqueios:
        por_espaco[space_id].append((comeco, termino))
        nomes[space_id] = nome

    linhas = []
    for space_id, intervalos in por_espaco.items():
        minutos = _minutos_dentro_das_janelas(intervalos, janelas)
        if not minutos:
            # Bloqueio inteiramente fora do expediente: real, mas não é
            # downtime. Some da lista em vez de aparecer com zero.
            continue
        linhas.append(
            {
                "espaco": nomes[space_id],
                "espaco_id": space_id,
                "minutos": minutos,
                "taxa": (minutos / disponiveis) if disponiveis else 0.0,
                "bloqueios": len(intervalos),
            }
        )
    linhas.sort(key=lambda linha: (-linha["minutos"], linha["espaco"]))
    return linhas


def servicos(inicio, fim):
    """Return how many service requests each type received, and their outcome.

    Ancorado no horário da reserva, e não em quando o pedido foi feito: a
    pergunta de quem planeja a copa é "quanto café este mês vai precisar", não
    "quantos formulários foram preenchidos".

    Args:
        inicio: Início do período.
        fim: Fim do período.

    Returns:
        list[dict]: ``servico``, ``total`` e ``por_situacao`` (dicionário de
        rótulo para contagem), ordenado do mais pedido para o menos.
    """
    pedidos = (
        ReservationServiceRequest.objects.filter(
            reservation__start_time__lt=fim,
            reservation__end_time__gt=inicio,
        )
        .values("service_type__name", "status")
        .annotate(quantidade=Count("id"))
    )

    agrupado = defaultdict(lambda: {"total": 0, "por_situacao": {}})
    rotulos = dict(ReservationServiceRequest._meta.get_field("status").choices)
    for linha in pedidos:
        nome = linha["service_type__name"]
        agrupado[nome]["total"] += linha["quantidade"]
        rotulo = rotulos.get(linha["status"], linha["status"])
        agrupado[nome]["por_situacao"][rotulo] = linha["quantidade"]

    linhas = [
        {"servico": nome, "total": dados["total"], "por_situacao": dados["por_situacao"]}
        for nome, dados in agrupado.items()
    ]
    linhas.sort(key=lambda linha: (-linha["total"], linha["servico"]))
    return linhas


def antecedencia(inicio, fim):
    """Return how far ahead people book, in hours.

    Devolve média **e** mediana. A média sozinha é enganosa aqui: uma única
    reserva feita com seis meses de antecedência desloca a média de um mês
    inteiro, e quem lê conclui que o prédio se planeja bem. A mediana diz o que
    a maioria das pessoas faz.

    Entram todas as reservas do período, inclusive canceladas e não
    comparecidas: a métrica é sobre **como as pessoas agendam**, e quem
    reservou com um dia de antecedência e depois desistiu agendou com um dia de
    antecedência do mesmo jeito. Filtrar por status responderia outra pergunta.

    Args:
        inicio: Início do período.
        fim: Fim do período.

    Returns:
        dict: ``media_horas``, ``mediana_horas`` e ``amostra``.
    """
    valores = [
        (comeco - criada).total_seconds() / 3600
        for comeco, criada in Reservation.objects.filter(
            start_time__gte=inicio, start_time__lt=fim
        ).values_list("start_time", "created_at")
        # Reservas semeadas podem ter sido criadas depois do próprio início;
        # antecedência negativa não é antecedência, e entraria puxando a média
        # para baixo como se alguém tivesse reservado o passado.
        if comeco >= criada
    ]
    if not valores:
        return {"media_horas": None, "mediana_horas": None, "amostra": 0}
    return {
        "media_horas": statistics.fmean(valores),
        "mediana_horas": statistics.median(valores),
        "amostra": len(valores),
    }


def subutilizacao(inicio, fim):
    """Return how full the booked rooms actually were, where that is known.

    A cobertura viaja junto com o número pelo mesmo motivo do ``regra_ligada``
    do no-show: ``attendee_count`` é opcional e as reservas anteriores à Fase 10
    não têm nenhum. Uma média calculada sobre três reservas de duzentas é um
    número verdadeiro sobre uma amostra que não representa nada, e quem lê
    precisa saber disso antes de decidir desativar uma sala.

    Args:
        inicio: Início do período.
        fim: Fim do período.

    Returns:
        list[dict]: ``espaco``, ``capacidade``, ``media_participantes``,
        ``taxa`` (participantes ÷ capacidade), ``com_informacao`` e ``total``,
        ordenado da menor taxa para a maior — a subutilização vem primeiro.
        Espaços sem nenhuma reserva com participantes informados ficam de fora.
    """
    linhas_por_espaco = defaultdict(lambda: {"participantes": [], "total": 0})
    consulta = Reservation.objects.filter(
        status__in=STATUS_QUE_OCUPAM,
        start_time__lt=fim,
        end_time__gt=inicio,
    ).values_list("space_id", "space__name", "space__capacity", "attendee_count")

    nomes = {}
    capacidades = {}
    for space_id, nome, capacidade, participantes in consulta:
        nomes[space_id] = nome
        capacidades[space_id] = capacidade
        linhas_por_espaco[space_id]["total"] += 1
        if participantes:
            linhas_por_espaco[space_id]["participantes"].append(participantes)

    linhas = []
    for space_id, dados in linhas_por_espaco.items():
        if not dados["participantes"]:
            continue
        media = statistics.fmean(dados["participantes"])
        capacidade = capacidades[space_id] or 0
        linhas.append(
            {
                "espaco": nomes[space_id],
                "espaco_id": space_id,
                "capacidade": capacidade,
                "media_participantes": media,
                "taxa": (media / capacidade) if capacidade else 0.0,
                "com_informacao": len(dados["participantes"]),
                "total": dados["total"],
            }
        )
    linhas.sort(key=lambda linha: (linha["taxa"], linha["espaco"]))
    return linhas


#: Períodos oferecidos na tela. A chave viaja na querystring; o rótulo é o que
#: a pessoa lê. Ficam aqui, e não no template, para que a exportação CSV
#: entenda exatamente os mesmos valores que a tela — um relatório e seu arquivo
#: divergirem sobre qual mês estão descrevendo é o pior defeito possível aqui.
PRESETS = (
    ("7", "Últimos 7 dias"),
    ("30", "Últimos 30 dias"),
    ("mes", "Mês atual"),
    ("mes_anterior", "Mês anterior"),
)

PRESET_PADRAO = "30"


def _limites_do_dia(primeiro, ultimo):
    """Return the aware bounds of a closed range of dates, end exclusive."""
    from django.utils import timezone

    inicio = timezone.make_aware(datetime.datetime.combine(primeiro, datetime.time.min))
    fim = timezone.make_aware(
        datetime.datetime.combine(ultimo + datetime.timedelta(days=1), datetime.time.min)
    )
    return inicio, fim


def periodo_pedido(preset=None, de=None, ate=None, *, hoje=None):
    """Return the period to report on, from a preset or two typed dates.

    Uma data inválida não é erro de digitação a corrigir com página de erro: é
    URL editada ou link velho. Cai no período padrão, que mostra números
    verdadeiros — ao contrário de uma tela de erro, que não mostra nada.

    Args:
        preset: Uma das chaves de :data:`PRESETS`, ou vazio.
        de: Data inicial ``YYYY-MM-DD``, quando o período for digitado.
        ate: Data final ``YYYY-MM-DD``, inclusiva.
        hoje: O dia de referência; ``timezone.localdate()`` quando omitido.

    Returns:
        dict: ``inicio`` e ``fim`` cientes do fuso, ``primeiro_dia`` e
        ``ultimo_dia`` como datas, ``preset`` efetivamente usado (vazio quando
        o período foi digitado) e ``rotulo``.
    """
    from django.utils import timezone

    hoje = timezone.localdate() if hoje is None else hoje

    if de or ate:
        try:
            primeiro = datetime.date.fromisoformat(de)
            ultimo = datetime.date.fromisoformat(ate)
        except (TypeError, ValueError):
            primeiro = ultimo = None
        if primeiro and ultimo and primeiro <= ultimo:
            inicio, fim = _limites_do_dia(primeiro, ultimo)
            return {
                "inicio": inicio,
                "fim": fim,
                "primeiro_dia": primeiro,
                "ultimo_dia": ultimo,
                "preset": "",
                "rotulo": f"{primeiro:%d/%m/%Y} a {ultimo:%d/%m/%Y}",
            }

    chave = preset if preset in dict(PRESETS) else PRESET_PADRAO
    if chave == "mes":
        primeiro = hoje.replace(day=1)
        ultimo = hoje
    elif chave == "mes_anterior":
        primeiro_deste = hoje.replace(day=1)
        ultimo = primeiro_deste - datetime.timedelta(days=1)
        primeiro = ultimo.replace(day=1)
    else:
        dias = int(chave)
        # O período inclui hoje, então recua ``dias - 1``: "últimos 7 dias" que
        # cobrisse oito é o erro clássico de intervalo fechado.
        ultimo = hoje
        primeiro = hoje - datetime.timedelta(days=dias - 1)

    inicio, fim = _limites_do_dia(primeiro, ultimo)
    return {
        "inicio": inicio,
        "fim": fim,
        "primeiro_dia": primeiro,
        "ultimo_dia": ultimo,
        "preset": chave,
        "rotulo": dict(PRESETS)[chave],
    }

