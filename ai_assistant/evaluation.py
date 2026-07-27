"""Automatic evaluation of the assistant's answers (LLM-as-a-judge).

A retrieval-augmented system can fail in ways that look fine from the outside: a
fluent answer that the retrieved passages do not actually support, or one that omits
half of what they say. Reading answers by hand catches some of it, but does not scale
and is not reproducible across runs.

This module scores each answer against **the passages that were retrieved for it**, not
against the world. That is the property that matters here: the system is supposed to
report what the corpus says, so an answer is correct when it is faithful to the corpus —
even if the corpus itself is incomplete.

Three criteria, scored 0 to 5 by a second LLM call:

* **Fundamentação** — is every claim supported by the excerpts? Penalises invention.
* **Completude** — does the answer use the relevant information available?
* **Citação** — are the excerpts cited by number, and correctly attributed?
"""

import logging

from ai_assistant.exceptions import AIServiceError
from ai_assistant.services import _build_context, _run_json_completion

logger = logging.getLogger(__name__)

CRITERIA = ("fundamentacao", "completude", "citacao")
MAX_SCORE = 5

_JUDGE_SYSTEM_PROMPT = (
    "Você é um avaliador rigoroso de sistemas de perguntas e respostas baseados em "
    "recuperação de documentos. Receberá uma pergunta, os trechos que foram "
    "recuperados e a resposta gerada.\n\n"
    "Avalie a resposta EXCLUSIVAMENTE em relação aos trechos fornecidos. Não use "
    "conhecimento próprio sobre o assunto: se a resposta afirma algo que os trechos "
    "não sustentam, isso é falha de fundamentação, ainda que a afirmação seja "
    "verdadeira no mundo real.\n\n"
    "Critérios, cada um de 0 a 5:\n"
    "- fundamentacao: toda afirmação da resposta é sustentada pelos trechos? "
    "Penalize severamente qualquer informação inventada.\n"
    "- completude: a resposta aproveita a informação relevante disponível nos "
    "trechos, ou deixa de fora algo que responderia melhor à pergunta?\n"
    "- citacao: a resposta cita os trechos pelo número e atribui corretamente cada "
    "regra à sua instituição?\n\n"
    "Quando a resposta corretamente declara que os trechos não permitem responder, "
    "isso é bom comportamento: atribua nota alta em fundamentacao.\n\n"
    "Responda SOMENTE com um JSON válido, sem texto adicional, no formato exato: "
    '{"fundamentacao": <int 0-5>, "completude": <int 0-5>, "citacao": <int 0-5>, '
    '"justificativa": <string curta em português explicando as notas>}.'
)


def judge_answer(question: str, answer: str, sources: list[dict]) -> dict:
    """Score one answer against the passages that grounded it.

    Args:
        question: The question that was asked.
        answer: The answer the system produced.
        sources: The passages returned alongside the answer.

    Returns:
        dict: Scores per criterion, ``media`` and ``justificativa``.

    Raises:
        AIServiceError: If the judge call fails or returns an unusable verdict.
    """
    excerpts = "\n\n".join(
        f"[{source['position']}] {source['institution']} — {source['document']}\n"
        f"{source['excerpt']}"
        for source in sources
    )
    prompt = (
        f"Pergunta: {question}\n\n"
        f"Trechos recuperados:\n\n{excerpts or '(nenhum trecho recuperado)'}\n\n"
        f"Resposta gerada:\n\n{answer}"
    )

    verdict = _run_json_completion(_JUDGE_SYSTEM_PROMPT, prompt)
    scores = {criterion: _clamp(verdict.get(criterion)) for criterion in CRITERIA}

    return {
        **scores,
        "media": round(sum(scores.values()) / len(CRITERIA), 2),
        "justificativa": verdict.get("justificativa", ""),
    }


def _clamp(value) -> int:
    """Coerce a judge score into the 0..5 range.

    The judge is itself an LLM and can return a string, a float or a value outside the
    scale. Clamping here keeps a malformed verdict from corrupting the aggregate.

    Raises:
        AIServiceError: If the value cannot be read as a number at all.
    """
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError) as exc:
        raise AIServiceError(f"Nota inválida devolvida pelo avaliador: {value!r}") from exc
    return max(0, min(MAX_SCORE, number))


def summarise(results: list[dict]) -> dict:
    """Aggregate per-question results into overall scores.

    Args:
        results: One entry per evaluated question, each with the criterion scores.

    Returns:
        dict: Mean per criterion plus the overall mean.
    """
    if not results:
        return {criterion: 0.0 for criterion in (*CRITERIA, "media")}

    aggregate = {
        criterion: round(sum(r[criterion] for r in results) / len(results), 2)
        for criterion in CRITERIA
    }
    aggregate["media"] = round(sum(aggregate.values()) / len(CRITERIA), 2)
    return aggregate


__all__ = ["CRITERIA", "MAX_SCORE", "judge_answer", "summarise", "_build_context"]
