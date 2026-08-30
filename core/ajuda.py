"""Perguntas frequentes derivadas das regras que o sistema realmente aplica.

Esta camada só lê. Ela não decide nada e não guarda nada: pega a política
vigente, as constantes de check-in e o fluxo de reserva em uso, e devolve as
respostas já escritas em português.

O motivo de existir é um só. Uma tela de ajuda escrita à mão é a primeira coisa
de um sistema a virar mentira — o administrador muda o horário de funcionamento
na política, e a Ajuda continua dizendo o horário de antes, sem erro nenhum, por
tempo indeterminado. Ninguém percebe porque nada quebra; o usuário percebe
quando já perdeu a viagem.

Aqui não existe essa cópia. Cada número da tela vem do mesmo lugar de onde a
regra vem:

- horário, dias, incremento, duração e horizonte, de :class:`BookingPolicy`;
- a janela de check-in, de :data:`reservations.services.CHECK_IN_WINDOW_MINUTES`;
- a liberação por não comparecimento, de ``release_no_shows`` e da tolerância;
- as etapas do fluxo, de :data:`reservations.steps.FLUXO_EM_USO`.

Duas honestidades ficam explícitas no texto gerado, e não são detalhe:

1. Quando ``release_no_shows`` está desligado — o padrão de fábrica — a resposta
   sobre não comparecimento **diz** que nada é liberado automaticamente. A
   resposta contrária, genérica e tranquilizadora, faria o usuário acreditar num
   mecanismo que não está rodando.
2. Quando ``enforce_window`` está desligado, a resposta sobre horários fala do
   que é *oferecido*, não do que é *aceito*. É a diferença real: a tela não
   oferece nada fora da janela, mas a API ainda aceita.

O que esta camada não sabe — uso de auditórios, acessibilidade, orientações da
casa — não é inventado aqui. Vem de :class:`core.models.HelpArticle`, escrito
por quem sabe.
"""

from reservations.models import BookingPolicy
from reservations.services import CHECK_IN_WINDOW_MINUTES
from reservations.steps import FLUXO_EM_USO
from reservations.validators import dias_por_extenso


def _minutos_por_extenso(minutos):
    """Return a duration in the words people use for it.

    240 minutos é quanto o banco guarda; "4 horas" é o que alguém entende.

    Args:
        minutos: A duração em minutos.

    Returns:
        str: A duração escrita — "30 minutos", "1 hora", "2h30".
    """
    if minutos < 60:
        return f"{minutos} minutos"
    horas, resto = divmod(minutos, 60)
    if resto:
        return f"{horas}h{resto:02d}"
    return "1 hora" if horas == 1 else f"{horas} horas"


def _como_reservar(policy):
    """Return the step-by-step answer, taken from the flow that is live."""
    etapas = ", ".join(f"{etapa.numero}. {etapa.rotulo}" for etapa in FLUXO_EM_USO)
    return [
        f"A reserva tem {len(FLUXO_EM_USO)} etapas: {etapas}.",
        "Comece em Nova Reserva, escolha o espaço, depois a data e o horário. "
        "Os horários mostrados já excluem o que está reservado por outra pessoa "
        "e o que está bloqueado para manutenção — o que aparece livre, está livre.",
        f"É possível reservar com até {policy.horizon_days} dias de antecedência.",
    ]


def _quando_reservar(policy):
    """Return the opening hours and days answer."""
    dias = dias_por_extenso(policy)
    return [
        f"Os horários são oferecidos {dias}, "
        f"das {policy.opening_time:%H:%M} às {policy.closing_time:%H:%M}.",
        f"Os horários começam de {policy.slot_minutes} em {policy.slot_minutes} minutos.",
    ]


def _quanto_tempo(policy):
    """Return the duration limits answer."""
    minimo = _minutos_por_extenso(policy.min_duration_minutes)
    maximo = _minutos_por_extenso(policy.max_duration_minutes)
    return [
        f"Uma reserva dura no mínimo {minimo} e no máximo {maximo}.",
        "Se precisar de mais tempo do que o máximo, fale com a administração "
        "antes de dividir o período em duas reservas seguidas.",
    ]


def _check_in(policy):
    """Return the check-in answer, with the real window."""
    return [
        f"O check-in fica disponível {CHECK_IN_WINDOW_MINUTES} minutos antes do "
        "início e vai até o horário de término da reserva.",
        "Ele aparece como um botão na sua reserva, em Minhas Reservas. "
        "Só reservas confirmadas fazem check-in.",
    ]


