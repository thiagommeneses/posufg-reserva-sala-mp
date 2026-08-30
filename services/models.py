"""Models for the services app.

Serviço não é atributo. O pacote V2 dá o exemplo exato: ``Projetor`` é atributo
do espaço — está lá, fisicamente. ``Apoio audiovisual`` é serviço — alguém
precisa ser acionado e vai executar uma tarefa. Por isso ``ServiceType`` não
mora em ``spaces``: o que ele descreve é trabalho da administração, não
equipamento da sala.

A relação com ``Space`` é declarada aqui, e não lá, para que ``spaces`` não
precise conhecer este app. ``space.services.all()`` continua funcionando pelo
``related_name``.
"""

from django.conf import settings
from django.db import models

from services.enums import ServiceRequestStatus
from spaces.validators import validar_nome_de_icone


class ServiceType(models.Model):
    """Something the administration can be asked to provide for a reservation.

    Catálogo administrável, como ``SpaceType``: criar um serviço novo é
    operação de administrador, não migration.
    """

    name = models.CharField(max_length=120, unique=True, verbose_name="Nome")
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Uma frase explicando o que o usuário recebe ao solicitar.",
    )
    category = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Categoria",
        help_text="Agrupa os serviços na tela de reserva. Opcional.",
    )
    icon_name = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="Ícone",
        help_text="Nome de um ícone do catálogo da aplicação. Decoração apenas.",
        validators=[validar_nome_de_icone],
    )
    spaces = models.ManyToManyField(
        "spaces.Space",
        blank=True,
        related_name="services",
        verbose_name="Espaços",
        help_text="Onde este serviço é oferecido. Sem nenhum espaço marcado, "
        "ele não aparece para ninguém.",
    )
    min_lead_time_hours = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Antecedência mínima",
        help_text="Quantas horas antes do início da reserva o pedido precisa "
        "chegar. Zero significa sem exigência.",
    )
    requires_notes = models.BooleanField(
        default=False,
        verbose_name="Exige detalhamento",
        help_text="Quando ligado, o usuário precisa descrever o que precisa antes de solicitar.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="Menor aparece primeiro. Empate resolve por nome.",
    )

    class Meta:
        """Meta options for ServiceType."""

        ordering = ["sort_order", "name"]
        verbose_name = "Tipo de serviço"
        verbose_name_plural = "Tipos de serviço"

    def __str__(self):
        """Return the service name."""
        return self.name


class ReservationServiceRequest(models.Model):
    """One service asked for on one reservation.

    Uma linha por pedido, e não um booleano por serviço no modelo da reserva.
    O pacote V2 proíbe os booleanos explicitamente, e a razão é operacional:
    um booleano diz que alguém pediu, mas não diz se foi recebido, recusado ou
    concluído — nem por quem. Sem isso não existe fila de trabalho.
    """

    reservation = models.ForeignKey(
        "reservations.Reservation",
        on_delete=models.CASCADE,
        related_name="service_requests",
        verbose_name="Reserva",
    )
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="Serviço",
    )
    status = models.CharField(
        max_length=20,
        choices=ServiceRequestStatus,
        default=ServiceRequestStatus.REQUESTED,
        verbose_name="Situação",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Detalhamento",
        help_text="O que o usuário descreveu ao solicitar.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="processed_service_requests",
        verbose_name="Atendido por",
    )
    processed_at = models.DateTimeField(blank=True, null=True, verbose_name="Atendido em")

    class Meta:
        """Meta options for ReservationServiceRequest."""

        ordering = ["reservation__start_time", "service_type__sort_order"]
        verbose_name = "Solicitação de serviço"
        verbose_name_plural = "Solicitações de serviço"
        constraints = [
            # Pedir duas vezes o mesmo serviço para a mesma reserva não é um
            # segundo pedido — é o mesmo pedido, e duplicá-lo faria a fila
            # mostrar trabalho que não existe.
            models.UniqueConstraint(
                fields=["reservation", "service_type"],
                name="unique_service_request_per_reservation",
            ),
        ]

    def __str__(self):
        """Return a human-readable description of the request."""
        return f"{self.service_type.name} — {self.reservation}"
