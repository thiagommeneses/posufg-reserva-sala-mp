"""Step definitions for the reservation flow.

A jornada em vigor é a de quatro etapas do redesign V2: escolher espaço, data e
horário, detalhes e serviços, revisão e confirmação. Todas existem — as telas de
detalhes/serviços e de revisão entraram nas fases anteriores.

Houve um tempo em que a lista era outra, de três etapas, e o módulo guardava as
duas: a em uso e a alvo. Esse arranjo cobrou o preço dele. As views migraram
para a de quatro e **ninguém veio aqui apagar a de três**; a constante morta
ficou parecendo viva, e na Fase 23 a tela de Ajuda foi escrita lendo-a. O
resultado é o defeito que este módulo agora existe para impedir: o stepper
mostrando quatro etapas e a Ajuda ensinando três, sem nada quebrar.

Por isso sobrou **um nome só**, :data:`FLUXO_EM_USO`, e é ele que as views e a
Ajuda leem. Quando a jornada mudar de novo, muda aqui, num lugar. Uma segunda
lista "para o futuro" só volta a existir junto com um teste que compare as duas
telas entre si — não com a constante, que é o erro que já cometemos.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Etapa:
    """One step of the reservation flow.

    Attributes:
        numero: Posição da etapa, começando em 1.
        rotulo: Texto exibido ao usuário.
    """

    numero: int
    rotulo: str


#: A jornada que está no ar. Fonte única: as views do fluxo e a tela de Ajuda
#: leem daqui, e nada mais define etapas em lugar nenhum.
FLUXO_EM_USO = (
    Etapa(1, "Escolher espaço"),
    Etapa(2, "Data e horário"),
    Etapa(3, "Detalhes e serviços"),
    Etapa(4, "Revisão e confirmação"),
)

#: Apelido preservado porque as views o importam pelo nome. Aponta para o mesmo
#: objeto — não é uma segunda lista.
FLUXO_V2 = FLUXO_EM_USO


def contexto_do_stepper(etapa_atual, fluxo=FLUXO_EM_USO):
    """Build the template context for the stepper component.

    Args:
        etapa_atual: Número da etapa em que o usuário está (base 1).
        fluxo: Sequência de :class:`Etapa`. O padrão é o fluxo em vigor.

    Returns:
        dict: ``{"etapas": [...], "etapa_atual": int, "total_etapas": int}``,
        em que cada etapa carrega ``concluida`` e ``atual`` já resolvidos, para
        o template não precisar comparar números.
    """
    etapas = [
        {
            "numero": etapa.numero,
            "rotulo": etapa.rotulo,
            "concluida": etapa.numero < etapa_atual,
            "atual": etapa.numero == etapa_atual,
        }
        for etapa in fluxo
    ]
    return {
        "etapas": etapas,
        "etapa_atual": etapa_atual,
        "total_etapas": len(fluxo),
    }
