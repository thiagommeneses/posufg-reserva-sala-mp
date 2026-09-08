"""Tests for the three-agent pipeline.

Nenhum teste aqui chama a API do Groq nem a base vetorial: o que se verifica é o
**julgamento** — quando o pipeline para, quando ele reserva, quando ele recusa e quando
ele escala. As chamadas de modelo e de recuperação entram substituídas, porque o valor
que elas devolvem é justamente o que precisa ser controlado para testar a decisão.
"""

import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from ai_assistant import agents
from ai_assistant.exceptions import AIServiceError
from ai_assistant.management.commands.testar_agentes import Command
from reservations.models import BookingPolicy, Reservation, ReservationStatus
from spaces.models import Attribute, Space, SpaceAttribute, SpaceType

User = get_user_model()


@pytest.fixture
def usuario(db):
    """Create the user who owns the reservations."""
    return User.objects.create_user(username="agente", password="senha-forte-123")


@pytest.fixture
def politica(db):
    """Return the booking policy with known limits."""
    policy = BookingPolicy.carregar()
    policy.opening_time = datetime.time(8, 0)
    policy.closing_time = datetime.time(18, 0)
    policy.min_duration_minutes = 30
    policy.max_duration_minutes = 240
    policy.horizon_days = 90
    policy.opens_saturday = False
    policy.opens_sunday = False
    policy.save()
    return policy


@pytest.fixture
def sala(db):
    """Create an active 12-seat room with a TV."""
    tipo = SpaceType.objects.create(name="Reunião", slug="reuniao")
    espaco = Space.objects.create(
        name="Sala Alfa", capacity=12, location="Bloco A", space_type=tipo, is_active=True
    )
    tv = Attribute.objects.create(name="TV")
    SpaceAttribute.objects.create(space=espaco, attribute=tv)
    return espaco


def proxima_quarta():
    """Return the next Wednesday, a day the policy is always open."""
    hoje = timezone.localdate()
    return hoje + datetime.timedelta(days=(2 - hoje.weekday()) % 7 or 7)


def criterios_validos(**ajustes):
    """Build a complete set of criteria, overridable field by field."""
    base = {
        "min_capacity": 10,
        "max_capacity": None,
        "attributes": ["TV"],
        "location": None,
        "summary": "sala para 10 pessoas com TV",
        "date": proxima_quarta(),
        "start_time": datetime.time(9, 0),
        "duration_minutes": 120,
        "avisos": [],
        "faltando": [],
    }
    base.update(ajustes)
    return base


def trecho(posicao=1):
    """Build a retrieved chunk without touching the vector store."""
    return SimpleNamespace(
        institution=f"Instituição {posicao}",
        document_title="Regulamento de auditórios",
        source_url=f"https://example.org/{posicao}.pdf",
        text="A reserva deve ser solicitada com antecedência mínima de 48 horas.",
        score=0.9,
    )


# --------------------------------------------------------------------- agente 1


