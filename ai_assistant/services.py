"""Services that call the Groq LLM API to power AI-assisted features.

This module encapsulates all interaction with the external LLM provider so
that views stay thin and the AI logic can be unit tested by mocking a single
function (:func:`_run_json_completion`).
"""

import datetime
import json
import logging
import re
import unicodedata

from django.conf import settings
from groq import (
    APIConnectionError,
    AuthenticationError,
    Groq,
    GroqError,
    RateLimitError,
)

from ai_assistant.exceptions import AIServiceError
from core.seeds.attributes import DEFAULT_ATTRIBUTES
from knowledge import retrieval
from knowledge.embedding import EmbeddingError

logger = logging.getLogger(__name__)

#: Generic fallback when the Groq API fails for an unclassified reason.
GENERIC_GROQ_FAILURE_MESSAGE = (
    "Não foi possível obter uma resposta do assistente agora. Tente novamente em instantes."
)

#: Matches Groq rate-limit hints like "Please try again in 33m50.4s".
_RETRY_AFTER_PATTERN = re.compile(
    r"try again in (?:(\d+)m)?([\d.]+)s",
    re.IGNORECASE,
)

MAINTENANCE_CATEGORIES = [
    "eletrica",
    "hidraulica",
    "limpeza",
    "ti_equipamentos",
    "mobiliario",
    "seguranca",
    "outros",
]

# Popular synonyms (normalized, without accents) → canonical Attribute.name values.
ATTRIBUTE_SYNONYMS: dict[str, str] = {
    # Wi-Fi
    "internet": "Wi-Fi",
    "wifi": "Wi-Fi",
    "wi fi": "Wi-Fi",
    "wireless": "Wi-Fi",
    "rede": "Wi-Fi",
    "rede sem fio": "Wi-Fi",
    "rede wifi": "Wi-Fi",
    "acesso a internet": "Wi-Fi",
    "acesso a rede": "Wi-Fi",
    "net": "Wi-Fi",
    "conexao": "Wi-Fi",
    "banda larga": "Wi-Fi",
    # Ar-condicionado
    "ar": "Ar-condicionado",
    "ar condicionado": "Ar-condicionado",
    "ar cond": "Ar-condicionado",
    "ac": "Ar-condicionado",
    "refrigeracao": "Ar-condicionado",
    "climatizacao": "Ar-condicionado",
    "clima": "Ar-condicionado",
    "sala refrigerada": "Ar-condicionado",
    "frio": "Ar-condicionado",
    # Projetor
    "projetor": "Projetor",
    "projector": "Projetor",
    "data show": "Projetor",
    "datashow": "Projetor",
    "beamer": "Projetor",
    "canhao": "Projetor",
    "apresentacao": "Projetor",
    "slides": "Projetor",
    # TV
    "tv": "TV",
    "televisao": "TV",
    "televisor": "TV",
    "tela": "TV",
    "tela grande": "TV",
    "monitor": "TV",
    "smart tv": "TV",
    # Webcam
    "webcam": "Webcam",
    "camera": "Webcam",
    "camera web": "Webcam",
    "camera usb": "Webcam",
    "cam": "Webcam",
    "para call": "Webcam",
    # Quadro branco
    "quadro": "Quadro branco",
    "quadro branco": "Quadro branco",
    "whiteboard": "Quadro branco",
    "lousa": "Quadro branco",
    "pizarra": "Quadro branco",
    "quadro para escrever": "Quadro branco",
    "flip chart": "Quadro branco",
    "flipchart": "Quadro branco",
    # Videoconferência
    "videoconferencia": "Videoconferência",
    "video conferencia": "Videoconferência",
    "videochamada": "Videoconferência",
    "chamada de video": "Videoconferência",
    "reuniao online": "Videoconferência",
    "call": "Videoconferência",
    "meet": "Videoconferência",
    "google meet": "Videoconferência",
    "zoom": "Videoconferência",
    "teams": "Videoconferência",
    "webex": "Videoconferência",
}

_KNOWN_ATTRIBUTES_LIST = ", ".join(DEFAULT_ATTRIBUTES)
_CATALOG_ATTRIBUTE_NAMES = frozenset(DEFAULT_ATTRIBUTES)

