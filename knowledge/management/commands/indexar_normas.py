"""Indexa o corpus de normas: extrai, segmenta, gera embeddings e grava.

Segunda etapa do pipeline de RAG, depois de ``baixar_normas``. É idempotente: só
reprocessa documentos cujo arquivo mudou desde a última indexação.
"""

from django.core.management.base import BaseCommand, CommandError

from knowledge.manifest import ManifestError
from knowledge.services import ingest_corpus


class Command(BaseCommand):
    """Indexa os documentos de data/normas/ no banco vetorial."""

    help = "Extrai, segmenta e vetoriza o corpus de normas para busca semântica"

    def add_arguments(self, parser):
        """Declara as opções de linha de comando."""
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reindexa mesmo os documentos cujo arquivo não mudou.",
        )
        parser.add_argument(
            "--somente",
            type=int,
            nargs="*",
            help="Indexa apenas os ids informados (ex.: --somente 3 5 9).",
        )

    def handle(self, *args, **options):
        """Executa a ingestão e imprime o resumo."""
        self.stdout.write("Carregando modelo de embedding (pode demorar na primeira vez)...")

        try:
            report = ingest_corpus(options.get("somente"), force=options["force"])
        except ManifestError as exc:
            raise CommandError(str(exc)) from exc

        for identifier, nome, chunks in report.indexed:
            self.stdout.write(
                self.style.SUCCESS(f"  indexado  {identifier:02d} {nome} ({chunks} trechos)")
            )
        for identifier, nome in report.skipped:
            self.stdout.write(f"  sem mudança {identifier:02d} {nome}")
        for identifier, nome in report.pruned:
            self.stdout.write(
                self.style.WARNING(f"  removido  {identifier:02d} {nome} (fora do manifesto)")
            )

        self._resumir(report)

    def _resumir(self, report) -> None:
        """Imprime o resumo e detalha ausências e falhas."""
        self.stdout.write("")
        self.stdout.write(f"Indexados: {len(report.indexed)} ({report.total_chunks} trechos)")
        self.stdout.write(f"Sem mudança: {len(report.skipped)}")
        self.stdout.write(f"Sem arquivo: {len(report.missing)}")
        self.stdout.write(f"Falhas: {len(report.failed)}")
        if report.pruned:
            self.stdout.write(f"Removidos do índice: {len(report.pruned)}")

        if report.missing:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Fontes sem arquivo em disco:"))
            for identifier, label in report.missing:
                self.stdout.write(f"  {identifier:02d} {label}")
            self.stdout.write("Rode: python manage.py baixar_normas")

        if report.failed:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Documentos que não puderam ser indexados:"))
            for identifier, label, erro in report.failed:
                self.stdout.write(f"  {identifier:02d} {label}")
                self.stdout.write(f"     {erro}")