class TestInterpreteDeSolicitacao:
    """O Agente 1 estrutura o pedido e diz o que falta."""

    def test_marca_campos_essenciais_ausentes(self, db, politica):
        """Sem data, horário ou duração, o pedido não segue."""
        extraido = criterios_validos(date=None, start_time=None, duration_minutes=None)
        extraido.pop("faltando")

        with patch("ai_assistant.services.extract_room_search_filters", return_value=extraido):
            criterios, passo = agents.interpretar_pedido("quero uma sala", policy=politica)

        assert criterios["faltando"] == ["date", "start_time", "duration_minutes"]
        assert passo.agente == agents.AGENTE_INTERPRETE
        assert passo.erro is None

    def test_pedido_completo_nao_deixa_pendencia(self, db, politica):
        """Com tudo informado, nada fica faltando."""
        extraido = criterios_validos()
        extraido.pop("faltando")

        with patch("ai_assistant.services.extract_room_search_filters", return_value=extraido):
            criterios, _ = agents.interpretar_pedido("sala amanhã às 9h", policy=politica)

        assert criterios["faltando"] == []

    def test_falha_do_modelo_vira_erro_do_passo(self, db, politica):
        """A falha é registrada no passo, não propagada para cima."""
        with patch(
            "ai_assistant.services.extract_room_search_filters",
            side_effect=AIServiceError("indisponível"),
        ):
            criterios, passo = agents.interpretar_pedido("sala", policy=politica)

        assert criterios == {}
        assert "indisponível" in passo.erro

    def test_pergunta_de_esclarecimento_lista_o_que_falta(self):
        """A pergunta nomeia exatamente os campos ausentes."""
        pergunta = agents.pergunta_de_esclarecimento({"faltando": ["date", "duration_minutes"]})

        assert "a data" in pergunta
        assert "a duração" in pergunta

    def test_valor_recusado_explica_em_vez_de_perguntar(self):
        """Quem escreveu "por 15 minutos" não pode ouvir "qual a duração?".

        Regressão da rodada #01: a validação anulava o campo e o pipeline tratava o
        valor recusado como valor ausente, devolvendo a pergunta que a pessoa já
        tinha respondido.
        """
        mensagem = agents.pergunta_de_esclarecimento(
            {
                "faltando": ["duration_minutes"],
                "avisos": ["A duração pedida está fora do permitido (de 30 a 240 minutos)."],
            }
        )

        assert "fora do permitido" in mensagem
        assert "preciso saber" not in mensagem


# --------------------------------------------------------------------- agente 2


class TestConsultorNormativo:
    """O Agente 2 emite parecer e nunca afirma regra sem trecho."""

    @pytest.mark.parametrize(
        ("ajuste", "esperado"),
        [
            ({"duration_minutes": 15}, "menor que o mínimo"),
            ({"duration_minutes": 600}, "excede o máximo"),
            ({"date": timezone.localdate() - datetime.timedelta(days=1)}, "já passou"),
            (
                {"date": timezone.localdate() + datetime.timedelta(days=400)},
                "horizonte",
            ),
        ],
    )
    def test_politica_barra_sem_chamar_o_modelo(self, db, politica, ajuste, esperado):
        """Regra cadastrada é comparação exata — não se pergunta isso a um LLM."""
        with patch("ai_assistant.services._run_json_completion") as modelo:
            parecer, passo = agents.emitir_parecer(criterios_validos(**ajuste), policy=politica)

        modelo.assert_not_called()
        assert parecer["parecer"] == agents.PARECER_INADMISSIVEL
        assert esperado in parecer["fundamentacao"]
        assert passo.total_tokens == 0

    def test_sem_referencia_aprova_sem_chamar_o_modelo(self, db, politica):
        """Ausência de referência comparativa não restringe nada.

        Correção da rodada #02: antes, corpus vazio virava escalação, e o pipeline
        mandava ao humano pedidos que a política interna já autorizava.
        """
        with (
            patch("knowledge.retrieval.search", return_value=[]),
            patch("ai_assistant.services._run_json_completion") as modelo,
        ):
            parecer, _ = agents.emitir_parecer(criterios_validos(), policy=politica)

        modelo.assert_not_called()
        assert parecer["parecer"] == agents.PARECER_ADMISSIVEL
        assert parecer["origem"] == "sem_referencia"

    def test_recusa_sem_citacao_vira_decisao_humana(self, db, politica):
        """Citação é exigida para restringir, não para permitir."""
        with (
            patch("knowledge.retrieval.search", return_value=[trecho()]),
            patch(
                "ai_assistant.services._run_json_completion",
                return_value={
                    "parecer": "inadmissivel",
                    "fundamentacao": "Não pode.",
                    "citacoes": [],
                },
            ),
        ):
            parecer, _ = agents.emitir_parecer(criterios_validos(), policy=politica)

        assert parecer["parecer"] == agents.PARECER_ESCALONAR
        assert any("sem citação" in aviso for aviso in parecer["avisos"])

    def test_aprovacao_sem_citacao_permanece(self, db, politica):
        """Permitir não exige fonte: exigir citação para aprovar barraria o caso comum."""
        with (
            patch("knowledge.retrieval.search", return_value=[trecho()]),
            patch(
                "ai_assistant.services._run_json_completion",
                return_value={
                    "parecer": "admissivel",
                    "fundamentacao": "Nada na política impede.",
                    "citacoes": [],
                },
            ),
        ):
            parecer, _ = agents.emitir_parecer(criterios_validos(), policy=politica)

        assert parecer["parecer"] == agents.PARECER_ADMISSIVEL

    def test_vocabulario_invalido_vira_decisao_humana(self, db, politica):
        """Parecer fora das três palavras previstas não é interpretado por adivinhação."""
        with (
            patch("knowledge.retrieval.search", return_value=[trecho()]),
            patch(
                "ai_assistant.services._run_json_completion",
                return_value={
                    "parecer": "talvez",
                    "fundamentacao": "Depende.",
                    "citacoes": [1],
                },
            ),
        ):
            parecer, _ = agents.emitir_parecer(criterios_validos(), policy=politica)

        assert parecer["parecer"] == agents.PARECER_ESCALONAR
        assert any("vocabulário" in aviso for aviso in parecer["avisos"])

    def test_parecer_com_citacao_preserva_a_fonte(self, db, politica):
        """A fonte citada volta com instituição e link, para aparecer na resposta."""
        with (
            patch("knowledge.retrieval.search", return_value=[trecho(1), trecho(2)]),
            patch(
                "ai_assistant.services._run_json_completion",
                return_value={
                    "parecer": "admissivel",
                    "fundamentacao": "Compatível com o trecho 2.",
                    "citacoes": [2],
                },
            ),
        ):
            parecer, _ = agents.emitir_parecer(criterios_validos(), policy=politica)

        assert parecer["parecer"] == agents.PARECER_ADMISSIVEL
        assert [fonte["posicao"] for fonte in parecer["fontes"]] == [2]
        assert parecer["fontes"][0]["url"].endswith("2.pdf")


