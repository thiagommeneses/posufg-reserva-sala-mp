"""Pipeline sequencial de três agentes especialistas para pedidos de espaço.

Implementa o desenho descrito em ``docs/dapia/04-especificacao-sistema-multiagente.md``:
o pedido em linguagem natural passa pelo Intérprete de Solicitação, pelo Consultor
Normativo e pelo Alocador de Espaço, nessa ordem, e cada etapa só depende da saída da
anterior.

Nada aqui reimplementa o que o sistema já sabe fazer. A extração de critérios reusa
``services.extract_room_search_filters``; a consulta normativa reusa ``knowledge.retrieval``;
a disponibilidade e a criação da reserva reusam ``reservations.availability`` e
``reservations.services``. O que este módulo acrescenta é o **julgamento**: decidir, a
partir do parecer, se reserva, se propõe alternativa ou se escala a um humano.

Cada etapa devolve um :class:`PassoDoAgente` com duração e tokens gastos, para que o
runner de testes possa medir latência e custo sem instrumentar o caminho de produção.
"""

import dataclasses
import datetime
import logging
import time

from django.utils import timezone

from ai_assistant import services
from ai_assistant.exceptions import AIServiceError
from knowledge import retrieval
from knowledge.embedding import EmbeddingError
from reservations import availability, validators
from reservations.models import BookingPolicy
from reservations.services import create_reservation
from spaces.models import Space

logger = logging.getLogger(__name__)

#: Quantas opções o Alocador oferece quando o pedido original não cabe.
MAX_ALTERNATIVAS = 3

#: Quantos trechos da base normativa alimentam o parecer.
PARECER_TOP_K = 5

#: Até quantos dias à frente o Alocador procura alternativa quando o pedido não cabe.
DIAS_PARA_ALTERNATIVA = 7

#: Campos sem os quais não dá para consultar disponibilidade nem reservar.
CAMPOS_ESSENCIAIS = ("date", "start_time", "duration_minutes")

ROTULO_DO_CAMPO = {
    "date": "a data",
    "start_time": "o horário de início",
    "duration_minutes": "a duração",
}

# Decisões possíveis do pipeline.
DECISAO_RESERVA = "reserva_confirmada"
DECISAO_ALTERNATIVAS = "alternativas"
DECISAO_ESCALONAMENTO = "escalonamento"
DECISAO_ESCLARECIMENTO = "esclarecimento"
DECISAO_ERRO = "erro"

# Pareceres possíveis do Consultor Normativo.
PARECER_ADMISSIVEL = "admissivel"
PARECER_INADMISSIVEL = "inadmissivel"
PARECER_ESCALONAR = "requer_decisao_humana"
PARECERES_VALIDOS = frozenset({PARECER_ADMISSIVEL, PARECER_INADMISSIVEL, PARECER_ESCALONAR})

AGENTE_INTERPRETE = "interprete"
AGENTE_NORMATIVO = "normativo"
AGENTE_ALOCADOR = "alocador"

_PARECER_SYSTEM_PROMPT = (
    "Você é assessor de um órgão de controle e analisa pedidos de uso de espaços físicos.\n"
    "A política interna do órgão JÁ foi verificada por outro componente, e o pedido passou: "
    "duração, antecedência, horário e dia de funcionamento estão dentro do permitido.\n"
    "Os trechos que você recebe são regulamentos de OUTRAS instituições públicas. Eles são "
    "referência comparativa: o MP-GO não possui norma própria, e nenhuma dessas regras "
    "vincula o órgão. Nunca torne um pedido inadmissível só porque outra instituição exige "
    "algo que ele não atende — nesse caso, registre a exigência como referência e siga.\n"
    "Devolva 'requer_decisao_humana' SOMENTE quando o pedido envolver algo que a política "
    "interna não cobre e que traga risco institucional: uso por pessoa ou entidade externa, "
    "cobrança de ingresso, evento aberto ao público, finalidade político-partidária ou "
    "religiosa, ou reserva em nome de terceiro.\n"
    "Fora dessas hipóteses, o parecer é 'admissivel'.\n"
    "Toda restrição que você afirmar precisa apontar o número do trecho que a sustenta. "
    "Permitir não exige fonte; restringir exige.\n"
    "Responda SOMENTE com JSON válido, no formato exato: "
    '{"parecer": "admissivel" | "inadmissivel" | "requer_decisao_humana", '
    '"fundamentacao": <string em português, no máximo cinco linhas>, '
    '"citacoes": [<números dos trechos usados>]}.'
)


