"""Models for the spaces app."""

from django.core.files.uploadedfile import UploadedFile
from django.db import models

from spaces.images import caminho_da_capa, processar_imagem_de_capa
from spaces.validators import validar_imagem_de_capa, validar_nome_de_icone


class SpaceType(models.Model):
    """A category of space, managed by administrators.

    O pacote V2 pede categorias reais ("Sala de Reunião", "Auditório"...) para
    alimentar as abas da tela de reserva. Escolhemos uma tabela em vez de um
    ``choices`` fixo justamente para que criar um tipo novo seja uma operação de
    administrador, não uma migration.
    """

    name = models.CharField(max_length=80, unique=True, verbose_name="Nome")
    slug = models.SlugField(max_length=80, unique=True)
    icon_name = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="Ícone",
        help_text="Nome de um ícone do catálogo da aplicação.",
        validators=[validar_nome_de_icone],
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="Define a ordem das abas. Menor aparece primeiro.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        """Meta options for SpaceType."""

        ordering = ["sort_order", "name"]
        verbose_name = "Tipo de espaço"
        verbose_name_plural = "Tipos de espaço"

    def __str__(self):
        """Return the type name."""
        return self.name


class Space(models.Model):
    """A reservable space with capacity and location attributes."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    capacity = models.PositiveIntegerField()
    location = models.CharField(max_length=255)
    # Nullable de propósito: os espaços já cadastrados não têm tipo, e a
    # classificação precisa ser revisada por um administrador antes de virar
    # obrigatória — inferir pelo nome e gravar faria as abas mentirem.
    space_type = models.ForeignKey(
        "spaces.SpaceType",
        on_delete=models.SET_NULL,
        related_name="spaces",
        blank=True,
        null=True,
        verbose_name="Tipo de espaço",
    )
    cover_image = models.ImageField(
        upload_to=caminho_da_capa,
        blank=True,
        null=True,
        validators=[validar_imagem_de_capa],
        verbose_name="Imagem de capa",
        help_text="JPG, PNG ou WebP. Mínimo 800x450 px, máximo 5 MB. "
        "A imagem é recortada em 16:9 nos cards.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Space."""

        ordering = ["name"]

    def __str__(self):
        """Return the space name."""
        return self.name

    def save(self, *args, **kwargs):
        """Process a newly uploaded cover image before storing it.

        O tratamento roda aqui, e não no formulário, para que todo caminho de
        escrita — painel administrativo, Django Admin e API — produza o mesmo
        resultado. O arquivo só é processado quando é um upload novo: uma
        imagem lida do storage tem ``file`` do tipo ``File``, não
        ``UploadedFile``, então recarregar e salvar o objeto não reprocessa nem
        degrada a imagem a cada vez.
        """
        if self.cover_image and isinstance(getattr(self.cover_image, "file", None), UploadedFile):
            self.cover_image = processar_imagem_de_capa(self.cover_image)
        super().save(*args, **kwargs)


class Attribute(models.Model):
    """An attribute that can be associated with a space (e.g., TV, projector).

    Os três campos acrescentados na Fase 5 servem à tela de busca: nem todo
    equipamento pesa igual na decisão de quem procura sala. ``is_featured``
    separa os que viram filtro de primeira linha dos que ficam no "mais
    equipamentos"; ``sort_order`` decide a ordem entre eles; ``category`` agrupa
    a lista longa quando um administrador se der ao trabalho de preencher.

    Nenhum deles tem valor inventado por padrão: sem destaque marcado, a tela
    exibe todos os equipamentos como sempre exibiu.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Nome")
    category = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Categoria",
        help_text="Agrupa os equipamentos na lista longa. Opcional.",
    )
    icon_name = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="Ícone",
        help_text="Nome de um ícone do catálogo da aplicação. Decoração apenas.",
        validators=[validar_nome_de_icone],
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name="Em destaque",
        help_text="Aparece como filtro de primeira linha na busca por espaços.",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="Menor aparece primeiro. Empate resolve por nome.",
    )

    class Meta:
        """Meta options for Attribute."""

        ordering = ["sort_order", "name"]

    def __str__(self):
        """Return the attribute name."""
        return self.name


class SpaceAttribute(models.Model):
    """Many-to-many through model linking spaces and attributes."""

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="space_attributes")
    attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name="space_attributes"
    )

    class Meta:
        """Meta options for SpaceAttribute."""

        constraints = [
            models.UniqueConstraint(
                fields=["space", "attribute"],
                name="unique_space_attribute",
            ),
        ]

    def __str__(self):
        """Return a human-readable description of the link."""
        return f"{self.space.name} — {self.attribute.name}"