# --------------------------------------------------------------------- agente 3


class TestAlocadorDeEspaco:
    """O Agente 3 reserva, propõe alternativa ou escala — nunca inventa."""

    def test_parecer_de_escalonamento_nao_reserva(self, db, politica, sala, usuario):
        """Quando a política não cobre o caso, quem decide é uma pessoa."""
        decisao, _ = agents.alocar(
            criterios_validos(),
            {"parecer": agents.PARECER_ESCALONAR},
            usuario,
            policy=politica,
        )

        assert decisao["decisao"] == agents.DECISAO_ESCALONAMENTO
        assert decisao["reserva_id"] is None
        assert not Reservation.objects.exists()

    def test_admissivel_e_livre_cria_a_reserva(self, db, politica, sala, usuario):
        """Caminho feliz: o espaço atende, está livre e o parecer é favorável."""
        decisao, passo = agents.alocar(
            criterios_validos(),
            {"parecer": agents.PARECER_ADMISSIVEL},
            usuario,
            policy=politica,
        )

        assert decisao["decisao"] == agents.DECISAO_RESERVA
        reserva = Reservation.objects.get(pk=decisao["reserva_id"])
        assert reserva.space == sala
        assert reserva.user == usuario
        assert passo.agente == agents.AGENTE_ALOCADOR

    def test_horario_ocupado_gera_alternativas(self, db, politica, sala, usuario):
        """Ocupado não é escalação: o agente procura outro horário no mesmo dia."""
        criterios = criterios_validos()
        inicio = timezone.make_aware(
            datetime.datetime.combine(criterios["date"], criterios["start_time"])
        )
        Reservation.objects.create(
            space=sala,
            user=usuario,
            start_time=inicio,
            end_time=inicio + datetime.timedelta(minutes=120),
            status=ReservationStatus.CONFIRMED,
        )

        decisao, _ = agents.alocar(
            criterios, {"parecer": agents.PARECER_ADMISSIVEL}, usuario, policy=politica
        )

        assert decisao["decisao"] == agents.DECISAO_ALTERNATIVAS
        assert 1 <= len(decisao["alternativas"]) <= agents.MAX_ALTERNATIVAS
        assert decisao["reserva_id"] is None

    def test_nenhum_espaco_atende_escala(self, db, politica, sala, usuario):
        """Sem candidato, não há alternativa a propor."""
        decisao, _ = agents.alocar(
            criterios_validos(min_capacity=500),
            {"parecer": agents.PARECER_ADMISSIVEL},
            usuario,
            policy=politica,
        )

        assert decisao["decisao"] == agents.DECISAO_ESCALONAMENTO
        assert decisao["alternativas"] == []

    def test_dia_fechado_busca_alternativa_no_proximo_dia_aberto(self, db, politica, sala, usuario):
        """Regressão da rodada #01: pedido para domingo escalava em vez de sugerir segunda.

        Procurar horário livre só no dia pedido é inútil quando o problema é o próprio
        dia — o domingo não tem nenhum horário a oferecer, e a segunda está inteira vaga.
        """
        hoje = timezone.localdate()
        domingo = hoje + datetime.timedelta(days=(6 - hoje.weekday()) % 7 or 7)

        decisao, _ = agents.alocar(
            criterios_validos(date=domingo),
            {"parecer": agents.PARECER_INADMISSIVEL},
            usuario,
            policy=politica,
        )

        assert decisao["decisao"] == agents.DECISAO_ALTERNATIVAS
        assert decisao["alternativas"]
        segunda = domingo + datetime.timedelta(days=1)
        assert decisao["alternativas"][0]["inicio"].startswith(segunda.strftime("%d/%m"))

    def test_alternativas_respeitam_o_limite(self, db, politica, usuario):
        """Mais de três opções cansam quem lê; o agente corta em três."""
        tipo = SpaceType.objects.create(name="Reunião", slug="reuniao")
        for indice in range(6):
            Space.objects.create(
                name=f"Sala {indice}", capacity=20, location="Bloco B", space_type=tipo
            )

        decisao, _ = agents.alocar(
            criterios_validos(attributes=[], min_capacity=None),
            {"parecer": agents.PARECER_INADMISSIVEL},
            usuario,
            policy=politica,
        )

        assert len(decisao["alternativas"]) == agents.MAX_ALTERNATIVAS


