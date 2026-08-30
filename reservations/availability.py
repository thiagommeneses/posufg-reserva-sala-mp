"""Derive what is offered to the user from what is actually booked.

Este módulo não decide nada sobre reservas — ele **lê** reservas e manutenções e
apresenta o resultado em duas formas:

* :func:`gerar_slots`, para a tela de um espaço: a janela de funcionamento
  fatiada no incremento da política, cada pedaço marcado como livre, reservado
  ou em manutenção.
* :func:`resumo_em_lote`, para a listagem: um resumo por espaço, calculado com
  **duas consultas no total**, independentemente de quantos espaços a lista
  tenha. Uma consulta por card seria um N+1 clássico e é justamente o que o
  pacote V2 proíbe.

Duas coisas que valem registro, porque erram fácil:

1. O status **nunca** deriva de ``is_active``. Um espaço desativado não aparece
   na listagem; um espaço ativo pode estar lotado. São eixos diferentes, e
   misturá-los faz o card mentir.
2. O dia é delimitado no fuso local, como no resto do sistema. "Hoje" é o dia
   que o usuário vê no calendário, não o dia em UTC.
"""

import datetime
from collections import defaultdict

from django.db.models import Q
from django.utils import timezone

from reservations.enums import ACTIVE_RESERVATION_STATUSES
from reservations.models import BookingPolicy, MaintenanceBlock, Reservation

#: Situação de um pedaço da janela de funcionamento.
LIVRE = "livre"
RESERVADO = "reservado"
MANUTENCAO = "manutencao"

#: Situação de um espaço na listagem, para a data escolhida.
STATUS_LIVRE = "livre"
STATUS_POUCOS = "poucos"
STATUS_LOTADO = "lotado"
STATUS_MANUTENCAO = "manutencao"
STATUS_ENCERRADO = "encerrado"
#: O prédio não abre neste dia da semana. É um estado diferente de
#: ``STATUS_ENCERRADO``: "o expediente de hoje já acabou" e "aqui não há
#: expediente" levam a ações diferentes — a primeira sugere amanhã cedo, a
#: segunda sugere outro dia da semana.
STATUS_FECHADO = "fechado"

#: Situação quando o usuário pediu um horário específico. São estados
#: diferentes dos de cima de propósito: "Disponível" num dia com uma janela
#: livre às 8h não responde a quem perguntou por 15h.
STATUS_LIVRE_NO_HORARIO = "livre_no_horario"
STATUS_OCUPADO_NO_HORARIO = "ocupado_no_horario"

#: Texto exibido no cartão. Fica aqui, e não no template, para que os testes
#: possam afirmar sobre o rótulo sem depender de HTML.
ROTULOS = {
    STATUS_LIVRE: "Disponível",
    STATUS_POUCOS: "Poucos horários",
    STATUS_LOTADO: "Sem horários",
    STATUS_MANUTENCAO: "Em manutenção",
    STATUS_ENCERRADO: "Fora do horário",
    STATUS_FECHADO: "Fechado",
    STATUS_LIVRE_NO_HORARIO: "Disponível no horário",
    STATUS_OCUPADO_NO_HORARIO: "Indisponível no horário",
}

#: Os dois estados que respondem a um horário pedido. O cartão precisa saber
#: disso para não repetir "hoje"/"em 27/08" depois de um rótulo que já é sobre
#: um horário exato.
STATUS_DE_HORARIO = frozenset({STATUS_LIVRE_NO_HORARIO, STATUS_OCUPADO_NO_HORARIO})


def janela_do_dia(date, policy):
    """Return the operating window of ``date`` as aware datetimes.

    Args:
        date: O dia desejado.
        policy: A política vigente.

    Returns:
        tuple[datetime, datetime]: Início e fim da janela, no fuso local.
    """
    inicio = timezone.make_aware(datetime.datetime.combine(date, policy.opening_time))
    fim = timezone.make_aware(datetime.datetime.combine(date, policy.closing_time))
    return inicio, fim


