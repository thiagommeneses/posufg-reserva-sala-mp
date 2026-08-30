"""Status values for service requests.

Ficam num módulo próprio, como os de ``reservations``, para que os validadores
possam importá-los sem depender dos modelos.
"""

from django.db import models


class ServiceRequestStatus(models.TextChoices):
    """The life of one service request, from asked to resolved.

    Os seis valores são os sugeridos pelo pacote V2. A separação entre
    ``DECLINED`` e ``CANCELLED`` importa: recusado é decisão de quem atende,
    cancelado é decisão de quem pediu. Juntar os dois apagaria a informação de
    quem desistiu do quê.
    """

    REQUESTED = "requested", "Solicitado"
    ACKNOWLEDGED = "acknowledged", "Recebido"
    IN_PROGRESS = "in_progress", "Em andamento"
    COMPLETED = "completed", "Concluído"
    DECLINED = "declined", "Recusado"
    CANCELLED = "cancelled", "Cancelado"


#: Situações em que o pedido ainda espera alguma ação de quem atende. É o que
#: define a fila operacional do painel administrativo.
STATUS_PENDENTES = (
    ServiceRequestStatus.REQUESTED,
    ServiceRequestStatus.ACKNOWLEDGED,
    ServiceRequestStatus.IN_PROGRESS,
)

#: Situações finais. Um pedido aqui não volta para a fila sozinho.
STATUS_ENCERRADOS = (
    ServiceRequestStatus.COMPLETED,
    ServiceRequestStatus.DECLINED,
    ServiceRequestStatus.CANCELLED,
)
