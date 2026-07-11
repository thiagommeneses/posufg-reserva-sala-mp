"""Services that call the Groq LLM API to power AI-assisted features.

This module encapsulates all interaction with the external LLM provider so
that views stay thin and the AI logic can be unit tested by mocking a single
function (:func:`_run_json_completion`).
"""

import json
import logging

from django.conf import settings
from groq import Groq, GroqError

from ai_assistant.exceptions import AIServiceError

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

_ROOM_SEARCH_SYSTEM_PROMPT = (
    "Você é um assistente que converte pedidos em linguagem natural sobre reserva de "
    "salas em filtros estruturados. Responda SOMENTE com um JSON válido, sem texto "
    "adicional, no formato exato: "
    '{"min_capacity": <int ou null>, "attributes": [<string>, ...], '
    '"location": <string ou null>, "summary": <string curta explicando o que foi '
    'entendido, em português>}. '
    "Os itens de 'attributes' devem ser nomes genéricos de equipamentos citados "
    "(ex.: projetor, tv, videoconferência, quadro branco). Se algo não for "
    "mencionado, use null ou lista vazia."
)

_MAINTENANCE_SYSTEM_PROMPT = (
    "Você é um classificador de motivos de bloqueio de manutenção de salas. Dado um "
    "texto curto descrevendo o motivo, classifique em exatamente uma das categorias: "
    f"{', '.join(MAINTENANCE_CATEGORIES)}. "
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


def extract_room_search_filters(query: str) -> dict:
    """Use an LLM to turn a natural-language room request into structured search filters.

    Args:
        query: free-text description of the desired space, e.g. "sala para 8
            pessoas com projetor amanhã de manhã".

    Returns:
        A dict with keys ``min_capacity``, ``attributes``, ``location`` and
        ``summary``.
    """
    logger.info("Extraindo filtros de busca de sala a partir de linguagem natural.")
    data = _run_json_completion(_ROOM_SEARCH_SYSTEM_PROMPT, query)
    return {
        "min_capacity": data.get("min_capacity"),
        "attributes": data.get("attributes") or [],
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