def _intervalos_ocupados(reservas, bloqueios, inicio, fim):
    """Return the busy intervals inside a window, clipped to it.

    Args:
        reservas: Reservas ativas que tocam a janela.
        bloqueios: Bloqueios de manutenção que tocam a janela.
        inicio: Início da janela.
        fim: Fim da janela.

    Returns:
        list[tuple]: ``(início, fim, tipo)`` ordenados por início.
    """
    intervalos = [
        (max(reserva.start_time, inicio), min(reserva.end_time, fim), RESERVADO)
        for reserva in reservas
    ]
    intervalos += [
        (max(bloqueio.start_time, inicio), min(bloqueio.end_time, fim), MANUTENCAO)
        for bloqueio in bloqueios
    ]
    intervalos.sort(key=lambda intervalo: intervalo[0])
    return intervalos


def _situacao(inicio_do_slot, fim_do_slot, ocupados):
    """Return the status of one slot against the busy intervals.

    A manutenção vence a reserva quando as duas tocam o mesmo pedaço: é a
    informação mais útil para quem olha, e a mais restritiva.

    Args:
        inicio_do_slot: Início do pedaço.
        fim_do_slot: Fim do pedaço.
        ocupados: Intervalos ocupados, como devolvidos por :func:`_intervalos_ocupados`.

    Returns:
        str: ``LIVRE``, ``RESERVADO`` ou ``MANUTENCAO``.
    """
    situacao = LIVRE
    for inicio, fim, tipo in ocupados:
        if inicio < fim_do_slot and fim > inicio_do_slot:
            if tipo == MANUTENCAO:
                return MANUTENCAO
            situacao = RESERVADO
    return situacao


def gerar_slots(space, date, policy=None, *, reservas=None, bloqueios=None):
    """Return the operating window of ``date`` sliced into offerable slots.

    Diferente de ``services.get_availability_for_date`` — que devolve intervalos
    contínuos e é o contrato público da API — aqui a janela sai fatiada no
    incremento da política, que é o que a tela precisa para oferecer botões
    clicáveis em vez de um único bloco de 24 horas.

    Args:
        space: O espaço.
        date: O dia desejado.
        policy: A política vigente; carregada do banco quando omitida.
        reservas: Reservas já carregadas, para evitar nova consulta (uso interno
            do cálculo em lote).
        bloqueios: Bloqueios já carregados, pelo mesmo motivo.

    Returns:
        list[dict]: Um dicionário por pedaço, com ``inicio``, ``fim``,
        ``situacao``, ``rotulo`` e ``disponivel``.
    """
    policy = policy or BookingPolicy.carregar()
    if not policy.abre_em(date):
        # Dia fechado não tem pedaço nenhum a oferecer. Devolver a janela
        # inteira marcada como ocupada seria pior: a tela mostraria trinta
        # botões cinzentos onde a resposta certa é uma frase.
        return []
    inicio_janela, fim_janela = janela_do_dia(date, policy)

    if reservas is None:
        reservas = Reservation.objects.filter(
            space=space,
            status__in=ACTIVE_RESERVATION_STATUSES,
            start_time__lt=fim_janela,
            end_time__gt=inicio_janela,
        )
    if bloqueios is None:
        bloqueios = MaintenanceBlock.objects.filter(
            space=space,
            start_time__lt=fim_janela,
            end_time__gt=inicio_janela,
        )

    ocupados = _intervalos_ocupados(reservas, bloqueios, inicio_janela, fim_janela)
    incremento = datetime.timedelta(minutes=policy.slot_minutes)

    slots = []
    atual = inicio_janela
    while atual + incremento <= fim_janela:
        proximo = atual + incremento
        situacao = _situacao(atual, proximo, ocupados)
        slots.append(
            {
                "inicio": atual,
                "fim": proximo,
                "situacao": situacao,
                "disponivel": situacao == LIVRE,
            }
        )
        atual = proximo
    return slots