@dataclasses.dataclass
class PassoDoAgente:
    """Registro de uma etapa do pipeline, com o custo que ela teve."""

    agente: str
    duracao_ms: int
    saida: dict = dataclasses.field(default_factory=dict)
    tokens: dict = dataclasses.field(default_factory=dict)
    espera_ms: int = 0
    erro: str | None = None

    @property
    def total_tokens(self) -> int:
        """Return the token count of this step, or zero when the LLM was not called."""
        return self.tokens.get("total_tokens") or 0


@dataclasses.dataclass
class ResultadoDoPipeline:
    """O que o pipeline devolve ao chamador."""

    pedido: str
    decisao: str
    mensagem: str
    criterios: dict = dataclasses.field(default_factory=dict)
    parecer: dict = dataclasses.field(default_factory=dict)
    alternativas: list = dataclasses.field(default_factory=list)
    reserva_id: int | None = None
    passos: list = dataclasses.field(default_factory=list)

    @property
    def duracao_ms(self) -> int:
        """Return the net processing time of every step, excluding 429 waits."""
        return sum(passo.duracao_ms for passo in self.passos)

    @property
    def espera_ms(self) -> int:
        """Return the milliseconds spent waiting on HTTP 429 retries."""
        return sum(passo.espera_ms for passo in self.passos)

    @property
    def total_tokens(self) -> int:
        """Return the tokens spent across every step."""
        return sum(passo.total_tokens for passo in self.passos)

    def como_dict(self) -> dict:
        """Return a JSON-serialisable view, for the test runner's report."""
        return {
            "pedido": self.pedido,
            "decisao": self.decisao,
            "mensagem": self.mensagem,
            "criterios": _criterios_serializaveis(self.criterios),
            "parecer": self.parecer,
            "alternativas": self.alternativas,
            "reserva_id": self.reserva_id,
            "duracao_ms": self.duracao_ms,
            "espera_ms": self.espera_ms,
            "total_tokens": self.total_tokens,
            "passos": [
                {
                    "agente": passo.agente,
                    "duracao_ms": passo.duracao_ms,
                    "espera_ms": passo.espera_ms,
                    "tokens": passo.tokens,
                    "erro": passo.erro,
                }
                for passo in self.passos
            ],
        }


def _tempo_do_passo(relogio, tokens=None) -> tuple[int, int]:
    """Split wall-clock time into net work and 429 wait.

    Args:
        relogio: The step stopwatch.
        tokens: Optional usage sink that may carry ``espera_ms``.

    Returns:
        tuple: Net duration in milliseconds and wait in milliseconds.
    """
    tokens = tokens or {}
    espera_ms = int(tokens.pop("espera_ms", 0) or 0)
    return max(0, relogio.decorrido_ms - espera_ms), espera_ms


def _registrar_passo(agente, relogio, tokens=None, **kwargs) -> PassoDoAgente:
    """Build a step record with net duration and recorded 429 wait.

    Args:
        agente: Which specialist produced the step.
        relogio: The step stopwatch.
        tokens: Optional usage sink.
        **kwargs: Extra fields for :class:`PassoDoAgente`.

    Returns:
        The filled step record.
    """
    duracao_ms, espera_ms = _tempo_do_passo(relogio, tokens)
    return PassoDoAgente(
        agente=agente,
        duracao_ms=duracao_ms,
        espera_ms=espera_ms,
        tokens=tokens or {},
        **kwargs,
    )