# --------------------------------------------------------------------- pipeline


class TestPipeline:
    """As duas interrupções previstas na especificação."""

    def test_falta_de_dado_interrompe_antes_do_parecer(self, db, politica, usuario):
        """Sem data e horário não há o que consultar — o Agente 2 nem roda."""
        extraido = criterios_validos(date=None, start_time=None)
        extraido.pop("faltando")

        with (
            patch("ai_assistant.services.extract_room_search_filters", return_value=extraido),
            patch("ai_assistant.agents.emitir_parecer") as normativo,
        ):
            resultado = agents.executar_pipeline("quero uma sala", usuario, policy=politica)

        normativo.assert_not_called()
        assert resultado.decisao == agents.DECISAO_ESCLARECIMENTO
        assert len(resultado.passos) == 1

    def test_base_vazia_nao_impede_a_reserva(self, db, politica, sala, usuario):
        """Correção da rodada #02: sem referência, a política interna decide sozinha.

        Antes, corpus vazio derrubava todo pedido válido na mesa do administrador.
        """
        extraido = criterios_validos()
        extraido.pop("faltando")

        with (
            patch("ai_assistant.services.extract_room_search_filters", return_value=extraido),
            patch("knowledge.retrieval.search", return_value=[]),
        ):
            resultado = agents.executar_pipeline("sala amanhã", usuario, policy=politica)

        assert resultado.decisao == agents.DECISAO_RESERVA
        assert Reservation.objects.count() == 1
        assert [passo.agente for passo in resultado.passos] == [
            agents.AGENTE_INTERPRETE,
            agents.AGENTE_NORMATIVO,
            agents.AGENTE_ALOCADOR,
        ]

    def test_percurso_completo_soma_tempo_e_tokens(self, db, politica, sala, usuario):
        """O resultado carrega o custo de cada etapa, que é o que o relatório mede."""
        extraido = criterios_validos()
        extraido.pop("faltando")

        def gastar_tokens(*_args, usage_sink=None, **_kwargs):
            if usage_sink is not None:
                usage_sink.update({"total_tokens": 100})
            return {"parecer": "admissivel", "fundamentacao": "ok", "citacoes": [1]}

        with (
            patch("ai_assistant.services.extract_room_search_filters", return_value=extraido),
            patch("knowledge.retrieval.search", return_value=[trecho()]),
            patch("ai_assistant.services._run_json_completion", side_effect=gastar_tokens),
        ):
            resultado = agents.executar_pipeline("sala amanhã", usuario, policy=politica)

        assert resultado.decisao == agents.DECISAO_RESERVA
        assert resultado.total_tokens == 100
        assert resultado.duracao_ms >= 0
        assert resultado.espera_ms == 0
        relatorio = resultado.como_dict()
        assert relatorio["criterios"]["date"] == extraido["date"].isoformat()
        assert relatorio["espera_ms"] == 0
        assert relatorio["passos"][0]["espera_ms"] == 0

    def test_resultado_soma_espera_dos_passos(self):
        """Latência líquida e espera 429 viajam separados no relatório."""
        resultado = agents.ResultadoDoPipeline(pedido="x", decisao="y", mensagem="z")
        resultado.passos.append(
            agents.PassoDoAgente(agente="interprete", duracao_ms=80, espera_ms=1200)
        )
        resultado.passos.append(
            agents.PassoDoAgente(agente="normativo", duracao_ms=20, espera_ms=300)
        )

        assert resultado.duracao_ms == 100
        assert resultado.espera_ms == 1500
        assert resultado.como_dict()["espera_ms"] == 1500

    def test_equipamento_fora_do_catalogo_aparece_na_mensagem(self, db, politica, sala, usuario):
        """Descartar o requisito em silêncio entrega uma sala que não atende ao pedido."""
        extraido = criterios_validos(attributes=[], atributos_ignorados=["esteira ergométrica"])
        extraido.pop("faltando")

        with (
            patch("ai_assistant.services.extract_room_search_filters", return_value=extraido),
            patch("knowledge.retrieval.search", return_value=[]),
        ):
            resultado = agents.executar_pipeline(
                "sala com esteira ergométrica", usuario, policy=politica
            )

        assert resultado.decisao == agents.DECISAO_RESERVA
        assert "esteira" in resultado.mensagem
        assert "não consta no catálogo" in resultado.mensagem


def test_resumo_do_runner_separa_latencia_e_espera():
    """O bloco final do comando precisa mostrar trabalho e fila 429 à parte."""
    resumo = Command()._resumir(
        [
            {
                "duracao_ms": 100,
                "espera_ms": 40,
                "total_tokens": 10,
                "confere": True,
                "passos": [
                    {
                        "agente": "interprete",
                        "duracao_ms": 100,
                        "espera_ms": 40,
                        "tokens": {},
                        "erro": None,
                    }
                ],
            }
        ]
    )

    assert resumo["latencia_media_ms"] == 100
    assert resumo["espera_total_ms"] == 40
    assert resumo["espera_media_ms"] == 40
    assert resumo["por_agente"]["interprete"]["espera_media_ms"] == 40