def _agrupar_por_espaco(objetos):
    """Group objects by their ``space_id``.

    Args:
        objetos: Reservas ou bloqueios já carregados.

    Returns:
        dict[int, list]: Objetos indexados pelo id do espaço.
    """
    agrupados = defaultdict(list)
    for objeto in objetos:
        agrupados[objeto.space_id].append(objeto)
    return agrupados


def _proxima_janela_livre(slots, agora):
    """Return the start of the first free slot that has not passed yet.

    Args:
        slots: Os pedaços do dia.
        agora: O instante atual, ou ``None`` para não descartar o passado.

    Returns:
        datetime | None: O início do próximo horário livre, se houver.
    """
    for slot in slots:
        if not slot["disponivel"]:
            continue
        if agora is not None and slot["fim"] <= agora:
            continue
        return slot["inicio"]
    return None


def _status_do_espaco(slots, restantes, policy, em_manutencao):
    """Classify a space for the given day.

    Args:
        slots: Todos os pedaços do dia.
        restantes: Os pedaços livres que ainda não passaram.
        policy: A política vigente.
        em_manutencao: Se algum pedaço do dia está bloqueado para manutenção.

    Returns:
        str: Uma das constantes ``STATUS_*``.
    """
    if restantes:
        if len(restantes) <= policy.few_slots_threshold:
            return STATUS_POUCOS
        return STATUS_LIVRE
    if em_manutencao and all(slot["situacao"] == MANUTENCAO for slot in slots):
        return STATUS_MANUTENCAO
    if any(slot["disponivel"] for slot in slots):
        # Havia horário livre, mas o dia já passou por ele.
        return STATUS_ENCERRADO
    return STATUS_LOTADO


def _cabe_no_horario(slots, inicio, fim):
    """Return whether every slot inside a window is free.

    Args:
        slots: Os pedaços do dia.
        inicio: Início do intervalo pedido.
        fim: Fim do intervalo pedido.

    Returns:
        bool: ``True`` se o intervalo inteiro está livre.
    """
    tocados = [slot for slot in slots if slot["inicio"] < fim and slot["fim"] > inicio]
    return bool(tocados) and all(slot["disponivel"] for slot in tocados)