_ROOM_SEARCH_SYSTEM_PROMPT = (
    "Você é um assistente que converte pedidos em linguagem natural sobre reserva de "
    "salas em filtros estruturados. Responda SOMENTE com um JSON válido, sem texto "
    "adicional, no formato exato: "
    '{"min_capacity": <int ou null>, "max_capacity": <int ou null>, '
    '"attributes": [<string>, ...], "location": <string ou null>, '
    '"summary": <string curta explicando o que foi entendido, em português>}. '
    f"Os itens de 'attributes' DEVEM sair EXCLUSIVAMENTE deste catálogo: "
    f"{_KNOWN_ATTRIBUTES_LIST}. Não invente equipamentos fora da lista. "
    "Mapeie sinônimos populares para o catálogo (ex.: 'internet'/'wifi'/'rede' → "
    "'Wi-Fi'; 'datashow'/'slides' → 'Projetor'; 'meet'/'zoom'/'call' → "
    "'Videoconferência'; 'lousa' → 'Quadro branco'; 'ac' → 'Ar-condicionado'). "
    "Capacidade — escolha o campo certo conforme a intenção:\n"
    "- Piso (min_capacity): 'para N pessoas', 'pelo menos N', 'a partir de N', "
    "'com capacidade de N' quando o sentido é caber no mínimo N.\n"
    "- Teto (max_capacity): 'até N', 'no máximo N', 'capacidade máxima de N', "
    "'para no máximo N pessoas'. NÃO coloque o teto em min_capacity.\n"
    "- Ambos: 'entre A e B', 'de A a B'.\n"
    "- Exato: 'exatamente N lugares', 'com N lugares' → min_capacity=N e "
    "max_capacity=N.\n"
    "Tamanho aproximado sem número: 'pequena'→max_capacity=6; 'média'→"
    "min_capacity=6 e max_capacity=15; 'grande'→min_capacity=12; "
    "'auditório'→min_capacity=30.\n"
    "Para location, prefira fragmentos do cadastro real: 'Bloco A', 'Bloco B', "
    "'Bloco C', 'Térreo', ou o andar em formato numérico curto (ex.: '2º', '3º'). "
    "Se algo não for mencionado, use null ou lista vazia."
)

#: Acrescentado ao prompt quando o chamador informa o contexto temporal.
#:
#: Sem uma data de referência explícita, "amanhã" não significa nada para o
#: modelo: ele não sabe que dia é hoje. E sem a janela de funcionamento, "de
#: manhã" viraria um palpite. Os dois entram como fato, não como sugestão.
_PROMPT_TEMPORAL = (
    "\nO JSON deve trazer TAMBÉM estes três campos: "
    '"date": <"AAAA-MM-DD" ou null>, "start_time": <"HH:MM" ou null>, '
    '"duration_minutes": <int ou null>.\n'
    "Hoje é {hoje} ({dia_da_semana}). Resolva expressões relativas a partir "
    "desta data: 'hoje', 'amanhã', 'depois de amanhã', 'segunda que vem', "
    "'dia 12'. Nunca devolva uma data no passado.\n"
    "O expediente vai das {abertura} às {fechamento}. Períodos do dia: "
    "'de manhã' → {abertura}; 'à tarde' → 13:00; 'no fim do dia' → duas horas "
    "antes do fechamento. Horário explícito ('às 14h', '14:30') vence o período.\n"
    "duration_minutes vem de 'por N horas', 'reunião de N minutos', 'a manhã "
    "toda'. Sem menção, use null — não invente duração.\n"
    "Se a pessoa não falar de tempo, os três campos são null."
)


_MAINTENANCE_SYSTEM_PROMPT = (
    "Você é um classificador de motivos de bloqueio de manutenção de salas. Dado um "
    "texto curto descrevendo o motivo, classifique em exatamente uma das categorias: "
    f"{', '.join(MAINTENANCE_CATEGORIES)}. "
    "Exemplos: lâmpada/tomada/fio → eletrica; vazamento/torneira/encanamento → "
    "hidraulica; limpeza/faxina/pós-evento → limpeza; projetor/TV/Wi-Fi/computador → "
    "ti_equipamentos; cadeira/mesa/armário → mobiliario; fechadura/alarme/câmera de "
    "segurança → seguranca; caso ambíguo → outros. "
    "Responda SOMENTE com um JSON válido, sem texto adicional, no formato exato: "
    '{"category": <uma das categorias listadas, em minúsculas>, '
    '"confidence": <"alta", "media" ou "baixa">, '
    '"justification": <string curta em português explicando a escolha>}.'
)