def _sem_check_in(policy):
    """Return the no-show answer — and say plainly when the rule is off.

    Esta é a resposta que mais tenta o texto genérico. "Sua reserva pode ser
    liberada" soa prudente e serve para os dois casos, e é exatamente por isso
    que não serve: com a regra desligada, ela ameaça o usuário com uma
    consequência que não existe; com a regra ligada, ela subestima uma que
    existe e tem prazo.
    """
    if policy.release_no_shows:
        tolerancia = _minutos_por_extenso(policy.no_show_threshold_minutes)
        return [
            f"Passados {tolerancia} do início sem check-in, a reserva é marcada "
            "como não comparecida e o espaço volta a ficar livre para outra pessoa.",
            "Se souber que não vai usar, cancele: cancelar libera o espaço na hora "
            "e não conta como não comparecimento.",
        ]
    return [
        "Hoje nada é liberado automaticamente: a reserva sem check-in continua "
        "ocupando o espaço até o horário de término.",
        "Por isso o cancelamento importa. Se souber que não vai usar, cancele — "
        "é o que devolve o espaço para outra pessoa.",
    ]


def _cancelar(policy):
    """Return the cancellation answer."""
    return [
        "Você cancela pela própria reserva, em Minhas Reservas. "
        "Só o dono da reserva pode cancelá-la.",
        "Dá para cancelar enquanto a reserva estiver confirmada ou com check-in "
        "feito. Depois de encerrada ou já cancelada, não há o que cancelar.",
        "Os serviços que você tiver pedido para aquela reserva são cancelados "
        "junto, sem precisar avisar ninguém.",
    ]


def _remarcar(policy):
    """Return the rescheduling answer."""
    return [
        "Dá para mudar a data e o horário sem perder a reserva: use Remarcar, "
        "na própria reserva. O novo horário passa pelas mesmas verificações de "
        "conflito e de política que valeram na criação.",
        "Assunto, número de participantes e observações você edita direto, "
        "sem remarcar — mudar o que a reunião é não disputa horário com ninguém.",
    ]


def _servicos(policy):
    """Return the services answer, naming the real catalog when it exists."""
    from services.models import ServiceType

    ativos = list(
        ServiceType.objects.filter(is_active=True)
        .order_by("sort_order", "name")
        .values_list("name", "min_lead_time_hours")
    )
    if not ativos:
        # Sem catálogo, prometer serviços seria inventar. A resposta diz o que
        # existe: nada, por enquanto.
        return [
            "Nenhum serviço está disponível para solicitação no momento.",
        ]

    nomes = ", ".join(nome for nome, _ in ativos)
    paragrafos = [
        "Você pede serviços junto com a reserva, ou depois, pela própria reserva. "
        "Cada espaço oferece os serviços que a administração vinculou a ele.",
        f"Serviços no catálogo: {nomes}.",
    ]
    prazos = sorted({horas for _, horas in ativos if horas})
    if prazos:
        maior = max(prazos)
        paragrafos.append(
            f"Alguns exigem antecedência — até {maior} horas antes do início da "
            "reserva. O prazo de cada um aparece na hora de solicitar.",
        )
    return paragrafos


#: As perguntas, na ordem em que a tela as mostra. Cada uma tem um ``id`` que
#: vira âncora e alvo do índice, e uma função que devolve os parágrafos da
#: resposta a partir da política.
PERGUNTAS = (
    ("como-reservar", "Como faço uma reserva?", _como_reservar),
    ("quando-reservar", "Em que dias e horários posso reservar?", _quando_reservar),
    ("quanto-tempo", "Quanto tempo pode durar uma reserva?", _quanto_tempo),
    ("check-in", "Como faço o check-in?", _check_in),
    ("sem-check-in", "E se eu não fizer o check-in?", _sem_check_in),
    ("cancelar", "Como cancelo uma reserva?", _cancelar),
    ("remarcar", "Posso mudar a data ou o horário?", _remarcar),
    ("servicos", "Como peço café, projetor ou outro serviço?", _servicos),
)


def perguntas_frequentes(policy=None):
    """Build the factual half of the help screen from the live rules.

    Args:
        policy: A política a considerar. Quando omitida, a vigente.

    Returns:
        list[dict]: Cada item com ``id``, ``pergunta`` e ``respostas`` — esta
        última uma lista de parágrafos já escritos.
    """
    policy = policy or BookingPolicy.carregar()
    return [
        {"id": identificador, "pergunta": pergunta, "respostas": resposta(policy)}
        for identificador, pergunta, resposta in PERGUNTAS
    ]
