"""Executa o pipeline dos três agentes contra um conjunto de pedidos de teste.

Mede latência e tokens por agente e compara a decisão obtida com a que a equipe
previa. O relatório resultante é o insumo do Log de Iteração e das Métricas de
Sucesso exigidos pela disciplina — nenhuma linha daquele documento deve ser escrita
sem uma execução deste comando por trás.

Por padrão a execução é revertida ao final: o caminho de código roda inteiro, inclusive
a criação da reserva e a restrição de exclusão do banco, mas o banco volta ao estado
anterior. Use ``--persistir`` quando quiser mesmo guardar as reservas criadas.
"""

import datetime
import json
import statistics
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ai_assistant import agents
from reservations.models import BookingPolicy

PEDIDOS_PADRAO = Path(settings.BASE_DIR) / "data" / "agentes" / "pedidos-teste.json"
PASTA_RESULTADOS = Path(settings.BASE_DIR) / "data" / "agentes"

User = get_user_model()


class _ReverterError(Exception):
    """Sinal interno para desfazer a transação preservando o resultado."""


class Command(BaseCommand):
    """Roda os pedidos de teste pelo pipeline e mede o custo de cada etapa."""

    help = "Executa o pipeline dos três agentes e mede latência, tokens e decisões"

    def add_arguments(self, parser):
        """Declara as opções de linha de comando."""
        parser.add_argument(
            "--arquivo",
            type=str,
            default=str(PEDIDOS_PADRAO),
            help="JSON com os pedidos de teste.",
        )
        parser.add_argument(
            "--usuario",
            type=str,
            help="Username que fará as reservas. Por padrão, o primeiro superusuário.",
        )
        parser.add_argument(
            "--somente",
            type=str,
            nargs="*",
            help="Roda apenas os pedidos com os ids informados (ex.: P01 P04).",
        )
        parser.add_argument(
            "--persistir",
            action="store_true",
            help="Mantém as reservas criadas. Sem esta opção, tudo é revertido no fim.",
        )
        parser.add_argument(
            "--saida",
            type=str,
            help="Caminho do relatório JSON. Por padrão, data/agentes/resultado-AAAA-MM-DD.json.",
        )

    def handle(self, *args, **options):
        """Roda o conjunto de pedidos e imprime o resumo."""
        pedidos = self._carregar(options["arquivo"], options.get("somente"))
        user = self._usuario(options.get("usuario"))
        policy = BookingPolicy.carregar()

        self.stdout.write(
            f"Rodando {len(pedidos)} pedidos como '{user.username}' — "
            f"modelo {settings.GROQ_MODEL}"
            + ("" if options["persistir"] else " — reservas serão revertidas ao final")
        )
        self.stdout.write("")

        registros = []
        for pedido in pedidos:
            resultado = self._executar(pedido, user, policy, options["persistir"])
            registro = resultado.como_dict()
            registro["id"] = pedido.get("id", "")
            registro["esperado"] = pedido.get("esperado", "")
            registro["sonda"] = pedido.get("sonda", "")
            registro["confere"] = registro["decisao"] == registro["esperado"]
            registros.append(registro)
            self._imprimir(registro)

        resumo = self._resumir(registros)
        self._imprimir_resumo(resumo)
        caminho = self._salvar(registros, resumo, options.get("saida"))
        self.stdout.write(self.style.SUCCESS(f"\nRelatório gravado em {caminho}"))

    # ------------------------------------------------------------------ apoio

    def _carregar(self, caminho, somente):
        """Read the test requests, optionally filtered by id."""
        arquivo = Path(caminho)
        if not arquivo.exists():
            raise CommandError(f"Arquivo de pedidos não encontrado: {arquivo}")
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        pedidos = dados.get("pedidos", [])
        if somente:
            alvo = {item.upper() for item in somente}
            pedidos = [p for p in pedidos if p.get("id", "").upper() in alvo]
        if not pedidos:
            raise CommandError("Nenhum pedido a executar.")
        return pedidos

    def _usuario(self, username):
        """Return the user who will own the reservations."""
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist as exc:
                raise CommandError(f"Usuário '{username}' não existe.") from exc
        # O admin criado pelo seed é staff, nem sempre superusuário — exigir
        # `is_superuser` fazia o comando falhar num ambiente perfeitamente válido.
        user = (
            User.objects.filter(is_superuser=True).order_by("pk").first()
            or User.objects.filter(is_staff=True).order_by("pk").first()
        )
        if user is None:
            raise CommandError(
                "Nenhum usuário administrador encontrado. Rode 'make seed' ou informe --usuario."
            )
        return user

    def _executar(self, pedido, user, policy, persistir):
        """Run one request, rolling the transaction back unless asked to persist."""
        if persistir:
            return agents.executar_pipeline(pedido["texto"], user, policy=policy)
        try:
            with transaction.atomic():
                resultado = agents.executar_pipeline(pedido["texto"], user, policy=policy)
                raise _ReverterError(resultado)
        except _ReverterError as sinal:
            return sinal.args[0]

    def _imprimir(self, registro):
        """Print one line per request, plus the reason when it diverged."""
        marca = "ok " if registro["confere"] else "DIF"
        estilo = self.style.SUCCESS if registro["confere"] else self.style.WARNING
        self.stdout.write(
            estilo(
                f"[{marca}] {registro['id']} "
                f"{registro['decisao']:<20} "
                f"esperado={registro['esperado']:<20} "
                f"{registro['duracao_ms']:>6} ms  "
                f"{registro['total_tokens']:>6} tok"
            )
        )
        for passo in registro["passos"]:
            if passo["erro"]:
                self.stdout.write(f"        erro em {passo['agente']}: {passo['erro']}")
        if not registro["confere"]:
            self.stdout.write(f"        {registro['mensagem']}")

    def _resumir(self, registros):
        """Aggregate latency, tokens and agreement across the run."""
        latencias = [r["duracao_ms"] for r in registros]
        tokens = [r["total_tokens"] for r in registros]
        por_agente = {}
        for registro in registros:
            for passo in registro["passos"]:
                acumulado = por_agente.setdefault(
                    passo["agente"], {"execucoes": 0, "ms": [], "tokens": 0, "erros": 0}
                )
                acumulado["execucoes"] += 1
                acumulado["ms"].append(passo["duracao_ms"])
                acumulado["tokens"] += (passo["tokens"] or {}).get("total_tokens") or 0
                acumulado["erros"] += 1 if passo["erro"] else 0
        for acumulado in por_agente.values():
            acumulado["ms_medio"] = round(statistics.mean(acumulado["ms"]), 1)
            acumulado["ms_maximo"] = max(acumulado["ms"])
            del acumulado["ms"]

        return {
            "pedidos": len(registros),
            "conferem": sum(1 for r in registros if r["confere"]),
            "latencia_media_ms": round(statistics.mean(latencias), 1) if latencias else 0,
            "latencia_mediana_ms": round(statistics.median(latencias), 1) if latencias else 0,
            "latencia_maxima_ms": max(latencias) if latencias else 0,
            "tokens_totais": sum(tokens),
            "tokens_medios_por_pedido": round(statistics.mean(tokens), 1) if tokens else 0,
            "por_agente": por_agente,
            "modelo": settings.GROQ_MODEL,
        }

    def _imprimir_resumo(self, resumo):
        """Print the aggregate block."""
        self.stdout.write("")
        self.stdout.write(f"Pedidos: {resumo['pedidos']} — conferem: {resumo['conferem']}")
        self.stdout.write(
            f"Latência: média {resumo['latencia_media_ms']} ms, "
            f"mediana {resumo['latencia_mediana_ms']} ms, "
            f"máxima {resumo['latencia_maxima_ms']} ms"
        )
        self.stdout.write(
            f"Tokens: {resumo['tokens_totais']} no total, "
            f"{resumo['tokens_medios_por_pedido']} por pedido"
        )
        for agente, dados in resumo["por_agente"].items():
            self.stdout.write(
                f"  {agente:<12} {dados['execucoes']:>2} execuções, "
                f"{dados['ms_medio']:>7} ms médio, "
                f"{dados['tokens']:>6} tokens, {dados['erros']} erro(s)"
            )

    def _salvar(self, registros, resumo, saida):
        """Write the full report as JSON and return its path."""
        if saida:
            caminho = Path(saida)
        else:
            hoje = datetime.date.today().isoformat()
            caminho = PASTA_RESULTADOS / f"resultado-{hoje}.json"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(
            json.dumps(
                {"resumo": resumo, "execucoes": registros},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return caminho