def _prompt_de_busca(contexto=None):
    """Return the room-search prompt, with temporal context when available.

    Args:
        contexto: Dicionário com ``hoje``, ``dia_da_semana``, ``abertura`` e
            ``fechamento``. Quando ausente, o prompt não pede campos de tempo —
            perguntar por data sem dizer que dia é hoje só produziria chute.

    Returns:
        str: O prompt de sistema.
    """
    if not contexto:
        return _ROOM_SEARCH_SYSTEM_PROMPT
    return _ROOM_SEARCH_SYSTEM_PROMPT + _PROMPT_TEMPORAL.format(**contexto)


def _format_retry_wait(exc: RateLimitError) -> str:
    """Extract a short Portuguese wait hint from a Groq rate-limit error.

    Args:
        exc: The rate-limit exception raised by the Groq client.

    Returns:
        A phrase such as " Tente de novo em cerca de 34 minutos." or an empty
        string when the retry hint cannot be parsed.
    """
    match = _RETRY_AFTER_PATTERN.search(str(exc))
    if not match:
        return ""

    minutes = int(match.group(1) or 0)
    seconds = float(match.group(2))
    total_minutes = max(1, minutes + int(seconds // 60) + (1 if seconds % 60 else 0))
    if total_minutes == 1:
        return " Tente de novo em cerca de 1 minuto."
    return f" Tente de novo em cerca de {total_minutes} minutos."


def _technical_detail_for_groq_error(exc: GroqError) -> str:
    """Build a console/log-friendly detail string from a Groq exception.

    Args:
        exc: The exception raised by the Groq SDK.

    Returns:
        A compact technical summary including exception type and message.
    """
    return f"{type(exc).__name__}: {exc}"


def _ai_error_from_groq(exc: GroqError) -> AIServiceError:
    """Map a Groq client exception to an AIServiceError with friendly + technical text.

    Args:
        exc: The exception raised by the Groq SDK.

    Returns:
        An AIServiceError ready to surface in the UI and browser console.
    """
    technical_detail = _technical_detail_for_groq_error(exc)

    if isinstance(exc, RateLimitError):
        return AIServiceError(
            "O assistente recebeu muitas consultas e precisa de uma pausa."
            f"{_format_retry_wait(exc)}",
            technical_detail=technical_detail,
        )
    if isinstance(exc, AuthenticationError):
        return AIServiceError(
            "O assistente não está disponível no momento. Se continuar assim, fale com o suporte.",
            technical_detail=technical_detail,
        )
    if isinstance(exc, APIConnectionError):
        return AIServiceError(
            "Não conseguimos falar com o assistente agora. Confira sua conexão e tente de novo.",
            technical_detail=technical_detail,
        )
    return AIServiceError(GENERIC_GROQ_FAILURE_MESSAGE, technical_detail=technical_detail)


def _get_client() -> Groq:
    """Build a Groq client using the configured API key.

    Returns:
        A configured Groq client instance.

    Raises:
        AIServiceError: if no API key is configured in the environment.
    """
    if not settings.GROQ_API_KEY:
        logger.error("GROQ_API_KEY não configurada; não é possível chamar o serviço de IA.")
        raise AIServiceError(
            "O assistente não está disponível no momento. Se continuar assim, fale com o suporte.",
            technical_detail="GROQ_API_KEY ausente na configuração do ambiente.",
        )
    return Groq(api_key=settings.GROQ_API_KEY)


def _run_json_completion(system_prompt: str, user_content: str) -> dict:
    """Call the Groq chat completion API and parse a JSON object from the response.

    Args:
        system_prompt: instructions describing the expected output format.
        user_content: the user-provided text to process.

    Returns:
        The parsed JSON response as a dict.

    Raises:
        AIServiceError: if the API call fails or returns invalid JSON.
    """
    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    except GroqError as exc:
        logger.exception("Falha ao chamar a API da Groq.")
        raise _ai_error_from_groq(exc) from None

    raw_content = completion.choices[0].message.content
    try:
        return json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        logger.error("Resposta da IA não é um JSON válido: %r", raw_content)
        raise AIServiceError(
            "O assistente devolveu uma resposta incompleta. Tente novamente.",
            technical_detail=f"JSON inválido na resposta do modelo: {raw_content!r}",
        ) from None


def _normalize_lookup_key(value: str) -> str:
    """Normalize text for synonym/catalog lookup (lowercase, no accents/hyphens)."""
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_accents.replace("-", " ").split())


def normalize_room_search_attributes(attributes: list) -> list[str]:
    """Map free-form attribute labels onto canonical catalog names when possible.

    Args:
        attributes: raw attribute labels returned by the LLM (e.g. ``internet``).

    Returns:
        Deduplicated list of catalog attribute names. Labels that cannot be mapped
        to :data:`DEFAULT_ATTRIBUTES` are discarded so invented equipment does not
        wipe out search results.
    """
    catalog_by_key = {_normalize_lookup_key(name): name for name in DEFAULT_ATTRIBUTES}
    normalized_attributes: list[str] = []
    seen: set[str] = set()

    for raw_attribute in attributes:
        if not isinstance(raw_attribute, str):
            continue
        trimmed = raw_attribute.strip()
        if not trimmed:
            continue

        lookup_key = _normalize_lookup_key(trimmed)
        canonical_name = ATTRIBUTE_SYNONYMS.get(lookup_key) or catalog_by_key.get(lookup_key)
        if canonical_name is None:
            canonical_name = next(
                (
                    catalog_name
                    for catalog_key, catalog_name in catalog_by_key.items()
                    if lookup_key in catalog_key or catalog_key in lookup_key
                ),
                None,
            )

        if canonical_name is None or canonical_name not in _CATALOG_ATTRIBUTE_NAMES:
            logger.info("Ignorando atributo fora do catálogo retornado pela IA: %r", trimmed)
            continue

        if canonical_name not in seen:
            seen.add(canonical_name)
            normalized_attributes.append(canonical_name)

    return normalized_attributes


def _coerce_capacity(value) -> int | None:
    """Convert an LLM capacity value to a positive int, or ``None`` if invalid."""
    if value is None or value == "":
        return None
    try:
        capacity = int(value)
    except (TypeError, ValueError):
        return None
    if capacity < 1:
        return None
    return capacity


def _coerce_date(valor, contexto, avisos):
    """Convert an LLM date to a usable ``date``, or ``None``.

    A regra de negócio não é do modelo: uma data no passado ou além do horizonte
    de agendamento é recusada aqui, do lado de cá. Quando isso acontece, o
    motivo entra em ``avisos`` — descartar em silêncio deixaria o resumo da IA
    dizendo "amanhã" enquanto a tela mostra hoje.

    Args:
        valor: O que o modelo devolveu.
        contexto: O contexto temporal, com ``hoje_date`` e ``horizonte``.
        avisos: Lista onde registrar o que foi descartado e por quê.

    Returns:
        datetime.date | None: A data utilizável.
    """
    if not valor or not isinstance(valor, str):
        return None
    try:
        escolhida = datetime.datetime.strptime(valor.strip(), "%Y-%m-%d").date()
    except ValueError:
        avisos.append("Não consegui entender a data pedida.")
        return None

    hoje = contexto["hoje_date"]
    if escolhida < hoje:
        avisos.append("A data pedida já passou; mostrando hoje.")
        return None
    if escolhida > hoje + datetime.timedelta(days=contexto["horizonte"]):
        avisos.append(
            f"Só é possível reservar com até {contexto['horizonte']} dias de "
            "antecedência; mostrando hoje."
        )
        return None
    return escolhida


def _coerce_time(valor, contexto, avisos):
    """Convert an LLM time to a ``time`` inside the operating window, or ``None``.

    Args:
        valor: O que o modelo devolveu.
        contexto: O contexto temporal, com ``abertura_time`` e ``fechamento_time``.
        avisos: Lista onde registrar o que foi descartado e por quê.

    Returns:
        datetime.time | None: O horário utilizável.
    """
    if not valor or not isinstance(valor, str):
        return None
    try:
        horario = datetime.datetime.strptime(valor.strip(), "%H:%M").time()
    except ValueError:
        avisos.append("Não consegui entender o horário pedido.")
        return None

    if not (contexto["abertura_time"] <= horario < contexto["fechamento_time"]):
        avisos.append(
            f"O horário pedido está fora do expediente "
            f"({contexto['abertura']} às {contexto['fechamento']})."
        )
        return None
    return horario


def _coerce_duration(valor, contexto, avisos):
    """Convert an LLM duration to a value the policy accepts, or ``None``.

    Não arredonda para o limite mais próximo: encurtar ou esticar a reunião de
    alguém sem avisar é pior do que ignorar o pedido e deixar a pessoa escolher.

    Args:
        valor: O que o modelo devolveu.
        contexto: O contexto temporal, com ``duracao_minima`` e ``duracao_maxima``.
        avisos: Lista onde registrar o que foi descartado e por quê.

    Returns:
        int | None: A duração utilizável, em minutos.
    """
    if valor is None or valor == "":
        return None
    try:
        minutos = int(valor)
    except (TypeError, ValueError):
        return None
    if minutos < contexto["duracao_minima"] or minutos > contexto["duracao_maxima"]:
        avisos.append(
            f"A duração pedida está fora do permitido "
            f"(de {contexto['duracao_minima']} a {contexto['duracao_maxima']} minutos)."
        )
        return None
    return minutos


def extract_room_search_filters(query: str, contexto_temporal: dict | None = None) -> dict:
    """Use an LLM to turn a natural-language room request into structured search filters.

    Args:
        query: free-text description of the desired space, e.g. "sala para 8
            pessoas com projetor amanhã de manhã".
        contexto_temporal: quando informado, habilita a extração de data e
            horário. Precisa trazer ``hoje``, ``hoje_date``, ``dia_da_semana``,
            ``abertura``, ``abertura_time``, ``fechamento``, ``fechamento_time``,
            ``horizonte``, ``duracao_minima`` e ``duracao_maxima``. Sem ele o
            comportamento é exatamente o de antes — "amanhã" não significa nada
            para um modelo que não sabe que dia é hoje.

    Returns:
        A dict with keys ``min_capacity``, ``max_capacity``, ``attributes``,
        ``location``, ``summary``, ``date``, ``start_time``, ``duration_minutes``
        and ``avisos``. Attribute labels are normalized to catalog names when
        possible (e.g. ``internet`` → ``Wi-Fi``). Os três campos temporais são
        ``None`` quando não houve contexto ou quando o valor devolvido não
        passou na validação — e, nesse caso, ``avisos`` explica o motivo.
    """
    logger.info("Extraindo filtros de busca de sala a partir de linguagem natural.")
    data = _run_json_completion(_prompt_de_busca(contexto_temporal), query)

    avisos: list[str] = []
    if contexto_temporal:
        data_pedida = _coerce_date(data.get("date"), contexto_temporal, avisos)
        horario = _coerce_time(data.get("start_time"), contexto_temporal, avisos)
        duracao = _coerce_duration(data.get("duration_minutes"), contexto_temporal, avisos)
    else:
        data_pedida = horario = duracao = None

    return {
        "min_capacity": _coerce_capacity(data.get("min_capacity")),
        "max_capacity": _coerce_capacity(data.get("max_capacity")),
        "attributes": normalize_room_search_attributes(data.get("attributes") or []),
        "location": data.get("location"),
        "summary": data.get("summary", ""),
        "date": data_pedida,
        "start_time": horario,
        "duration_minutes": duracao,
        "avisos": avisos,
    }


def classify_maintenance_reason(reason: str) -> dict:
    """Use an LLM to classify a free-text maintenance reason into a fixed category.

    Args:
        reason: free-text reason for a maintenance block, e.g. "Troca de
            lâmpadas queimadas no teto".

    Returns:
        A dict with keys ``category`` (one of :data:`MAINTENANCE_CATEGORIES`),
        ``confidence`` and ``justification``.
    """
    logger.info("Classificando motivo de manutenção via IA.")
    data = _run_json_completion(_MAINTENANCE_SYSTEM_PROMPT, reason)
    category = data.get("category")
    if category not in MAINTENANCE_CATEGORIES:
        logger.warning("Categoria fora do conjunto esperado retornada pela IA: %r", category)
        category = "outros"
    return {
        "category": category,
        "confidence": data.get("confidence", "baixa"),
        "justification": data.get("justification", ""),
    }


_DOCUMENT_QA_SYSTEM_PROMPT = (
    "Você é um assistente que responde perguntas sobre normas de uso de espaços "
    "físicos (auditórios, salas de reunião, cessão a terceiros) em instituições "
    "públicas brasileiras.\n\n"
    "Regras obrigatórias:\n"
    "1. Responda EXCLUSIVAMENTE com base nos trechos numerados fornecidos. Não use "
    "conhecimento próprio nem complete lacunas por conta própria.\n"
    "2. Ao afirmar uma regra, diga de qual instituição ela é. As normas variam entre "
    "instituições e uma resposta sem essa atribuição é enganosa.\n"
    "3. Quando os trechos divergirem entre si, apresente as diferenças em vez de "
    "escolher uma versão.\n"
    "4. Se os trechos não permitirem responder, diga isso claramente. Não invente.\n"
    "5. Cite os trechos usados pelo número, no formato [1], [2].\n"
    "6. Responda em português do Brasil, de forma direta e objetiva.\n"
    "7. Se houver histórico da conversa, interprete a pergunta atual como "
    "continuação: resolva pronomes e elipses (ex.: 'e na UFBA?', 'e a taxa?', "
    "'comparando com a anterior') usando o assunto das perguntas anteriores, "
    "mas continue respondendo só com os trechos numerados desta rodada."
)

_FOLLOWUP_REWRITE_SYSTEM_PROMPT = (
    "Você reescreve perguntas de acompanhamento sobre normas de uso de espaços "
    "públicos. Dado o histórico e a pergunta atual (que pode ser elíptica, como "
    "'e na UFBA?' ou 'e a taxa?'), produza UMA pergunta completa e autônoma, "
    "adequada para busca documental, sem depender do histórico para ser "
    "entendida. Preserve a intenção e a instituição/tema implícitos. "
    "Responda SOMENTE com a pergunta reescrita, sem aspas, prefixo nem explicação."
)

#: Resposta padrão quando o corpus não tem nada relacionado à pergunta. Evita
#: chamar o LLM sem contexto, situação em que ele tenderia a responder de memória.
NO_CONTEXT_ANSWER = (
    "Não encontrei nada na base de normas que responda a essa pergunta. "
    "O corpus cobre regulamentos de uso de auditórios, salas e cessão de espaços "
    "em instituições públicas."
)

#: Minimum length accepted for an LLM-rewritten follow-up before falling back.
MIN_FOLLOWUP_REWRITE_LENGTH = 8


def _run_text_completion(system_prompt: str, user_content: str) -> str:
    """Call the Groq chat completion API and return the raw text answer.

    Args:
        system_prompt: Instructions describing how to answer.
        user_content: The question plus its retrieved context.

    Returns:
        str: The model's answer.

    Raises:
        AIServiceError: If the API call fails or returns an empty answer.
    """
    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
        )
    except GroqError as exc:
        logger.exception("Falha ao chamar a API da Groq.")
        raise _ai_error_from_groq(exc) from None

    answer = (completion.choices[0].message.content or "").strip()
    if not answer:
        raise AIServiceError(
            "O assistente devolveu uma resposta incompleta. Tente novamente.",
            technical_detail=f"Resposta vazia do modelo {settings.GROQ_MODEL}.",
        )
    return answer