def resumo_em_lote(spaces, date, policy=None, *, agora=None, inicio=None, duracao_minutos=None):
    """Return a per-space availability summary for ``date``.

    Duas consultas no total — uma de reservas, uma de manutenções — para
    qualquer quantidade de espaços. Este é o ponto principal da função: fazer
    uma consulta por cartão é o N+1 que o pacote V2 proíbe explicitamente.

    Quando ``inicio`` é informado, o resumo passa a responder à pergunta que a
    pessoa fez de fato. "Disponível" num dia com uma janela livre às 8h não
    responde a quem perguntou por 15h — por isso o status vira
    ``livre_no_horario``/``ocupado_no_horario``, e não uma variação do outro.

    Args:
        spaces: Os espaços a resumir (lista ou queryset já avaliado).
        date: O dia desejado.
        policy: A política vigente; carregada do banco quando omitida.
        agora: O instante considerado "agora"; ``timezone.now()`` quando
            omitido. Horários que já terminaram não contam como disponíveis.
        inicio: Horário local pedido (``datetime.time``). Sem ele, o resumo é
            do dia inteiro, como antes.
        duracao_minutos: Duração pedida. Sem ela, usa a duração mínima da
            política — é o menor compromisso que a pessoa poderia assumir.

    Returns:
        dict[int, dict]: Indexado pelo id do espaço, com ``status``, ``rotulo``,
        ``slots_livres``, ``minutos_livres`` e ``proxima_janela``.
    """
    spaces = list(spaces)
    policy = policy or BookingPolicy.carregar()
    if not spaces:
        return {}

    if not policy.abre_em(date):
        # O dia é o mesmo para todos os espaços, então a resposta também é —
        # e nenhuma consulta precisa ser feita. Sem este atalho o resumo cairia
        # em "Sem horários", que descreve um prédio lotado, não um prédio
        # fechado; e com horário pedido cairia em "Indisponível no horário",
        # que faz a pessoa procurar outra sala no mesmo domingo.
        return {
            space.pk: {
                "status": STATUS_FECHADO,
                "rotulo": ROTULOS[STATUS_FECHADO],
                "slots_livres": 0,
                "minutos_livres": 0,
                "proxima_janela": None,
            }
            for space in spaces
        }

    inicio_janela, fim_janela = janela_do_dia(date, policy)
    ids = [space.pk for space in spaces]
    agora = timezone.now() if agora is None else agora

    reservas = _agrupar_por_espaco(
        Reservation.objects.filter(
            space_id__in=ids,
            status__in=ACTIVE_RESERVATION_STATUSES,
            start_time__lt=fim_janela,
            end_time__gt=inicio_janela,
        )
    )
    bloqueios = _agrupar_por_espaco(
        MaintenanceBlock.objects.filter(
            space_id__in=ids,
            start_time__lt=fim_janela,
            end_time__gt=inicio_janela,
        )
    )

    pedido_inicio = pedido_fim = None
    if inicio is not None:
        pedido_inicio = timezone.make_aware(datetime.datetime.combine(date, inicio))
        pedido_fim = pedido_inicio + datetime.timedelta(
            minutes=duracao_minutos or policy.min_duration_minutes
        )

    resumo = {}
    for space in spaces:
        slots = gerar_slots(
            space,
            date,
            policy,
            reservas=reservas.get(space.pk, []),
            bloqueios=bloqueios.get(space.pk, []),
        )
        restantes = [slot for slot in slots if slot["disponivel"] and slot["fim"] > agora]
        em_manutencao = any(slot["situacao"] == MANUTENCAO for slot in slots)
        if pedido_inicio is not None:
            status = (
                STATUS_LIVRE_NO_HORARIO
                if _cabe_no_horario(slots, pedido_inicio, pedido_fim)
                else STATUS_OCUPADO_NO_HORARIO
            )
        else:
            status = _status_do_espaco(slots, restantes, policy, em_manutencao)
        resumo[space.pk] = {
            "status": status,
            "rotulo": ROTULOS[status],
            "slots_livres": len(restantes),
            "minutos_livres": len(restantes) * policy.slot_minutes,
            "proxima_janela": _proxima_janela_livre(slots, agora),
        }
    return resumo


#: Nomes dos dias em português, para o contexto do assistente. O ``%A`` do
#: ``strftime`` depende do locale do sistema operacional, que no contêiner é o
#: inglês — e um prompt dizendo "Wednesday" para pedir "quarta que vem" é
#: exatamente o tipo de detalhe que faz o modelo errar em silêncio.
DIAS_DA_SEMANA = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]


def contexto_temporal(policy=None, *, hoje=None):
    """Return the facts the assistant needs to resolve dates and times.

    Um modelo de linguagem não sabe que dia é hoje nem que horas abre o prédio.
    Esta função reúne esses fatos num dicionário simples, para que o serviço de
    IA continue sem saber nada sobre a política de reserva — quem conhece a
    regra é esta camada.

    Args:
        policy: A política vigente; carregada do banco quando omitida.
        hoje: O dia de referência; ``timezone.localdate()`` quando omitido.

    Returns:
        dict: Contexto pronto para ``extract_room_search_filters``.
    """
    policy = policy or BookingPolicy.carregar()
    hoje = timezone.localdate() if hoje is None else hoje
    return {
        "hoje": hoje.isoformat(),
        "hoje_date": hoje,
        "dia_da_semana": DIAS_DA_SEMANA[hoje.weekday()],
        "abertura": policy.opening_time.strftime("%H:%M"),
        "abertura_time": policy.opening_time,
        "fechamento": policy.closing_time.strftime("%H:%M"),
        "fechamento_time": policy.closing_time,
        "horizonte": policy.horizon_days,
        "duracao_minima": policy.min_duration_minutes,
        "duracao_maxima": policy.max_duration_minutes,
    }


