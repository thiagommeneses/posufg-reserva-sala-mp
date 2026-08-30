"""Business rules for requesting services on a reservation.

A decisão central desta camada está no pacote V2, e é contraintuitiva à
primeira vista:

    "Validar lead time de serviço sem impedir necessariamente a reserva
    inteira; quando a política assim definir, permitir reserva e marcar serviço
    como indisponível/necessita contato, em vez de falhar silenciosamente."

Ou seja: pedir café com uma hora de antecedência quando a copa precisa de
quatro **não** pode derrubar a reserva da sala. A sala está livre; o café é que
não dá. Recusar tudo faria a pessoa perder a sala por causa do café — e
aceitar em silêncio faria a copa descobrir tarde demais. O caminho é reservar a
sala, não criar o pedido, e dizer isso na cara do usuário.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from services.enums import STATUS_ENCERRADOS, ServiceRequestStatus
from services.models import ReservationServiceRequest, ServiceType

NOTES_REQUIRED_CODE = "service_notes_required"


class ServiceNotesRequiredError(ValidationError):
    """Raised when a service that requires notes was asked for without them.

    Continua sendo um ``ValidationError`` — quem só quer a mensagem não precisa
    saber que esta classe existe. O que ela acrescenta é ``service_type``: num
    formulário longo, um aviso no topo sem destino é um erro que o usuário não
    consegue encontrar, e a tela precisa saber para qual campo levar o foco.

    Não use ``params`` do Django para isso: ele aplica ``mensagem % params``, e
    um serviço chamado "Desconto 10%" derrubaria a formatação.
    """

    def __init__(self, service_type):
        """Build the error for a specific service.

        Args:
            service_type: O serviço que exige detalhamento.
        """
        super().__init__(
            f"Descreva o que você precisa em “{service_type.name}” para solicitar este serviço.",
            code=NOTES_REQUIRED_CODE,
        )
        self.service_type = service_type


def servicos_do_espaco(space):
    """Return the active services offered in a space.

    Um serviço que não é oferecido ali não aparece para o usuário — o pacote V2
    é explícito: "serviço não aplicável não aparece ao usuário".

    Args:
        space: O espaço.

    Returns:
        QuerySet: Serviços ativos vinculados ao espaço, na ordem do catálogo.
    """
    return ServiceType.objects.filter(is_active=True, spaces=space)


def antecedencia_suficiente(service_type, inicio_da_reserva, agora=None):
    """Return whether there is still time to ask for this service.

    Args:
        service_type: O serviço pretendido.
        inicio_da_reserva: Quando a reserva começa.
        agora: O instante considerado; ``timezone.now()`` quando omitido.

    Returns:
        bool: ``True`` se o pedido cabe na antecedência exigida.
    """
    if not service_type.min_lead_time_hours:
        return True
    agora = timezone.now() if agora is None else agora
    horas_restantes = (inicio_da_reserva - agora).total_seconds() / 3600
    return horas_restantes >= service_type.min_lead_time_hours


def montar_pedidos(space, selecoes):
    """Turn raw form selections into ``(ServiceType, detalhamento)`` pairs.

    A exigência de detalhamento é verificada aqui, e não no template, porque o
    campo é revelado por CSS (``peer-checked:``) e um ``required`` em elemento
    escondido trava o envio no navegador com uma mensagem que ninguém enxerga
    nem alcança pelo teclado. A regra fica onde as outras regras estão.

    Uma seleção que não corresponde a serviço oferecido neste espaço é
    descartada em silêncio: a tela honesta nunca a ofereceu, então não há nada
    a explicar ao usuário — e registrá-la criaria tarefa que ninguém ali sabe
    executar.

    Args:
        space: O espaço da reserva.
        selecoes: Iterável de ``(identificador, detalhamento)`` vindos do
            formulário.

    Returns:
        list: Pares ``(ServiceType, detalhamento)`` prontos para
        ``solicitar_servicos``.

    Raises:
        ValidationError: Quando um serviço que exige detalhamento veio sem.
    """
    oferecidos = {str(servico.pk): servico for servico in servicos_do_espaco(space)}

    pedidos = []
    for identificador, detalhamento in selecoes:
        service_type = oferecidos.get(str(identificador))
        if service_type is None:
            continue
        detalhamento = (detalhamento or "").strip()
        if service_type.requires_notes and not detalhamento:
            raise ServiceNotesRequiredError(service_type)
        pedidos.append((service_type, detalhamento))
    return pedidos


def _mensagem_de_recusa(service_type):
    """Return the sentence explaining why a service could not be requested."""
    horas = service_type.min_lead_time_hours
    return (
        f"{service_type.name} precisa de {horas} hora{'s' if horas != 1 else ''} "
        "de antecedência. A reserva foi confirmada; procure a administração se "
        "ainda precisar deste serviço."
    )


def solicitar_servicos(reservation, pedidos, agora=None):
    """Create the service requests that are still possible for a reservation.

    Nunca levanta erro por causa de um serviço: a reserva já existe quando esta
    função é chamada, e derrubá-la agora seria punir o usuário por um pedido
    acessório. O que não couber volta descrito em ``recusados``, para a tela
    dizer o que aconteceu.

    Args:
        reservation: A reserva já criada.
        pedidos: Iterável de ``(ServiceType, detalhamento)``.
        agora: O instante considerado; ``timezone.now()`` quando omitido.

    Returns:
        tuple[list, list]: ``(criados, recusados)``, onde ``recusados`` é uma
        lista de ``(ServiceType, motivo)``.
    """
    agora = timezone.now() if agora is None else agora
    oferecidos = set(servicos_do_espaco(reservation.space).values_list("pk", flat=True))

    criados = []
    recusados = []
    with transaction.atomic():
        for service_type, detalhamento in pedidos:
            if service_type.pk not in oferecidos:
                # Não é erro do usuário: é um pedido que a tela não deveria ter
                # oferecido. Registrar em silêncio criaria uma tarefa que
                # ninguém naquele espaço sabe executar.
                recusados.append(
                    (service_type, f"{service_type.name} não é oferecido neste espaço.")
                )
                continue
            if not antecedencia_suficiente(service_type, reservation.start_time, agora):
                recusados.append((service_type, _mensagem_de_recusa(service_type)))
                continue
            pedido, criado = ReservationServiceRequest.objects.get_or_create(
                reservation=reservation,
                service_type=service_type,
                defaults={"notes": detalhamento or ""},
            )
            if criado:
                criados.append(pedido)
    return criados, recusados


def sincronizar_servicos(reservation, pedidos, agora=None):
    """Bring a reservation's service requests in line with a new selection.

    A regra que sustenta esta função é sobre trabalho alheio: **um pedido que a
    administração já pegou não é desmarcável pelo usuário**. Enquanto ninguém
    tocou nele — situação ``Solicitado`` —, desmarcar é só desistir de pedir. A
    partir de ``Recebido``, alguém leu, se organizou, talvez já comprou o café;
    apagar a linha faria esse trabalho desaparecer da fila sem que a pessoa que
    o executa ficasse sabendo.

    Por isso o que sai da tela não é "o que foi desmarcado", e sim "o que foi
    desmarcado **e ainda podia** ser desmarcado". O resto volta em ``mantidos``,
    para a tela dizer por que continua ali.

    Args:
        reservation: A reserva sendo editada.
        pedidos: Iterável de ``(ServiceType, detalhamento)`` — a seleção nova.
        agora: O instante considerado; ``timezone.now()`` quando omitido.

    Returns:
        dict: ``criados``, ``removidos``, ``atualizados``, ``mantidos`` e
        ``recusados`` — este último com os pares ``(ServiceType, motivo)`` que
        ``solicitar_servicos`` já devolvia.
    """
    agora = timezone.now() if agora is None else agora
    desejados = {servico.pk: (servico, texto) for servico, texto in pedidos}
    existentes = {
        pedido.service_type_id: pedido
        for pedido in reservation.service_requests.select_related("service_type")
    }

    criados = []
    removidos = []
    atualizados = []
    mantidos = []

    with transaction.atomic():
        for service_type_id, pedido in existentes.items():
            if service_type_id in desejados:
                # Continua pedido: só o detalhamento pode ter mudado — e só
                # enquanto ninguém pegou o pedido. Depois de "Recebido", a
                # administração já leu este texto; reescrevê-lo faria a fila
                # trabalhar com uma informação e o usuário acreditar noutra,
                # sem nenhum dos dois perceber. É o mesmo motivo pelo qual o
                # pedido não pode ser removido.
                if pedido.status != ServiceRequestStatus.REQUESTED:
                    continue
                _servico, texto = desejados[service_type_id]
                if pedido.notes != (texto or ""):
                    pedido.notes = texto or ""
                    pedido.save(update_fields=["notes"])
                    atualizados.append(pedido)
                continue

            if pedido.status == ServiceRequestStatus.REQUESTED:
                removidos.append(pedido.service_type)
                pedido.delete()
            elif pedido.status in STATUS_ENCERRADOS:
                # Recusado, cancelado ou concluído já é história: nem sai da
                # tela por desmarcar, nem precisa de aviso.
                continue
            else:
                mantidos.append(
                    (
                        pedido.service_type,
                        f"{pedido.service_type.name} já está com a administração "
                        f"({pedido.get_status_display().lower()}). Fale com ela para cancelar.",
                    )
                )

        novos = [
            (servico, texto) for pk, (servico, texto) in desejados.items() if pk not in existentes
        ]
        criados, recusados = solicitar_servicos(reservation, novos, agora)

    return {
        "criados": criados,
        "removidos": removidos,
        "atualizados": atualizados,
        "mantidos": mantidos,
        "recusados": recusados,
    }


def atualizar_situacao(pedido, novo_status, usuario):
    """Move a service request to another status, recording who did it.

    Args:
        pedido: A solicitação.
        novo_status: O novo valor de ``ServiceRequestStatus``.
        usuario: Quem está atendendo.

    Returns:
        ReservationServiceRequest: A solicitação atualizada.
    """
    pedido.status = novo_status
    if novo_status in STATUS_ENCERRADOS:
        pedido.processed_by = usuario
        pedido.processed_at = timezone.now()
    else:
        # Voltar um pedido encerrado para a fila apaga o registro de conclusão:
        # ele não foi atendido, então dizer quem atendeu seria falso.
        pedido.processed_by = None
        pedido.processed_at = None
    pedido.save(update_fields=["status", "processed_by", "processed_at"])
    return pedido


def cancelar_pedidos_da_reserva(reservation):
    """Cancel the pending service requests of a cancelled reservation.

    Sem isto, cancelar uma reserva deixaria a copa preparando café para uma
    reunião que não vai acontecer. Pedidos já concluídos ou recusados ficam como
    estão: são história, não fila.

    Args:
        reservation: A reserva cancelada.

    Returns:
        int: Quantos pedidos foram cancelados.
    """
    return reservation.service_requests.exclude(status__in=STATUS_ENCERRADOS).update(
        status=ServiceRequestStatus.CANCELLED
    )
