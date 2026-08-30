"""Propose which equipment attributes deserve to be first-line filters.

Quais equipamentos importam mais na hora de escolher uma sala é uma pergunta
sobre esta casa, não sobre software. Em vez de eleger favoritos no código, este
comando olha o dado que existe: quantos espaços ativos oferecem cada
equipamento.

O critério é deliberadamente simples e explicável — um equipamento que quase
todo espaço tem não separa nada, e um que quase nenhum tem interessa a pouca
gente. O que discrimina bem fica no meio. O comando ordena por essa utilidade e
propõe os primeiros.

Como no backfill de tipos, ele **propõe** por padrão e só grava com
``--aplicar``. E, também como lá, nada impede um administrador de discordar e
marcar outro na tela de equipamentos.

Uso::

    python manage.py sugerir_atributos_em_destaque              # só mostra
    python manage.py sugerir_atributos_em_destaque --aplicar    # grava
    python manage.py sugerir_atributos_em_destaque --quantidade 5
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from spaces.models import Attribute, Space

#: Quantos equipamentos entram em destaque por padrão. Acima disso a primeira
#: linha de filtros deixa de ser uma escolha e vira a lista inteira de novo.
QUANTIDADE_PADRAO = 4


def _utilidade(disponivel_em, total_de_espacos):
    """Return how well an attribute splits the catalog in two.

    O valor é máximo quando metade dos espaços tem o equipamento e cai para
    zero nos extremos — "todos têm" e "ninguém tem" filtram igualmente mal.

    Args:
        disponivel_em: Em quantos espaços ativos o equipamento aparece.
        total_de_espacos: Quantos espaços ativos existem.

    Returns:
        float: Zero a um.
    """
    if not total_de_espacos or not disponivel_em:
        return 0.0
    proporcao = disponivel_em / total_de_espacos
    return 1 - abs(proporcao - 0.5) * 2


class Command(BaseCommand):
    """Propose the featured attributes from real usage."""

    help = "Propõe quais equipamentos vão para o filtro principal. Grava só com --aplicar."

    def add_arguments(self, parser):
        """Declare the command-line arguments."""
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Grava a proposta. Sem esta opção o comando apenas mostra.",
        )
        parser.add_argument(
            "--quantidade",
            type=int,
            default=QUANTIDADE_PADRAO,
            help=f"Quantos equipamentos destacar (padrão: {QUANTIDADE_PADRAO}).",
        )

    def _ranquear(self):
        """Return the attributes ordered by how well they discriminate.

        Returns:
            list[tuple]: ``(atributo, espaços, utilidade)`` do mais ao menos útil.
        """
        total = Space.objects.filter(is_active=True).count()
        atributos = Attribute.objects.annotate(
            espacos=Count(
                "space_attributes",
                filter=Q(space_attributes__space__is_active=True),
                distinct=True,
            )
        )
        ranking = [(a, a.espacos, _utilidade(a.espacos, total)) for a in atributos]
        ranking.sort(key=lambda item: (-item[2], item[0].name))
        return total, ranking

    def handle(self, *args, **options):
        """Print the proposal and optionally apply it."""
        quantidade = options["quantidade"]
        total, ranking = self._ranquear()

        if not ranking:
            self.stdout.write(self.style.WARNING("Nenhum equipamento cadastrado."))
            return

        propostos = [item for item in ranking[:quantidade] if item[2] > 0]

        self.stdout.write("")
        self.stdout.write(f"{total} espaço(s) ativo(s).")
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Equipamentos, do mais ao menos útil:"))
        for atributo, espacos, utilidade in ranking:
            marca = "→" if any(atributo.pk == p[0].pk for p in propostos) else " "
            self.stdout.write(
                f"  {marca} {atributo.name:<24} {espacos:>3} espaço(s)   utilidade {utilidade:.2f}"
            )

        self.stdout.write("")
        if not propostos:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum equipamento separa o acervo de forma útil. "
                    "A tela continua listando todos."
                )
            )
            return

        if not options["aplicar"]:
            self.stdout.write(
                self.style.NOTICE(
                    "Nada foi gravado. Revise a proposta e rode de novo com --aplicar."
                )
            )
            return

        pks = [atributo.pk for atributo, _, _ in propostos]
        Attribute.objects.exclude(pk__in=pks).update(is_featured=False)
        for ordem, (atributo, _, _) in enumerate(propostos, start=1):
            Attribute.objects.filter(pk=atributo.pk).update(is_featured=True, sort_order=ordem * 10)

        self.stdout.write(self.style.SUCCESS(f"{len(propostos)} equipamento(s) em destaque."))