def _build_context(chunks: list) -> str:
    """Format retrieved passages as a numbered context block.

    The institution is repeated on every excerpt so the model can attribute each rule
    without having to infer provenance from the text.

    Args:
        chunks: Retrieved passages, best first.

    Returns:
        str: The context block sent to the model.
    """
    return "\n\n".join(
        f"[{position}] {chunk.institution} — {chunk.document_title}\n{chunk.text}"
        for position, chunk in enumerate(chunks, start=1)
    )


def _build_history(history: list | None) -> str:
    """Format previous turns as a conversation preamble.

    Args:
        history: Previous turns, most recent first, each with ``question`` and
            ``answer``.

    Returns:
        str: The preamble, or an empty string when there is no history.
    """
    if not history:
        return ""

    trocas = "\n\n".join(
        f"Pergunta anterior: {turn.question}\nResposta anterior: {turn.answer}"
        for turn in reversed(history)
    )
    return (
        "Contexto da conversa até aqui (use apenas para entender referências "
        f"implícitas na pergunta atual, como 'e na UFBA?'):\n\n{trocas}\n\n---\n\n"
    )


def _fallback_search_query(question: str, history: list) -> str:
    """Build a retrieval query by concatenating the latest turn with the follow-up."""
    anterior = history[0]
    return f"{anterior.question} {question}".strip()