def _anexar_avisos_de_catalogo(mensagem: str, criterios: dict) -> str:
    """Append discarded-equipment warnings that are not already in the message.

    Args:
        mensagem: The decision text already built.
        criterios: The interpreter output, possibly with ``atributos_ignorados``.

    Returns:
        The message plus any missing catalog warnings.
    """
    extras = []
    for termo in criterios.get("atributos_ignorados") or []:
        aviso = services.aviso_de_equipamento_ignorado(termo)
        if aviso not in mensagem:
            extras.append(aviso)
    if not extras:
        return mensagem
    return f"{mensagem} {' '.join(extras)}".strip()


def _criterios_serializaveis(criterios: dict) -> dict:
    """Return the criteria with dates and times as strings."""
    saida = {}
    for chave, valor in criterios.items():
        if isinstance(valor, datetime.date | datetime.time):
            saida[chave] = valor.isoformat()
        else:
            saida[chave] = valor
    return saida


class _Cronometro:
    """Mede a duração de uma etapa sem espalhar ``time.perf_counter`` pelo código.

    ``decorrido_ms`` funciona dentro do bloco — necessário porque uma etapa pode
    terminar em ``return`` no meio do ``with``, antes de ``__exit__`` rodar.
    """

    def __enter__(self):
        self._inicio = time.perf_counter()
        self.duracao_ms = 0
        return self

    @property
    def decorrido_ms(self) -> int:
        """Return the milliseconds elapsed so far."""
        return int((time.perf_counter() - self._inicio) * 1000)

    def __exit__(self, *_):
        self.duracao_ms = self.decorrido_ms
        return False


# --------------------------------------------------------------------------- agente 1


def interpretar_pedido(texto: str, *, policy=None) -> tuple[dict, PassoDoAgente]:
    """Agente 1 — converte o pedido em texto livre em critérios estruturados.

    Args:
        texto: O pedido como a pessoa escreveu.
        policy: A política vigente; carregada do banco quando omitida.

    Returns:
        tuple: Os critérios extraídos e o registro do passo.
    """
    policy = policy or BookingPolicy.carregar()
    contexto = availability.contexto_temporal(policy)
    tokens: dict = {}

    with _Cronometro() as relogio:
        try:
            criterios = services.extract_room_search_filters(texto, contexto, usage_sink=tokens)
        except AIServiceError as exc:
            passo = _registrar_passo(AGENTE_INTERPRETE, relogio, tokens, erro=str(exc))
            return {}, passo

    criterios["faltando"] = [campo for campo in CAMPOS_ESSENCIAIS if criterios.get(campo) is None]
    passo = _registrar_passo(
        AGENTE_INTERPRETE, relogio, tokens, saida=_criterios_serializaveis(criterios)
    )
    return criterios, passo


def pergunta_de_esclarecimento(criterios: dict) -> str:
    """Return what to say back when the request cannot proceed as written.

    Um campo pode chegar vazio por dois motivos muito diferentes: a pessoa não o
    informou, ou informou e a validação recusou o valor (duração fora do permitido,
    horário fora do expediente, data no passado). Perguntar "qual a duração?" a quem
    acabou de escrever "por 15 minutos" é o pior desfecho possível — a pessoa repete a
    mesma coisa e leva a mesma resposta.

    Por isso o aviso da validação, quando existe, vem antes da pergunta e explica a
    recusa. Só quando não há aviso é que o campo estava mesmo ausente.

    Args:
        criterios: A saída do Agente 1, com ``faltando`` e ``avisos``.

    Returns:
        str: A mensagem devolvida a quem pediu.
    """
    avisos = criterios.get("avisos") or []
    faltando = criterios.get("faltando") or []
    rotulos = [ROTULO_DO_CAMPO[campo] for campo in faltando if campo in ROTULO_DO_CAMPO]

    if avisos:
        return " ".join(avisos) + " Corrija o pedido e envie de novo."
    if not rotulos:
        return "Pode detalhar um pouco mais o pedido?"
    if len(rotulos) == 1:
        return f"Para seguir, preciso saber {rotulos[0]}. Pode informar?"
    return f"Para seguir, preciso saber {', '.join(rotulos[:-1])} e {rotulos[-1]}. Pode informar?"


# --------------------------------------------------------------------------- agente 2


