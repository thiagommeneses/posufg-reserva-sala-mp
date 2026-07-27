"""Services that call the Groq LLM API to power AI-assisted features.

This module encapsulates all interaction with the external LLM provider so
that views stay thin and the AI logic can be unit tested by mocking a single
function (:func:`_run_json_completion`).
"""

import json
import logging
import unicodedata

from django.conf import settings
from groq import Groq, GroqError

from ai_assistant.exceptions import AIServiceError
from core.seeds.attributes import DEFAULT_ATTRIBUTES
from knowledge import retrieval
from knowledge.embedding import EmbeddingError

logger = logging.getLogger(__name__)

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
    '{"min_capacity": <int ou null>, "attributes": [<string>, ...], '
    '"location": <string ou null>, "summary": <string curta explicando o que foi '
    "entendido, em português>}. "
    f"Os itens de 'attributes' DEVEM sair EXCLUSIVAMENTE deste catálogo: "
    f"{_KNOWN_ATTRIBUTES_LIST}. Não invente equipamentos fora da lista. "
    "Mapeie sinônimos populares para o catálogo (ex.: 'internet'/'wifi'/'rede' → "
    "'Wi-Fi'; 'datashow'/'slides' → 'Projetor'; 'meet'/'zoom'/'call' → "
    "'Videoconferência'; 'lousa' → 'Quadro branco'; 'ac' → 'Ar-condicionado'). "
    "Para tamanho aproximado, use min_capacity assim quando o usuário não informar "
    "número: 'pequena'≈4, 'média'≈6, 'grande'≈12, 'auditório'≈30. "
    "Para location, prefira fragmentos do cadastro real: 'Bloco A', 'Bloco B', "
    "'Bloco C', 'Térreo', ou o andar em formato numérico curto (ex.: '2º', '3º'). "
    "Se algo não for mencionado, use null ou lista vazia."
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


def _get_client() -> Groq:
    """Build a Groq client using the configured API key.

    Returns:
        A configured Groq client instance.

    Raises:
        AIServiceError: if no API key is configured in the environment.
    """
    if not settings.GROQ_API_KEY:
        logger.error("GROQ_API_KEY não configurada; não é possível chamar o serviço de IA.")
        raise AIServiceError("Serviço de IA não configurado (GROQ_API_KEY ausente).")
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
    except GroqError:
        logger.exception("Falha ao chamar a API da Groq.")
        raise AIServiceError("Não foi possível consultar o serviço de IA no momento.") from None

    raw_content = completion.choices[0].message.content
    try:
        return json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        logger.error("Resposta da IA não é um JSON válido: %r", raw_content)
        raise AIServiceError("O serviço de IA retornou uma resposta em formato inválido.") from None


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


def extract_room_search_filters(query: str) -> dict:
    """Use an LLM to turn a natural-language room request into structured search filters.

    Args:
        query: free-text description of the desired space, e.g. "sala para 8
            pessoas com projetor amanhã de manhã".

    Returns:
        A dict with keys ``min_capacity``, ``attributes``, ``location`` and
        ``summary``. Attribute labels are normalized to catalog names when
        possible (e.g. ``internet`` → ``Wi-Fi``).
    """
    logger.info("Extraindo filtros de busca de sala a partir de linguagem natural.")
    data = _run_json_completion(_ROOM_SEARCH_SYSTEM_PROMPT, query)
    return {
        "min_capacity": data.get("min_capacity"),
        "attributes": normalize_room_search_attributes(data.get("attributes") or []),
        "location": data.get("location"),
        "summary": data.get("summary", ""),
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
    "6. Responda em português do Brasil, de forma direta e objetiva."
)

#: Resposta padrão quando o corpus não tem nada relacionado à pergunta. Evita
#: chamar o LLM sem contexto, situação em que ele tenderia a responder de memória.
NO_CONTEXT_ANSWER = (
    "Não encontrei nada na base de normas que responda a essa pergunta. "
    "O corpus cobre regulamentos de uso de auditórios, salas e cessão de espaços "
    "em instituições públicas."
)


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
    except GroqError:
        logger.exception("Falha ao chamar a API da Groq.")
        raise AIServiceError("Não foi possível consultar o serviço de IA no momento.") from None

    answer = (completion.choices[0].message.content or "").strip()
    if not answer:
        raise AIServiceError("O serviço de IA devolveu uma resposta vazia.")
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

    try:
        chunks = retrieval.search(question, top_k, hybrid=hybrid)
    except EmbeddingError as exc:
        logger.warning("Falha ao gerar embedding da pergunta: %s", exc)
        raise AIServiceError(str(exc)) from exc

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