#: Onde a manhã termina. Meio-dia é meio-dia — não é parâmetro de política,
#: é o jeito como as pessoas dividem o expediente ao falar dele.
FIM_DA_MANHA = datetime.time(12, 0)


def rotulo_de_duracao(minutos):
    """Return a duration written the way a person says it.

    "90 min" é correto e ninguém fala assim. O rótulo é montado aqui, e não no
    template, porque a aritmética de horas e minutos não cabe em filtros do
    Django sem virar uma linha ilegível.

    Args:
        minutos: A duração em minutos.

    Returns:
        str: ``"30 min"``, ``"1h"``, ``"1h30"``.
    """
    horas, resto = divmod(minutos, 60)
    if not horas:
        return f"{resto} min"
    if not resto:
        return f"{horas}h"
    return f"{horas}h{resto:02d}"


def duracoes_oferecidas(policy=None, *, limite=8):
    """Return the reservation lengths the screen may offer.

    Saem da política, e não de uma lista escrita no código: quem configurou
    duração mínima de 30 e máxima de 240 decidiu, ali, o que pode ser pedido.
    Uma lista fixa aqui contradiria a configuração no dia em que ela mudasse.

    Args:
        policy: A política vigente; carregada do banco quando omitida.
        limite: Quantas opções no máximo. Oito já enche uma linha na tela; mais
            do que isso vira uma lista para procurar, não para escolher.

    Returns:
        list[dict]: ``{"minutos": int, "rotulo": str}``, da duração mínima à
        máxima, no incremento da política.
    """
    policy = policy or BookingPolicy.carregar()
    passo = policy.slot_minutes or policy.min_duration_minutes
    if not passo:
        return [
            {
                "minutos": policy.min_duration_minutes,
                "rotulo": rotulo_de_duracao(policy.min_duration_minutes),
            }
        ]

    duracoes = []
    atual = policy.min_duration_minutes
    while atual <= policy.max_duration_minutes and len(duracoes) < limite:
        duracoes.append({"minutos": atual, "rotulo": rotulo_de_duracao(atual)})
        atual += passo
    if duracoes:
        return duracoes
    return [
        {
            "minutos": policy.min_duration_minutes,
            "rotulo": rotulo_de_duracao(policy.min_duration_minutes),
        }
    ]


def duracao_valida(bruto, policy=None):
    """Return the requested duration when the policy allows it.

    Args:
        bruto: O valor vindo da querystring, em minutos, como texto.
        policy: A política vigente; carregada do banco quando omitida.

    Returns:
        int | None: A duração aceita, ou ``None`` quando não serve.
    """
    policy = policy or BookingPolicy.carregar()
    bruto = (bruto or "").strip()
    if not bruto.isdigit():
        return None
    candidata = int(bruto)
    if policy.min_duration_minutes <= candidata <= policy.max_duration_minutes:
        return candidata
    return None