def _violacoes_de_politica(criterios: dict, policy) -> list[str]:
    """Return the policy rules the request breaks, in plain Portuguese.

    Esta é a metade determinística do parecer. Duração e antecedência são regras
    cadastradas pelo administrador — conferi-las com um modelo de linguagem seria
    trocar uma comparação exata por um palpite.
    """
    problemas = []
    duracao = criterios.get("duration_minutes")
    if duracao is not None:
        if duracao < policy.min_duration_minutes:
            problemas.append(
                f"a duração pedida ({duracao} min) é menor que o mínimo de "
                f"{policy.min_duration_minutes} min definido na política."
            )
        if duracao > policy.max_duration_minutes:
            problemas.append(
                f"a duração pedida ({duracao} min) excede o máximo de "
                f"{policy.max_duration_minutes} min definido na política."
            )

    data = criterios.get("date")
    if data is not None:
        hoje = timezone.localdate()
        if data < hoje:
            problemas.append("a data pedida já passou.")
        elif (data - hoje).days > policy.horizon_days:
            problemas.append(f"a data pedida está além do horizonte de {policy.horizon_days} dias.")
        elif not policy.abre_em(data):
            problemas.append("o espaço não funciona no dia da semana pedido.")
    return problemas


def _pergunta_normativa(criterios: dict, texto: str | None = None) -> str:
    """Build the question sent to retrieval, from the request and its criteria.

    O texto original entra porque os critérios estruturados descartam a finalidade —
    "evento externo com cobrança de ingresso" não sobrevive à extração, e é exatamente
    o tipo de pedido que precisa chegar ao Consultor.
    """
    partes = ["Regras de uso e reserva de espaços"]
    if texto:
        partes.append(f"— pedido: {texto}")
    if criterios.get("min_capacity"):
        partes.append(f"para {criterios['min_capacity']} pessoas")
    if criterios.get("attributes"):
        partes.append(f"com {', '.join(criterios['attributes'])}")
    partes.append("antecedência, duração máxima, quem pode reservar e vedações")
    return " ".join(partes)


