"""Avalia automaticamente as respostas do assistente (LLM-as-a-judge).

Executa um conjunto de perguntas de referência contra o sistema e submete cada resposta
a um segundo modelo, que a pontua em fundamentação, completude e citação — sempre em
relação aos trechos efetivamente recuperados.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ai_assistant.evaluation import CRITERIA, MAX_SCORE, judge_answer, summarise
from ai_assistant.exceptions import AIServiceError
from ai_assistant.services import answer_from_documents

PERGUNTAS = Path(settings.BASE_DIR) / "data" / "avaliacao" / "perguntas.json"


class Command(BaseCommand):
    """Avalia as respostas do assistente com um LLM juiz."""

    help = "Avalia as respostas do assistente documental usando LLM-as-a-judge"

    def add_arguments(self, parser):
        """Declara as opções de linha de comando."""
        parser.add_argument(
            "--somente",
            type=int,
            nargs="*",
            help="Avalia apenas as perguntas com os ids informados.",
        )
        parser.add_argument(
            "--salvar",
            type=str,
            help="Grava o relatório completo em JSON no caminho informado.",
        )

    def handle(self, *args, **options):
        """Roda a avaliação e imprime o relatório."""
        perguntas = self._carregar(options.get("somente"))
        resultados = []

        for item in perguntas:
            self.stdout.write(f"  avaliando {item['id']:02d} {item['pergunta'][:60]}...")
            try:
                resultado = self._avaliar(item)
            except AIServiceError as exc:
                self.stdout.write(self.style.ERROR(f"     falhou: {exc}"))
                continue
            resultados.append(resultado)
            self._imprimir_notas(resultado)

        self._resumir(resultados)

        if options.get("salvar"):
            destino = Path(options["salvar"])
            destino.write_text(
                json.dumps(
                    {"resultados": resultados, "resumo": summarise(resultados)},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            self.stdout.write(f"\nRelatório gravado em {destino}")

    def _carregar(self, ids: list[int] | None) -> list[dict]:
        """Lê o conjunto de perguntas de referência.

        Raises:
            CommandError: se o arquivo não existir ou estiver malformado.
        """
        if not PERGUNTAS.exists():
            raise CommandError(f"Conjunto de perguntas não encontrado: {PERGUNTAS}")
        try:
            dados = json.loads(PERGUNTAS.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Conjunto de perguntas inválido: {exc}") from exc

        perguntas = dados.get("perguntas", [])
        if ids:
            perguntas = [p for p in perguntas if p["id"] in ids]
        if not perguntas:
            raise CommandError("Nenhuma pergunta a avaliar.")
        return perguntas

    def _avaliar(self, item: dict) -> dict:
        """Responde uma pergunta e submete a resposta ao juiz."""
        resposta = answer_from_documents(item["pergunta"])
        notas = judge_answer(item["pergunta"], resposta["answer"], resposta["sources"])
        return {
            "id": item["id"],
            "pergunta": item["pergunta"],
            "tipo": item.get("tipo", ""),
            "resposta": resposta["answer"],
            "trechos_recuperados": len(resposta["sources"]),
            "used_context": resposta["used_context"],
            **notas,
        }

    def _imprimir_notas(self, resultado: dict) -> None:
        """Imprime as notas de uma pergunta."""
        notas = "  ".join(f"{c}={resultado[c]}" for c in CRITERIA)
        estilo = self.style.SUCCESS if resultado["media"] >= 4 else self.style.WARNING
        self.stdout.write(estilo(f"     {notas}  media={resultado['media']}"))

    def _resumir(self, resultados: list[dict]) -> None:
        """Imprime o resumo agregado."""
        resumo = summarise(resultados)

        self.stdout.write("")
        self.stdout.write(f"Perguntas avaliadas: {len(resultados)}")
        self.stdout.write(f"Escala: 0 a {MAX_SCORE}")
        self.stdout.write("")
        for criterio in CRITERIA:
            self.stdout.write(f"  {criterio:<16} {resumo[criterio]}")
        self.stdout.write(f"  {'MEDIA GERAL':<16} {resumo['media']}")

        fora = [r for r in resultados if not r["used_context"]]
        if fora:
            self.stdout.write("")
            self.stdout.write(
                f"{len(fora)} pergunta(s) sem contexto recuperado — esperado para as "
                f"de controle negativo."
            )