def marcar_cabimento(slots, duracao_minutos):
    """Say, for each slot, whether a reservation of that length fits starting there.

    A tela oferece um clique só: escolher a duração antes e o horário depois faz
    o botão significar "reservar das 9h às 10h30", e não "reservar os trinta
    minutos das 9h". Sem esta marcação a pessoa clicaria num horário livre e só
    descobriria no passo 3 que a hora e meia seguinte estava ocupada.

    Não decide nada sobre reservas — lê os pedaços já calculados e conta quantos
    seguidos estão livres. Quem valida continua sendo ``reservations.validators``.

    Args:
        slots: Os pedaços do dia, como devolvidos por :func:`gerar_slots`.
        duracao_minutos: A duração pretendida.

    Returns:
        list[dict]: Cópias dos pedaços com ``cabe`` (bool) e ``fim_da_reserva``
        (o término que aquele clique produziria, ou ``None`` quando não cabe).
    """
    duracao = datetime.timedelta(minutes=duracao_minutos)
    marcados = []
    for indice, slot in enumerate(slots):
        fim_desejado = slot["inicio"] + duracao
        # O último pedaço do dia define o fim da janela: uma reserva não pode
        # passar dele, ainda que "sobre" tempo no relógio.
        cabe = slot["disponivel"] and fim_desejado <= slots[-1]["fim"]
        if cabe:
            for seguinte in slots[indice:]:
                if seguinte["inicio"] >= fim_desejado:
                    break
                if not seguinte["disponivel"]:
                    cabe = False
                    break
        copia = dict(slot)
        copia["cabe"] = cabe
        copia["fim_da_reserva"] = fim_desejado if cabe else None
        marcados.append(copia)
    return marcados


def agrupar_por_periodo(slots):
    """Split the day's slots into morning and afternoon.

    Vinte botões em fileira única são difíceis de varrer com os olhos. Dois
    blocos rotulados dão ao usuário um ponto de referência antes de ele começar
    a procurar o horário.

    Args:
        slots: Os pedaços do dia, como devolvidos por :func:`gerar_slots`.

    Returns:
        list[dict]: Grupos com ``rotulo`` e ``slots``; grupos vazios não entram.
    """
    manha = [slot for slot in slots if timezone.localtime(slot["inicio"]).time() < FIM_DA_MANHA]
    tarde = [slot for slot in slots if timezone.localtime(slot["inicio"]).time() >= FIM_DA_MANHA]
    grupos = []
    if manha:
        grupos.append({"rotulo": "Manhã", "slots": manha})
    if tarde:
        grupos.append({"rotulo": "Tarde", "slots": tarde})
    return grupos


def horarios_proximos(slots, alvo, limite=3):
    """Return the free slots closest to a requested time.

    Quando o horário pedido está ocupado, dizer só "indisponível" devolve o
    problema para o usuário. O que ajuda é a próxima pergunta já respondida:
    "então quando?".

    A ordenação é pela distância até o horário pedido, e não pela hora do dia:
    quem queria 15h prefere 14h30 a 08h.

    Args:
        slots: Os pedaços do dia.
        alvo: O início pedido (``datetime`` ciente de fuso).
        limite: Quantas sugestões devolver.

    Returns:
        list[dict]: Os pedaços livres mais próximos, do mais perto ao mais longe.
    """
    livres = [slot for slot in slots if slot["disponivel"]]
    livres.sort(key=lambda slot: abs(slot["inicio"] - alvo))
    return livres[:limite]


#: Até quantas vezes a capacidade original uma sugestão pode ter.
#:
#: É um julgamento de produto, não um cálculo: uma sala com o dobro dos lugares
#: ainda serve para a mesma reunião — sobra espaço e pronto. Um auditório de 50
#: lugares oferecido a quem procurava uma sala de 8 não é a mesma coisa com
#: folga, é outra coisa. O limite só vale para espaços de tipo diferente ou
#: ainda não classificados: quem procurava um auditório e recebe um auditório
#: maior recebeu o que pediu.
FATOR_MAXIMO_DE_CAPACIDADE = 2