def emitir_parecer(criterios: dict, *, texto: str = "", policy=None, top_k: int | None = None):
    """Agente 2 — analisa o pedido à luz da política interna e de referências externas.

    Divisão de trabalho deliberada. A **política interna** decide admissibilidade, por
    comparação exata — é regra cadastrada, não matéria de interpretação. O **corpus**
    de outras instituições entra como referência comparativa, nunca como norma que
    vincule o MP-GO. Ao agente cabe uma única decisão de julgamento: reconhecer quando
    o pedido toca algo que a política não cobre e que exige um humano.

    A rodada #02 mostrou por que a divisão precisa ser essa. Quando o agente recebia a
    tarefa de "emitir parecer" tendo como insumo apenas normas que não vinculam o órgão,
    ele concluía — corretamente — que não havia fundamento para decidir, e escalava
    tudo. Num caso, fez o oposto e barrou um pedido legítimo aplicando prazo de outra
    instituição. Os dois desfechos vinham da mesma instrução contraditória.

    Args:
        criterios: A saída do Agente 1.
        texto: O pedido como a pessoa escreveu, para que a finalidade não se perca.
        policy: A política vigente; carregada do banco quando omitida.
        top_k: Quantos trechos recuperar.

    Returns:
        tuple: O parecer e o registro do passo.
    """
    policy = policy or BookingPolicy.carregar()
    tokens: dict = {}

    with _Cronometro() as relogio:
        violacoes = _violacoes_de_politica(criterios, policy)
        if violacoes:
            parecer = {
                "parecer": PARECER_INADMISSIVEL,
                "fundamentacao": "Política de reserva vigente: " + " ".join(violacoes),
                "fontes": [{"origem": "política cadastrada"}],
                "origem": "politica",
            }
            passo = _registrar_passo(AGENTE_NORMATIVO, relogio, tokens, saida=parecer)
            return parecer, passo

        try:
            trechos = retrieval.search(
                _pergunta_normativa(criterios, texto), top_k or PARECER_TOP_K, hybrid=True
            )
        except (EmbeddingError, AIServiceError) as exc:
            passo = _registrar_passo(
                AGENTE_NORMATIVO, relogio, tokens, erro=f"{type(exc).__name__}: {exc}"
            )
            return {}, passo

        if not trechos:
            # Sem referência comparativa não há o que perguntar ao modelo — e a
            # ausência dela não restringe nada: quem autoriza é a política interna,
            # que já passou. Chamar o modelo aqui só gastaria token para ouvir que
            # ele não sabe.
            parecer = {
                "parecer": PARECER_ADMISSIVEL,
                "fundamentacao": (
                    "A política interna permite o pedido. Não há referência comparativa "
                    "na base para acrescentar."
                ),
                "fontes": [],
                "origem": "sem_referencia",
                "avisos": [],
            }
            passo = _registrar_passo(AGENTE_NORMATIVO, relogio, tokens, saida=parecer)
            return parecer, passo

        contexto = services._build_context(trechos)
        conteudo = (
            f"Pedido, como escrito: {texto or '(não informado)'}\n\n"
            f"Critérios extraídos: {_criterios_serializaveis(criterios)}\n\n"
            f"Trechos de referência:\n\n{contexto}"
        )
        try:
            bruto = services._run_json_completion(
                _PARECER_SYSTEM_PROMPT, conteudo, usage_sink=tokens
            )
        except AIServiceError as exc:
            passo = _registrar_passo(AGENTE_NORMATIVO, relogio, tokens, erro=str(exc))
            return {}, passo

    veredito = str(bruto.get("parecer", "")).strip().lower()
    avisos = []
    if veredito not in PARECERES_VALIDOS:
        avisos.append(f"parecer fora do vocabulário: {bruto.get('parecer')!r}")
        veredito = PARECER_ESCALONAR

    citadas = {int(n) for n in bruto.get("citacoes", []) if str(n).isdigit()}
    fontes = [
        {
            "posicao": posicao,
            "instituicao": trecho.institution,
            "documento": trecho.document_title,
            "url": trecho.source_url,
            "trecho": trecho.text,
        }
        for posicao, trecho in enumerate(trechos, start=1)
        if posicao in citadas
    ]

    if veredito == PARECER_INADMISSIVEL and not fontes:
        # Citação é exigida para restringir, não para permitir. Uma recusa sem trecho
        # apontado não vira aprovação silenciosa nem recusa automática: vira decisão
        # humana, que é o desfecho seguro quando o fundamento não se sustenta.
        avisos.append("recusa sem citação de trecho; encaminhada para decisão humana")
        veredito = PARECER_ESCALONAR

    parecer = {
        "parecer": veredito,
        "fundamentacao": bruto.get("fundamentacao", ""),
        "fontes": fontes,
        "origem": "corpus",
        "avisos": avisos,
    }
    passo = _registrar_passo(
        AGENTE_NORMATIVO,
        relogio,
        tokens,
        saida={**parecer, "fontes": [f["instituicao"] for f in fontes]},
    )
    return parecer, passo


# --------------------------------------------------------------------------- agente 3


def _espacos_candidatos(criterios: dict):
    """Return the active spaces that satisfy the structured criteria."""
    consulta = Space.objects.filter(is_active=True)
    if criterios.get("min_capacity"):
        consulta = consulta.filter(capacity__gte=criterios["min_capacity"])
    if criterios.get("max_capacity"):
        consulta = consulta.filter(capacity__lte=criterios["max_capacity"])
    for nome in criterios.get("attributes") or []:
        consulta = consulta.filter(space_attributes__attribute__name=nome)
    if criterios.get("location"):
        consulta = consulta.filter(location__icontains=criterios["location"])
    return consulta.distinct().order_by("capacity", "name")


def _janela_pedida(criterios: dict):
    """Return the requested interval as aware datetimes."""
    inicio = timezone.make_aware(
        datetime.datetime.combine(criterios["date"], criterios["start_time"])
    )
    return inicio, inicio + datetime.timedelta(minutes=criterios["duration_minutes"])


