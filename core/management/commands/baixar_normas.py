"""Baixa o corpus documental de normas de uso de espaços a partir de fontes.json.

Primeira etapa do pipeline de RAG: coleta e preparação dos documentos. O comando é
idempotente — arquivos já baixados são ignorados, salvo uso de ``--force``.
"""

import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from knowledge.manifest import ManifestError, load_sources

DESTINO = Path(settings.KNOWLEDGE_DOCUMENTS_DIR)

MINIMO_EXIGIDO = 20
TIMEOUT_SEGUNDOS = 60

# Alguns portais institucionais recusam requisições sem User-Agent de navegador.
CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/pdf,application/xhtml+xml,*/*",
}

EXTENSAO_POR_TIPO = {
    "application/pdf": ".pdf",
    "text/html": ".html",
    "text/plain": ".txt",
}


class Command(BaseCommand):
    """Baixa os documentos listados em data/normas/fontes.json."""

    help = "Baixa o corpus de normas de uso de espaços definido em data/normas/fontes.json"

    def add_arguments(self, parser):
        """Declara as opções de linha de comando."""
        parser.add_argument(
            "--force",
            action="store_true",
            help="Baixa novamente os documentos que já existem em disco.",
        )
        parser.add_argument(
            "--somente",
            type=int,
            nargs="*",
            help="Baixa apenas os ids informados (ex.: --somente 3 5 9).",
        )

    def handle(self, *args, **options):
        """Percorre as fontes, baixa cada documento e imprime o resumo."""
        fontes = self._carregar_fontes()

        ids_desejados = options.get("somente")
        if ids_desejados:
            fontes = [f for f in fontes if f["id"] in ids_desejados]

        DESTINO.mkdir(parents=True, exist_ok=True)

        baixados, ignorados, falhas = [], [], []

        for fonte in fontes:
            existente = self._arquivo_existente(fonte["id"], fonte["slug"])
            if existente and not options["force"]:
                ignorados.append((fonte, existente.name))
                continue

            try:
                caminho = self._baixar(fonte)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
                falhas.append((fonte, str(exc)))
                self.stdout.write(self.style.ERROR(f"  falhou  {fonte['id']:02d} {fonte['slug']}"))
                continue

            baixados.append((fonte, caminho.name))
            self.stdout.write(self.style.SUCCESS(f"  ok      {fonte['id']:02d} {caminho.name}"))

        self._resumir(baixados, ignorados, falhas)

    def _carregar_fontes(self) -> list[dict]:
        """Lê o manifesto compartilhado com o pipeline de indexação.

        Raises:
            CommandError: se o manifesto não existir ou estiver malformado.
        """
        try:
            return load_sources()
        except ManifestError as exc:
            raise CommandError(str(exc)) from exc

    def _arquivo_existente(self, indice: int, slug: str) -> Path | None:
        """Retorna o arquivo já baixado para esta fonte, se houver."""
        encontrados = sorted(DESTINO.glob(f"{indice:02d}-{slug}.*"))
        return encontrados[0] if encontrados else None

    def _baixar(self, fonte: dict) -> Path:
        """Baixa um documento e o grava com nome padronizado.

        Args:
            fonte: Entrada do manifesto, com ``id``, ``slug`` e ``url``.

        Returns:
            Path: Caminho do arquivo gravado.

        Raises:
            ValueError: se a URL não usar http/https.
        """
        url = fonte["url"]
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Esquema de URL não suportado: {url}")

        requisicao = urllib.request.Request(url, headers=CABECALHOS)  # noqa: S310
        # URL validada acima; o manifesto é versionado e revisado no repositório.
        with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:  # noqa: S310
            conteudo = resposta.read()
            tipo = resposta.headers.get_content_type()

        extensao = EXTENSAO_POR_TIPO.get(tipo, ".html")
        caminho = DESTINO / f"{fonte['id']:02d}-{fonte['slug']}{extensao}"
        caminho.write_bytes(conteudo)
        return caminho

    def _resumir(self, baixados: list, ignorados: list, falhas: list) -> None:
        """Imprime o resumo e alerta se o corpus ficar abaixo do mínimo exigido."""
        total = len(baixados) + len(ignorados)

        self.stdout.write("")
        self.stdout.write(f"Baixados: {len(baixados)}")
        self.stdout.write(f"Já existiam: {len(ignorados)}")
        self.stdout.write(f"Falhas: {len(falhas)}")
        self.stdout.write(f"Total em disco: {total}")

        if falhas:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Fontes que falharam:"))
            for fonte, erro in falhas:
                self.stdout.write(f"  {fonte['id']:02d} {fonte['instituicao']}: {erro}")
                self.stdout.write(f"     {fonte['url']}")
            self.stdout.write("")
            self.stdout.write(
                "Baixe manualmente as que falharam e salve em data/normas/ "
                "seguindo o padrão NN-slug.pdf"
            )

        if total < MINIMO_EXIGIDO:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(
                    f"Atenção: {total} documentos em disco, abaixo do mínimo de "
                    f"{MINIMO_EXIGIDO} exigido pelo enunciado."
                )
            )