def espacos_equivalentes(space, date, inicio, policy=None, *, duracao_minutos=None, limite=3):
    """Return other spaces free in the requested window.

    "Equivalente" aqui significa capacidade suficiente para quem cabia no
    original — sugerir uma sala de quatro lugares a quem procurava uma de oito
    seria trocar um problema por outro — e, quando o espaço tem tipo, o mesmo
    tipo primeiro.

    Espaços **sem** tipo entram na lista, depois dos do mesmo tipo. A
    classificação é deliberadamente incompleta neste sistema: o backfill propõe
    e um administrador revisa. Excluir o que ainda não foi classificado
    esconderia salas boas por uma pendência administrativa que o usuário não
    tem como ver nem resolver.

    Continua valendo a regra de não fazer uma consulta por cartão: a
    disponibilidade sai de :func:`resumo_em_lote`, em duas consultas.

    Args:
        space: O espaço que o usuário estava vendo.
        date: O dia desejado.
        inicio: O horário pedido (``datetime.time``).
        policy: A política vigente; carregada do banco quando omitida.
        duracao_minutos: A duração pedida.
        limite: Quantas sugestões devolver.

    Returns:
        list: Espaços livres na janela, os do mesmo tipo primeiro e, dentro de
        cada grupo, do mais parecido em capacidade ao menos.
    """
    from spaces.models import Space

    policy = policy or BookingPolicy.carregar()
    candidatos = Space.objects.filter(is_active=True, capacity__gte=space.capacity).exclude(
        pk=space.pk
    )
    if space.space_type_id:
        # Mesmo tipo sem teto de tamanho; o resto, dentro da banda de capacidade.
        candidatos = candidatos.filter(
            Q(space_type_id=space.space_type_id)
            | Q(capacity__lte=space.capacity * FATOR_MAXIMO_DE_CAPACIDADE)
        )
    else:
        candidatos = candidatos.filter(capacity__lte=space.capacity * FATOR_MAXIMO_DE_CAPACIDADE)
    candidatos = list(candidatos.select_related("space_type").order_by("capacity", "name"))
    if not candidatos:
        return []

    # Mesmo tipo antes do não classificado: a sugestão mais segura vem primeiro.
    candidatos.sort(key=lambda candidato: candidato.space_type_id != space.space_type_id)

    resumo = resumo_em_lote(
        candidatos, date, policy, inicio=inicio, duracao_minutos=duracao_minutos
    )
    livres = []
    for candidato in candidatos:
        situacao = resumo.get(candidato.pk)
        if situacao and situacao["status"] == STATUS_LIVRE_NO_HORARIO:
            candidato.resumo_disponibilidade = situacao
            livres.append(candidato)
    return livres[:limite]


def proximo_dia_aberto(date, policy=None, *, limite=14):
    """Return the first day from ``date`` on that the building opens.

    Existe para a tela poder responder "o prédio abre na segunda-feira" em vez
    de só dizer "Fechado" e deixar a pessoa clicar dia a dia até acertar.

    Args:
        date: A partir de quando procurar, inclusive.
        policy: A política vigente; carregada do banco quando omitida.
        limite: Quantos dias no máximo olhar adiante. Uma semana bastaria; duas
            dão folga sem risco de laço infinito se a política ficar sem dia
            aberto por algum caminho que não passe pelo ``clean``.

    Returns:
        datetime.date | None: O primeiro dia aberto, ou ``None`` se não houver
        nenhum dentro do limite.
    """
    policy = policy or BookingPolicy.carregar()
    for adiante in range(limite):
        candidato = date + datetime.timedelta(days=adiante)
        if policy.abre_em(candidato):
            return candidato
    return None


def data_dentro_do_horizonte(date, policy=None, *, hoje=None):
    """Return whether ``date`` can still be booked under the policy horizon.

    Args:
        date: O dia desejado.
        policy: A política vigente; carregada do banco quando omitida.
        hoje: O dia considerado "hoje"; ``timezone.localdate()`` quando omitido.

    Returns:
        bool: ``True`` se a data está entre hoje e o fim do horizonte.
    """
    policy = policy or BookingPolicy.carregar()
    hoje = timezone.localdate() if hoje is None else hoje
    return hoje <= date <= hoje + datetime.timedelta(days=policy.horizon_days)