def rewrite_followup_question(question: str, history: list | None) -> str:
    """Turn an elliptical follow-up into a standalone search query.

    Without this step, retrieval for questions like ``e na UFS?`` returns nothing
    useful, and the answer path refuses to call the LLM — correctly, to avoid
    hallucination, but the conversation then feels broken.

    Args:
        question: The user's current question.
        history: Previous turns, most recent first.

    Returns:
        str: A self-contained query for retrieval. Falls back to concatenating
        the previous question when the rewrite call fails.
    """
    if not history:
        return question

    trocas = "\n".join(f"- {turn.question}" for turn in reversed(history))
    user_content = f"Histórico recente:\n{trocas}\n\nPergunta atual: {question}"
    try:
        reescrita = _run_text_completion(_FOLLOWUP_REWRITE_SYSTEM_PROMPT, user_content)
    except AIServiceError:
        logger.warning(
            "Falha ao reescrever follow-up; usando concatenação com o turno anterior.",
        )
        return _fallback_search_query(question, history)

    reescrita = reescrita.strip().strip('"').strip("'")
    if len(reescrita) < MIN_FOLLOWUP_REWRITE_LENGTH:
        return _fallback_search_query(question, history)
    return reescrita


def answer_from_documents(
    question: str,
    top_k: int | None = None,
    *,
    hybrid: bool = True,
    history: list | None = None,
) -> dict:
    """Answer a question about the normative corpus, citing the passages used.

    Retrieval-augmented generation: the corpus is searched first, and only the
    retrieved passages are given to the model. When retrieval comes back empty the
    model is not called at all — without context it would answer from memory, which is
    exactly what this feature exists to avoid.

    When ``history`` is provided, follow-ups are rewritten into a standalone query
    before retrieval so elliptical questions still find relevant passages.

    Args:
        question: Natural-language question.
        top_k: How many passages to retrieve. Defaults to ``RAG_TOP_K``.
        hybrid: Whether to combine semantic and lexical search.
        history: Previous turns of the conversation, most recent first.

    Returns:
        dict: With keys ``answer``, ``sources`` and ``used_context``.

    Raises:
        AIServiceError: If retrieval or the LLM call fails.
    """
    logger.info("Respondendo pergunta sobre a base de normas.")

    search_query = rewrite_followup_question(question, history)

    try:
        chunks = retrieval.search(search_query, top_k, hybrid=hybrid)
    except EmbeddingError as exc:
        logger.warning("Falha ao gerar embedding da pergunta: %s", exc)
        raise AIServiceError(
            "Não foi possível analisar sua pergunta agora. Tente novamente em instantes.",
            technical_detail=f"EmbeddingError: {exc}",
        ) from exc

    if not chunks:
        return {"answer": NO_CONTEXT_ANSWER, "sources": [], "used_context": False}

    prompt = (
        f"{_build_history(history)}"
        f"Pergunta: {question}\n\nTrechos disponíveis:\n\n{_build_context(chunks)}"
    )
    answer = _run_text_completion(_DOCUMENT_QA_SYSTEM_PROMPT, prompt)

    return {
        "answer": answer,
        "sources": [
            {
                "position": position,
                "institution": chunk.institution,
                "document": chunk.document_title,
                "url": chunk.source_url,
                "excerpt": chunk.text,
                "score": round(chunk.score, 6),
            }
            for position, chunk in enumerate(chunks, start=1)
        ],
        "used_context": True,
    }
