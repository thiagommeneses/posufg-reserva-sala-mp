"""Suggest a space type for spaces that do not have one yet.

O pacote V2 é explícito: o backfill de tipo precisa ser revisado por um
administrador, e não inferido pelo nome e gravado. Uma sala chamada "Sala de
Reunião Alfa" quase certamente é uma sala de reunião — mas "Sala Focus" pode ser
qualquer coisa, e uma aba que classifica errado é pior do que uma aba vazia.

Por isso este comando **propõe** por padrão e só grava com ``--aplicar``, e mesmo
assim apenas onde a heurística tem certeza razoável. O que ele não souber
classificar fica em branco, para alguém decidir na tela de edição.

Uso::

    python manage.py sugerir_tipos_de_espaco            # só mostra a proposta
    python manage.py sugerir_tipos_de_espaco --aplicar  # grava o que foi proposto
"""

import unicodedata

from django.core.management.base import BaseCommand

from spaces.models import Space, SpaceType

#: Cada entrada é (trecho normalizado no nome do espaço, slug do tipo).
#: A ordem importa: o primeiro trecho encontrado vence, então os mais
#: específicos vêm antes.
REGRAS = [
    ("auditorio", "auditorio"),
    ("treinamento", "sala-de-treinamento"),
    ("capacitacao", "sala-de-treinamento"),
    ("coworking", "espaco-compartilhado"),
    ("compartilhad", "espaco-compartilhado"),
    ("executiva", "sala-executiva"),
    ("executivo", "sala-executiva"),
    ("reuniao", "sala-de-reuniao"),
]


def _normalizar(texto):
    """Return the text lowercased and without accents.

    Args:
        texto: O texto original.

    Returns:
        str: Texto comparável, sem acento e em minúsculas.
    """
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).lower()


def sugerir_slug(nome_do_espaco):
    """Return the suggested type slug for a space name, or ``None``.

    Args:
        nome_do_espaco: O nome cadastrado do espaço.

    Returns:
        str | None: O slug do tipo sugerido, ou ``None`` quando nenhuma regra
        se aplica — caso em que a decisão fica com o administrador.
    """
    normalizado = _normalizar(nome_do_espaco)
    for trecho, slug in REGRAS:
        if trecho in normalizado:
            return slug
    return None


class Command(BaseCommand):
    """Propose a space type for every space still unclassified."""

    help = "Propõe um tipo para os espaços sem classificação. Grava só com --aplicar."

    def add_arguments(self, parser):
        """Declare the command-line arguments."""
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Grava as sugestões. Sem esta opção o comando apenas mostra a proposta.",
        )

    def _separar(self, espacos):
        """Split the spaces into proposals and undecided ones.

        Args:
            espacos: Os espaços ainda sem tipo.

        Returns:
            tuple[list, list]: ``(propostos, indefinidos)``, onde ``propostos``
            é uma lista de ``(espaço, tipo)``.
        """
        tipos = {tipo.slug: tipo for tipo in SpaceType.objects.all()}
        propostos = []
        indefinidos = []
        for espaco in espacos:
            slug = sugerir_slug(espaco.name)
            tipo = tipos.get(slug) if slug else None
            if tipo:
                propostos.append((espaco, tipo))
            else:
                indefinidos.append(espaco)
        return propostos, indefinidos

    def _mostrar(self, total, propostos, indefinidos):
        """Print the proposal, so it can be reviewed before anything is written.

        Args:
            total: Quantos espaços estão sem tipo.
            propostos: Lista de ``(espaço, tipo)`` que a heurística classificou.
            indefinidos: Espaços que ficaram para decisão humana.
        """
        self.stdout.write("")
        self.stdout.write(f"{total} espaço(s) sem tipo.")
        self.stdout.write("")

        if propostos:
            self.stdout.write(self.style.MIGRATE_HEADING("Sugestões:"))
            for espaco, tipo in propostos:
                self.stdout.write(f"  {espaco.name:<40} → {tipo.name}")

        if indefinidos:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Sem sugestão (classifique na tela de edição):"))
            for espaco in indefinidos:
                self.stdout.write(f"  {espaco.name}")

        self.stdout.write("")

    def handle(self, *args, **options):
        """Print the proposal and optionally apply it."""
        aplicar = options["aplicar"]
        sem_tipo = Space.objects.filter(space_type__isnull=True).order_by("name")

        if not sem_tipo.exists():
            self.stdout.write(self.style.SUCCESS("Todos os espaços já têm tipo."))
            return

        propostos, indefinidos = self._separar(sem_tipo)
        self._mostrar(len(sem_tipo), propostos, indefinidos)

        if not aplicar:
            self.stdout.write(
                self.style.NOTICE(
                    "Nada foi gravado. Revise a proposta e rode de novo com --aplicar."
                )
            )
            return

        for espaco, tipo in propostos:
            espaco.space_type = tipo
            espaco.save(update_fields=["space_type", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"{len(propostos)} espaço(s) classificado(s)."))
        if indefinidos:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(indefinidos)} continuam sem tipo, por decisão do comando."
                )
            )