def _esta_livre(space, inicio, fim) -> bool:
    """Say whether the space is free in the interval, by the project's own rules."""
    if validators.active_reservations_overlapping(space, inicio, fim).exists():
        return False
    return not validators.maintenance_blocks_overlapping(space, inicio, fim).exists()


def _dias_para_alternativa(criterios: dict, policy) -> list:
    """Return the open days worth searching, starting at the requested one.

    Procurar alternativa só no dia pedido não serve quando o problema **é** o dia —
    um pedido para domingo não tem horário livre no domingo, e responder "nenhuma
    alternativa" é inútil quando a segunda-feira está inteira vaga.
    """
    hoje = timezone.localdate()
    inicio = max(criterios["date"], hoje)
    dias = []
    for deslocamento in range(DIAS_PARA_ALTERNATIVA + 1):
        dia = inicio + datetime.timedelta(days=deslocamento)
        if (dia - hoje).days > policy.horizon_days:
            break
        if policy.abre_em(dia):
            dias.append(dia)
    return dias


def _alternativas(criterios: dict, policy, *, excluir=None) -> list[dict]:
    """Return up to ``MAX_ALTERNATIVAS`` other windows that fit the request.

    Varre dia a dia, do pedido em diante, e dentro de cada dia percorre os espaços
    candidatos — assim a primeira opção oferecida é sempre a mais próxima do que a
    pessoa pediu.
    """
    duracao = criterios["duration_minutes"]
    candidatos = [
        space
        for space in _espacos_candidatos(criterios)
        if excluir is None or space.pk != excluir.pk
    ]
    encontradas = []
    for dia in _dias_para_alternativa(criterios, policy):
        for space in candidatos:
            slots = availability.marcar_cabimento(
                availability.gerar_slots(space, dia, policy), duracao
            )
            cabivel = next((slot for slot in slots if slot["cabe"]), None)
            if cabivel is None:
                continue
            encontradas.append(
                {
                    "espaco": space.name,
                    "espaco_id": space.pk,
                    "capacidade": space.capacity,
                    "inicio": timezone.localtime(cabivel["inicio"]).strftime("%d/%m %H:%M"),
                    "fim": timezone.localtime(cabivel["fim_da_reserva"]).strftime("%H:%M"),
                }
            )
            if len(encontradas) == MAX_ALTERNATIVAS:
                return encontradas
    return encontradas


