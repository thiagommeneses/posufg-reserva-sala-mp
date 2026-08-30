"""Core application models.

Hoje só a Ajuda mora aqui. Ela não é domínio de reserva: não tem espaço, não
tem horário, não participa de nenhuma regra de negócio. É texto institucional
sobre o produto inteiro, e por isso fica em ``core`` em vez de engordar
``reservations`` com uma tabela que nada tem a ver com reservar.
"""

import re

from django.db import models
from django.utils.text import slugify


class HelpArticleQuerySet(models.QuerySet):
    """Consultas nomeadas dos blocos de ajuda."""

    def publicados(self):
        """Return the blocks that should appear on the public help screen.

        Returns:
            HelpArticleQuerySet: Os blocos publicados, na ordem de exibição.
        """
        return self.filter(is_published=True).order_by("sort_order", "title")


class HelpArticle(models.Model):
    """Um bloco de orientação institucional, escrito por um administrador.

    A tela de Ajuda tem duas metades com origens diferentes, e a distinção é o
    ponto inteiro desta tabela.

    A metade factual — quando se pode reservar, quanto tempo dura, como é o
    check-in, o que acontece sem ele — é **derivada** da política vigente em
    :mod:`core.ajuda`. Ninguém a digita, porque texto digitado envelhece calado:
    o administrador muda o horário de funcionamento na política e a resposta da
    Ajuda continua dizendo o horário antigo, sem erro nenhum, por meses.

    A outra metade é institucional — uso de auditórios, recursos de
    acessibilidade, orientações da casa. Isso o código não tem como saber, e
    inventar seria pior do que omitir. Vem daqui, escrito por quem sabe.

    O texto é tratado como **texto puro**, nunca como HTML. Um bloco editável
    por um administrador que virasse marcação renderizada seria uma porta de
    injeção aberta na tela mais inocente do sistema. Os parágrafos saem de
    :meth:`paragrafos` e o template escapa cada um.
    """

    title = models.CharField(
        max_length=120,
        verbose_name="Título",
        help_text="A pergunta ou o assunto, como o usuário procuraria.",
    )
    #: Vira o ``id`` da seção na tela, e por isso o índice consegue apontar
    #: para ela. Derivado do título em :meth:`save`, nunca digitado.
    slug = models.SlugField(max_length=140, unique=True)
    body = models.TextField(
        verbose_name="Texto",
        help_text="Escreva em parágrafos, separados por uma linha em branco. "
        "É texto puro: marcação HTML não é interpretada.",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="Menor aparece primeiro. Empate resolve por título.",
    )
    is_published = models.BooleanField(
        default=True,
        verbose_name="Publicado",
        help_text="Desmarque para tirar o bloco da tela de Ajuda sem apagar o texto.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    objects = HelpArticleQuerySet.as_manager()

    class Meta:
        """Meta options for HelpArticle."""

        verbose_name = "Bloco de ajuda"
        verbose_name_plural = "Blocos de ajuda"
        ordering = ("sort_order", "title")

    def __str__(self):
        """Return the block title."""
        return self.title

    def save(self, *args, **kwargs):
        """Derive a unique slug from the title before saving."""
        if not self.slug:
            self.slug = self._slug_disponivel(slugify(self.title) or "bloco")
        super().save(*args, **kwargs)

    def _slug_disponivel(self, base):
        """Return ``base``, or ``base-2``, ``base-3``… until it is free.

        Args:
            base: O slug pretendido.

        Returns:
            str: Um slug que nenhum outro bloco usa.
        """
        candidato = base
        sufixo = 1
        existentes = HelpArticle.objects.exclude(pk=self.pk)
        while existentes.filter(slug=candidato).exists():
            sufixo += 1
            candidato = f"{base}-{sufixo}"
        return candidato

    def paragrafos(self):
        """Split the body into paragraphs on blank lines.

        Returns:
            list[str]: Os parágrafos, sem os vazios das linhas em branco.
        """
        return [bloco.strip() for bloco in re.split(r"\n\s*\n", self.body) if bloco.strip()]