def alocar(criterios: dict, parecer: dict, user, *, policy=None):
    """Agente 3 — reserva, propõe alternativas ou escala ao administrador.

    Args:
        criterios: A saída do Agente 1.
        parecer: A saída do Agente 2.
        user: Quem fez o pedido.
        policy: A política vigente; carregada do banco quando omitida.

    Returns:
        tuple: Um dicionário com ``decisao``, ``mensagem``, ``alternativas`` e
        ``reserva_id``, mais o registro do passo.
    """
    policy = policy or BookingPolicy.carregar()

    with _Cronometro() as relogio:
        if parecer.get("parecer") == PARECER_ESCALONAR:
            resultado = {
                "decisao": DECISAO_ESCALONAMENTO,
                "mensagem": (
                    "O pedido toca ponto que a política interna não cobre. Encaminhado ao "
                    "administrador com o pedido original, os critérios extraídos e as "
                    "referências consultadas."
                ),
                "alternativas": [],
                "reserva_id": None,
            }
            passo = _registrar_passo(AGENTE_ALOCADOR, relogio, saida=resultado)
            return resultado, passo

        inicio, fim = _janela_pedida(criterios)
        candidatos = list(_espacos_candidatos(criterios))

        if parecer.get("parecer") == PARECER_INADMISSIVEL:
            opcoes = _alternativas(criterios, policy) if candidatos else []
            resultado = {
                "decisao": DECISAO_ALTERNATIVAS if opcoes else DECISAO_ESCALONAMENTO,
                "mensagem": (
                    "O pedido não é admissível como está. "
                    + (
                        "Seguem alternativas dentro da regra."
                        if opcoes
                        else "Não há alternativa automática; encaminhado ao administrador."
                    )
                ),
                "alternativas": opcoes,
                "reserva_id": None,
            }
            passo = _registrar_passo(AGENTE_ALOCADOR, relogio, saida=resultado)
            return resultado, passo

        escolhido = next((space for space in candidatos if _esta_livre(space, inicio, fim)), None)
        if escolhido is not None:
            try:
                reserva = create_reservation(user, escolhido, inicio, fim)
            except Exception as exc:  # noqa: BLE001 — a causa entra no relatório
                resultado = {
                    "decisao": DECISAO_ESCALONAMENTO,
                    "mensagem": f"A reserva foi recusada na validação: {exc}",
                    "alternativas": [],
                    "reserva_id": None,
                }
                passo = _registrar_passo(
                    AGENTE_ALOCADOR,
                    relogio,
                    saida=resultado,
                    erro=f"{type(exc).__name__}: {exc}",
                )
                return resultado, passo

            resultado = {
                "decisao": DECISAO_RESERVA,
                "mensagem": (
                    f"Reservado: {escolhido.name}, "
                    f"{timezone.localtime(inicio).strftime('%d/%m %H:%M')} às "
                    f"{timezone.localtime(fim).strftime('%H:%M')}."
                ),
                "alternativas": [],
                "reserva_id": reserva.pk,
            }
            passo = _registrar_passo(AGENTE_ALOCADOR, relogio, saida=resultado)
            return resultado, passo

        opcoes = _alternativas(criterios, policy)
        resultado = {
            "decisao": DECISAO_ALTERNATIVAS if opcoes else DECISAO_ESCALONAMENTO,
            "mensagem": (
                "Nenhum espaço livre no horário pedido. Seguem alternativas."
                if opcoes
                else "Nenhum espaço atende ao pedido neste dia; encaminhado ao administrador."
            ),
            "alternativas": opcoes,
            "reserva_id": None,
        }
        passo = _registrar_passo(AGENTE_ALOCADOR, relogio, saida=resultado)
        return resultado, passo


# --------------------------------------------------------------------------- pipeline


def executar_pipeline(texto: str, user, *, policy=None) -> ResultadoDoPipeline:
    """Roda os três agentes em sequência e devolve a decisão fundamentada.

    Duas interrupções previstas, conforme a especificação: falta de campo essencial
    para o fluxo no Agente 1, e parecer de decisão humana leva o Agente 3 direto à
    escalação, sem tentar reservar.

    Args:
        texto: O pedido em linguagem natural.
        user: Quem fez o pedido.
        policy: A política vigente; carregada do banco quando omitida.

    Returns:
        ResultadoDoPipeline: A decisão, o rastro de cada agente e o custo de cada etapa.
    """
    policy = policy or BookingPolicy.carregar()
    resultado = ResultadoDoPipeline(pedido=texto, decisao=DECISAO_ERRO, mensagem="")

    criterios, passo1 = interpretar_pedido(texto, policy=policy)
    resultado.passos.append(passo1)
    if passo1.erro:
        resultado.mensagem = f"O Intérprete de Solicitação falhou: {passo1.erro}"
        return resultado
    resultado.criterios = criterios

    if criterios.get("faltando"):
        resultado.decisao = DECISAO_ESCLARECIMENTO
        resultado.mensagem = _anexar_avisos_de_catalogo(
            pergunta_de_esclarecimento(criterios), criterios
        )
        return resultado

    parecer, passo2 = emitir_parecer(criterios, texto=texto, policy=policy)
    resultado.passos.append(passo2)
    if passo2.erro:
        resultado.mensagem = f"O Consultor Normativo falhou: {passo2.erro}"
        return resultado
    resultado.parecer = parecer

    decisao, passo3 = alocar(criterios, parecer, user, policy=policy)
    resultado.passos.append(passo3)
    resultado.decisao = decisao["decisao"]
    resultado.mensagem = _anexar_avisos_de_catalogo(decisao["mensagem"], criterios)
    resultado.alternativas = decisao["alternativas"]
    resultado.reserva_id = decisao["reserva_id"]
    return resultado
