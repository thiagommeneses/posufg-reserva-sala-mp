"""Tests for the report metrics.

Um relatório errado não quebra nada: ele só faz alguém decidir errado. Por isso
a maior parte destes testes não confere se a função devolve alguma coisa — eles
conferem os casos em que a conta ingênua dá um número plausível e falso:

* reserva que começa antes de o prédio abrir (taxa acima de 100%);
* reserva no domingo, quando domingo não está no denominador;
* bloqueio de manutenção de madrugada contado como downtime;
* média de antecedência deslocada por um único agendamento remoto;
* zero de no-show quando ninguém está medindo;
* média de ocupação de capacidade calculada sobre três reservas de duzentas.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from reservations import relatorios
from reservations.models import BookingPolicy, MaintenanceBlock, Reservation, ReservationStatus
from services.enums import ServiceRequestStatus
from services.models import ReservationServiceRequest, ServiceType
from spaces.models import Space

User = get_user_model()

#: Uma semana inteira de segunda a domingo, fixa. Segunda 2026-03-09.
SEGUNDA = datetime.date(2026, 3, 9)
SABADO = datetime.date(2026, 3, 14)
DOMINGO = datetime.date(2026, 3, 15)


def local(date, hora, minuto=0):
    """Return an aware datetime in the local timezone."""
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hora, minuto)))


@pytest.fixture
def policy(db):
    """Return a policy that opens Monday to Friday, 08:00–18:00.

    Os dias são declarados porque estes testes **são** sobre o denominador, e
    ele depende de quais dias contam.
    """
    politica = BookingPolicy.carregar()
    politica.opening_time = datetime.time(8, 0)
    politica.closing_time = datetime.time(18, 0)
    politica.opens_saturday = False
    politica.opens_sunday = False
    politica.save()
    return politica


@pytest.fixture
def espaco(db):
    """Return a plain active space."""
    return Space.objects.create(name="Sala Alfa", capacity=10, location="1º andar")


@pytest.fixture
def usuario(db):
    """Return a user who can hold reservations."""
    return User.objects.create_user(username="dono", password="senha-de-teste-123")


@pytest.fixture
def semana():
    """Return the [Monday, next Monday) window as aware datetimes."""
    inicio = local(SEGUNDA, 0)
    return inicio, inicio + datetime.timedelta(days=7)


def reserva(espaco, usuario, dia, inicio, fim, **extra):
    """Create a confirmed reservation on a given local day."""
    campos = {
        "space": espaco,
        "user": usuario,
        "start_time": local(dia, inicio),
        "end_time": local(dia, fim),
        "status": ReservationStatus.CONFIRMED,
    }
    campos.update(extra)
    return Reservation.objects.create(**campos)


@pytest.mark.django_db
class TestExpediente:
    """The denominator every time metric divides by."""

    def test_a_semana_tem_cinco_dias_de_dez_horas(self, policy, semana):
        """Segunda a sexta, 8h–18h: 3000 minutos. Sábado e domingo não entram."""
        assert relatorios.minutos_de_expediente(*semana, policy) == 5 * 10 * 60

    def test_o_periodo_recorta_a_janela_do_dia(self, policy):
        """Um período que começa às 10h não ganha as duas horas anteriores."""
        inicio = local(SEGUNDA, 10)
        fim = local(SEGUNDA, 12)
        assert relatorios.minutos_de_expediente(inicio, fim, policy) == 120

    def test_periodo_inteiramente_fora_do_expediente_nao_tem_janela(self, policy):
        """Entre 19h e 20h o prédio está fechado; não há o que dividir."""
        inicio = local(SEGUNDA, 19)
        fim = local(SEGUNDA, 20)
        assert relatorios.janelas_abertas(inicio, fim, policy) == []
        assert relatorios.minutos_de_expediente(inicio, fim, policy) == 0

    def test_fim_de_semana_sozinho_nao_tem_expediente(self, policy):
        """Um relatório de sábado a domingo não divide por zero nem inventa horas."""
        inicio = local(SABADO, 0)
        fim = local(DOMINGO, 23, 59)
        assert relatorios.minutos_de_expediente(inicio, fim, policy) == 0


@pytest.mark.django_db
class TestOcupacao:
    """Where a naive sum produces a plausible, wrong number."""

    def test_reserva_dentro_da_janela_conta_inteira(self, policy, espaco, usuario, semana):
        """Duas horas numa semana de 3000 minutos."""
        reserva(espaco, usuario, SEGUNDA, 9, 11)
        linha = relatorios.ocupacao_por_espaco(*semana, policy)[0]
        assert linha["minutos_ocupados"] == 120
        assert linha["taxa"] == pytest.approx(120 / 3000)

    def test_reserva_que_extravasa_a_janela_e_recortada(self, policy, espaco, usuario, semana):
        """Das 7h às 19h o prédio só esteve aberto dez horas.

        Sem o recorte a reserva somaria doze horas contra um denominador que só
        tem dez por dia — e a taxa passaria de 100% sem que ninguém entendesse
        por quê.
        """
        reserva(espaco, usuario, SEGUNDA, 7, 19)
        linha = relatorios.ocupacao_por_espaco(*semana, policy)[0]
        assert linha["minutos_ocupados"] == 600
        assert linha["taxa"] <= 1.0

    def test_reserva_no_dia_fechado_nao_conta(self, policy, espaco, usuario, semana):
        """Domingo não está no denominador, então não pode estar no numerador.

        Uma reserva de domingo existe — foi feita antes da regra, ou com a
        recusa desligada —, mas contá-la contra um denominador que ignora
        domingo é como a ocupação passa de 100% em bases antigas.
        """
        reserva(espaco, usuario, DOMINGO, 9, 11)
        linha = relatorios.ocupacao_por_espaco(*semana, policy)[0]
        assert linha["minutos_ocupados"] == 0

    def test_a_borda_do_periodo_recorta(self, policy, espaco, usuario):
        """Reserva que atravessa o fim do período só conta o pedaço de dentro."""
        reserva(espaco, usuario, SEGUNDA, 9, 17)
        inicio = local(SEGUNDA, 0)
        fim = local(SEGUNDA, 12)
        linha = relatorios.ocupacao_por_espaco(inicio, fim, policy)[0]
        assert linha["minutos_ocupados"] == 180  # 9h–12h

    def test_o_no_show_nao_conta_como_ocupacao(self, policy, espaco, usuario, semana):
        """O espaço esteve reservado e não foi usado.

        Contar isso como ocupação transformaria desperdício em produtividade —
        exatamente o que a métrica existe para revelar.
        """
        reserva(espaco, usuario, SEGUNDA, 9, 11, status=ReservationStatus.NO_SHOW)
        linha = relatorios.ocupacao_por_espaco(*semana, policy)[0]
        assert linha["minutos_ocupados"] == 0

    def test_a_cancelada_nao_conta_como_ocupacao(self, policy, espaco, usuario, semana):
        """Cancelada libera o espaço; ele ficou livre."""
        reserva(espaco, usuario, SEGUNDA, 9, 11, status=ReservationStatus.CANCELLED)
        assert relatorios.ocupacao_por_espaco(*semana, policy)[0]["minutos_ocupados"] == 0

    def test_a_contagem_de_reservas_bate_com_os_minutos(
        self, policy, espaco, usuario, semana
    ):
        """Quatro reservas de fim de semana e uma de terça valem "1 reserva".

        A verificação contra a base real pegou isto: o espaço aparecia com
        "4 reservas" e 60 minutos, porque a contagem incluía as que o recorte
        tinha zerado. Quem dividisse uma coluna pela outra concluiria que a
        reserva média dura quinze minutos.
        """
        reserva(espaco, usuario, DOMINGO, 9, 11)
        reserva(espaco, usuario, SABADO, 9, 11)
        reserva(espaco, usuario, SEGUNDA, 9, 10)
        linha = relatorios.ocupacao_por_espaco(*semana, policy)[0]
        assert linha["minutos_ocupados"] == 60
        assert linha["reservas"] == 1

    def test_espaco_sem_reserva_aparece_com_zero(self, policy, espaco, semana):
        """Subutilização é informação: o espaço vazio precisa aparecer na lista."""
        linhas = relatorios.ocupacao_por_espaco(*semana, policy)
        assert len(linhas) == 1
        assert linhas[0]["minutos_ocupados"] == 0
        assert linhas[0]["taxa"] == 0.0

    def test_espaco_inativo_continua_no_relatorio(self, policy, espaco, usuario, semana):
        """Desativado ontem, ocupou tempo real até ontem."""
        reserva(espaco, usuario, SEGUNDA, 9, 11)
        espaco.is_active = False
        espaco.save(update_fields=["is_active"])
        assert relatorios.ocupacao_por_espaco(*semana, policy)[0]["minutos_ocupados"] == 120

    def test_ordena_do_mais_ocupado_para_o_menos(self, policy, espaco, usuario, semana):
        """Quem lê procura os extremos, e o topo é o que dói."""
        outro = Space.objects.create(name="Sala Beta", capacity=6, location="2º andar")
        reserva(espaco, usuario, SEGUNDA, 9, 10)
        reserva(outro, usuario, SEGUNDA, 9, 13)
        linhas = relatorios.ocupacao_por_espaco(*semana, policy)
        assert [linha["espaco"].name for linha in linhas] == ["Sala Beta", "Sala Alfa"]


@pytest.mark.django_db
class TestPicos:
    """When the building is busiest."""

    def test_reserva_longa_marca_todas_as_horas_que_ocupa(self, policy, espaco, usuario, semana):
        """Das 9h às 12h o prédio esteve ocupado nas três horas.

        Contar a reserva só na hora em que começa faria o meio da manhã parecer
        vazio — e é justamente o meio da manhã que costuma ser o pico.
        """
        reserva(espaco, usuario, SEGUNDA, 9, 12)
        por_hora = {
            linha["hora"]: linha["reservas"]
            for linha in relatorios.picos(*semana, policy)["por_hora"]
        }
        assert por_hora[9] == 1
        assert por_hora[10] == 1
        assert por_hora[11] == 1
        assert por_hora[12] == 0

    def test_a_hora_do_pico_soma_reservas_simultaneas(self, policy, espaco, usuario, semana):
        """Duas salas ocupadas às 10h valem dois."""
        outro = Space.objects.create(name="Sala Beta", capacity=6, location="2º andar")
        reserva(espaco, usuario, SEGUNDA, 10, 11)
        reserva(outro, usuario, SEGUNDA, 10, 11)
        por_hora = {
            linha["hora"]: linha["reservas"]
            for linha in relatorios.picos(*semana, policy)["por_hora"]
        }
        assert por_hora[10] == 2

    def test_so_os_dias_abertos_aparecem(self, policy, semana):
        """Um gráfico com sábado e domingo sempre em zero não informa nada."""
        dias = [linha["rotulo"] for linha in relatorios.picos(*semana, policy)["por_dia_da_semana"]]
        assert dias == ["Seg", "Ter", "Qua", "Qui", "Sex"]

    def test_a_faixa_de_horas_cobre_a_janela(self, policy, semana):
        """Da abertura ao fechamento, mesmo sem nenhuma reserva."""
        horas = [linha["hora"] for linha in relatorios.picos(*semana, policy)["por_hora"]]
        assert horas[0] == 8
        assert horas[-1] == 17


@pytest.mark.django_db
class TestCancelamentosENoShow:
    """Counts, and what sustains them."""

    def test_a_taxa_usa_as_reservas_do_periodo(self, policy, espaco, usuario, semana):
        """Uma cancelada em quatro marcadas é 25%."""
        for hora in (9, 11, 14):
            reserva(espaco, usuario, SEGUNDA, hora, hora + 1)
        reserva(espaco, usuario, SEGUNDA, 16, 17, status=ReservationStatus.CANCELLED)
        resumo = relatorios.cancelamentos(*semana)
        assert resumo["total"] == 1
        assert resumo["marcadas_no_periodo"] == 4
        assert resumo["taxa"] == pytest.approx(0.25)

    def test_periodo_vazio_nao_divide_por_zero(self, policy, semana):
        """Sem reserva nenhuma a taxa é zero, não uma exceção."""
        assert relatorios.cancelamentos(*semana)["taxa"] == 0.0
        assert relatorios.no_shows(*semana, policy)["taxa"] == 0.0

    def test_o_no_show_diz_se_alguem_esta_medindo(self, policy, semana):
        """Zero por não haver faltas e zero por não haver medição são opostos.

        Com ``release_no_shows`` desligado — o padrão — nada no sistema marca
        no-show. O número sozinho seria lido como boa notícia.
        """
        assert policy.release_no_shows is False
        resumo = relatorios.no_shows(*semana, policy)
        assert resumo["total"] == 0
        assert resumo["regra_ligada"] is False

    def test_com_a_regra_ligada_o_relatorio_diz_isso(self, policy, semana):
        """Ligada, o zero passa a significar o que parece significar."""
        policy.release_no_shows = True
        policy.save(update_fields=["release_no_shows"])
        assert relatorios.no_shows(*semana, policy)["regra_ligada"] is True

    def test_conta_o_no_show_que_existe(self, policy, espaco, usuario, semana):
        """Marcado à mão ou pela rotina, ele entra."""
        reserva(espaco, usuario, SEGUNDA, 9, 10, status=ReservationStatus.NO_SHOW)
        assert relatorios.no_shows(*semana, policy)["total"] == 1


@pytest.mark.django_db
class TestManutencao:
    """Downtime is time lost from the working day."""

    def test_bloqueio_no_expediente_e_downtime(self, policy, espaco, usuario, semana):
        """Duas horas de manhã são duas horas que ninguém pôde reservar."""
        MaintenanceBlock.objects.create(
            space=espaco,
            start_time=local(SEGUNDA, 9),
            end_time=local(SEGUNDA, 11),
            reason="Troca do projetor",
            created_by=usuario,
        )
        linha = relatorios.downtime_de_manutencao(*semana, policy)[0]
        assert linha["minutos"] == 120
        assert linha["bloqueios"] == 1

    def test_bloqueio_de_madrugada_nao_e_downtime(self, policy, espaco, usuario, semana):
        """Manutenção fora do expediente é a bem planejada.

        Contá-la como downtime faria a equipe que trabalha de madrugada — para
        não atrapalhar ninguém — aparecer como a maior causa de parada.
        """
        MaintenanceBlock.objects.create(
            space=espaco,
            start_time=local(SEGUNDA, 0),
            end_time=local(SEGUNDA, 6),
            reason="Limpeza pesada",
            created_by=usuario,
        )
        assert relatorios.downtime_de_manutencao(*semana, policy) == []

    def test_bloqueio_que_atravessa_a_abertura_e_recortado(self, policy, espaco, usuario, semana):
        """Das 6h às 10h, só duas horas caem no expediente."""
        MaintenanceBlock.objects.create(
            space=espaco,
            start_time=local(SEGUNDA, 6),
            end_time=local(SEGUNDA, 10),
            reason="Elétrica",
            created_by=usuario,
        )
        assert relatorios.downtime_de_manutencao(*semana, policy)[0]["minutos"] == 120


@pytest.mark.django_db
class TestServicos:
    """What the operation was asked for."""

    def test_agrupa_por_servico_e_situacao(self, policy, espaco, usuario, semana):
        """A copa quer saber quanto café, e quanto dele ainda está na fila."""
        cafe = ServiceType.objects.create(name="Café e água", slug="cafe-teste")
        limpeza = ServiceType.objects.create(name="Limpeza", slug="limpeza-teste")
        primeira = reserva(espaco, usuario, SEGUNDA, 9, 10)
        segunda = reserva(espaco, usuario, SEGUNDA, 11, 12)
        ReservationServiceRequest.objects.create(reservation=primeira, service_type=cafe)
        ReservationServiceRequest.objects.create(
            reservation=segunda, service_type=cafe, status=ServiceRequestStatus.COMPLETED
        )
        ReservationServiceRequest.objects.create(reservation=primeira, service_type=limpeza)

        linhas = relatorios.servicos(*semana)
        assert linhas[0]["servico"] == "Café e água"
        assert linhas[0]["total"] == 2
        assert linhas[0]["por_situacao"] == {"Solicitado": 1, "Concluído": 1}
        assert linhas[1]["total"] == 1

    def test_pedido_de_reserva_fora_do_periodo_nao_entra(self, policy, espaco, usuario):
        """A âncora é o horário da reserva, não o da solicitação."""
        cafe = ServiceType.objects.create(name="Café e água", slug="cafe-teste")
        fora = reserva(espaco, usuario, SEGUNDA + datetime.timedelta(days=30), 9, 10)
        ReservationServiceRequest.objects.create(reservation=fora, service_type=cafe)
        inicio = local(SEGUNDA, 0)
        assert relatorios.servicos(inicio, inicio + datetime.timedelta(days=7)) == []


@pytest.mark.django_db
class TestAntecedencia:
    """How far ahead people book."""

    def test_devolve_media_e_mediana(self, policy, espaco, usuario, semana):
        """A média sozinha esconde o que a maioria faz.

        Três reservas de véspera e uma feita com muito tempo: a média sugere
        planejamento, a mediana mostra a correria.
        """
        criadas = [
            (local(SEGUNDA, 9), local(SEGUNDA - datetime.timedelta(days=1), 9)),
            (local(SEGUNDA, 11), local(SEGUNDA - datetime.timedelta(days=1), 11)),
            (local(SEGUNDA, 14), local(SEGUNDA - datetime.timedelta(days=1), 14)),
            (local(SEGUNDA, 16), local(SEGUNDA - datetime.timedelta(days=60), 16)),
        ]
        for comeco, criada in criadas:
            item = Reservation.objects.create(
                space=espaco,
                user=usuario,
                start_time=comeco,
                end_time=comeco + datetime.timedelta(hours=1),
                status=ReservationStatus.CONFIRMED,
            )
            Reservation.objects.filter(pk=item.pk).update(created_at=criada)

        resumo = relatorios.antecedencia(*semana)
        assert resumo["amostra"] == 4
        assert resumo["mediana_horas"] == pytest.approx(24, abs=1)
        # A média é arrastada pela reserva de dois meses antes.
        assert resumo["media_horas"] > resumo["mediana_horas"] * 3

    def test_sem_reserva_devolve_nulo_e_nao_zero(self, policy, semana):
        """Zero hora de antecedência é uma afirmação; "não sei" é outra."""
        resumo = relatorios.antecedencia(*semana)
        assert resumo["media_horas"] is None
        assert resumo["amostra"] == 0

    def test_antecedencia_negativa_e_descartada(self, policy, espaco, usuario, semana):
        """Ninguém reserva o passado.

        Linhas semeadas podem ter ``created_at`` posterior ao início; entrariam
        puxando a média para baixo como se alguém tivesse agendado para trás.
        """
        item = reserva(espaco, usuario, SEGUNDA, 9, 10)
        Reservation.objects.filter(pk=item.pk).update(created_at=local(SEGUNDA, 17))
        assert relatorios.antecedencia(*semana)["amostra"] == 0


@pytest.mark.django_db
class TestSubutilizacao:
    """How full the booked rooms were — and how much of that is known."""

    def test_a_taxa_e_participantes_sobre_capacidade(self, policy, espaco, usuario, semana):
        """Quatro pessoas numa sala de dez é 40%."""
        reserva(espaco, usuario, SEGUNDA, 9, 10, attendee_count=4)
        linha = relatorios.subutilizacao(*semana)[0]
        assert linha["media_participantes"] == 4
        assert linha["taxa"] == pytest.approx(0.4)

    def test_a_cobertura_viaja_junto(self, policy, espaco, usuario, semana):
        """Uma média sobre uma reserva de quatro não representa as outras três.

        Sem a cobertura, quem lê decide desativar uma sala com base em uma
        linha — e é o tipo de decisão que este relatório existe para embasar.
        """
        reserva(espaco, usuario, SEGUNDA, 9, 10, attendee_count=4)
        reserva(espaco, usuario, SEGUNDA, 11, 12)
        reserva(espaco, usuario, SEGUNDA, 14, 15)
        linha = relatorios.subutilizacao(*semana)[0]
        assert linha["com_informacao"] == 1
        assert linha["total"] == 3

    def test_espaco_sem_nenhuma_informacao_fica_de_fora(self, policy, espaco, usuario, semana):
        """Sem participantes informados não há o que afirmar sobre lotação."""
        reserva(espaco, usuario, SEGUNDA, 9, 10)
        assert relatorios.subutilizacao(*semana) == []

    def test_ordena_da_menor_taxa_para_a_maior(self, policy, espaco, usuario, semana):
        """A subutilização é o que se procura, então vem primeiro."""
        outro = Space.objects.create(name="Sala Beta", capacity=4, location="2º andar")
        reserva(espaco, usuario, SEGUNDA, 9, 10, attendee_count=2)  # 2/10
        reserva(outro, usuario, SEGUNDA, 9, 10, attendee_count=3)  # 3/4
        linhas = relatorios.subutilizacao(*semana)
        assert [linha["espaco"] for linha in linhas] == ["Sala Alfa", "Sala Beta"]


class TestPeriodo:
    """The period selector — whole local days, and no surprises from bad input.

    Sem banco de propósito: o cálculo do período é aritmética de calendário, e
    passar ``hoje`` explicitamente é o que impede estes testes de mudarem de
    resultado conforme o dia em que a suíte roda.
    """

    def test_ultimos_dias_incluem_hoje_sem_estourar_a_contagem(self):
        """"Últimos 7 dias" cobre sete, não oito.

        É o erro clássico de intervalo fechado: recuar sete dias a partir de
        hoje e incluir os dois extremos dá oito.
        """
        hoje = datetime.date(2026, 3, 11)
        periodo = relatorios.periodo_pedido("7", hoje=hoje)
        assert periodo["primeiro_dia"] == datetime.date(2026, 3, 5)
        assert periodo["ultimo_dia"] == hoje
        assert (periodo["ultimo_dia"] - periodo["primeiro_dia"]).days + 1 == 7

    def test_o_fim_e_a_meia_noite_do_dia_seguinte(self):
        """O último dia entra inteiro; o período é fechado à esquerda e aberto à direita."""
        hoje = datetime.date(2026, 3, 11)
        periodo = relatorios.periodo_pedido("7", hoje=hoje)
        assert periodo["inicio"] == local(datetime.date(2026, 3, 5), 0)
        assert periodo["fim"] == local(datetime.date(2026, 3, 12), 0)

    def test_mes_atual_comeca_no_dia_primeiro(self):
        """Mês em curso vai do dia 1º até hoje."""
        periodo = relatorios.periodo_pedido("mes", hoje=datetime.date(2026, 3, 11))
        assert periodo["primeiro_dia"] == datetime.date(2026, 3, 1)
        assert periodo["ultimo_dia"] == datetime.date(2026, 3, 11)

    def test_mes_anterior_pega_o_mes_inteiro(self):
        """Fevereiro de 2026 tem 28 dias, e o período precisa dar conta disso."""
        periodo = relatorios.periodo_pedido("mes_anterior", hoje=datetime.date(2026, 3, 11))
        assert periodo["primeiro_dia"] == datetime.date(2026, 2, 1)
        assert periodo["ultimo_dia"] == datetime.date(2026, 2, 28)

    def test_mes_anterior_a_partir_de_janeiro_volta_para_dezembro(self):
        """A virada do ano é onde a aritmética de mês costuma quebrar."""
        periodo = relatorios.periodo_pedido("mes_anterior", hoje=datetime.date(2026, 1, 5))
        assert periodo["primeiro_dia"] == datetime.date(2025, 12, 1)
        assert periodo["ultimo_dia"] == datetime.date(2025, 12, 31)

    def test_datas_digitadas_valem_mais_que_o_preset(self):
        """Quem escolheu as datas escolheu as datas."""
        periodo = relatorios.periodo_pedido(
            "30", de="2026-02-10", ate="2026-02-20", hoje=datetime.date(2026, 3, 11)
        )
        assert periodo["primeiro_dia"] == datetime.date(2026, 2, 10)
        assert periodo["ultimo_dia"] == datetime.date(2026, 2, 20)
        assert periodo["preset"] == ""

    def test_datas_invertidas_caem_no_padrao(self):
        """Fim antes do início é URL editada, não pedido a atender."""
        periodo = relatorios.periodo_pedido(
            de="2026-02-20", ate="2026-02-10", hoje=datetime.date(2026, 3, 11)
        )
        assert periodo["preset"] == relatorios.PRESET_PADRAO

    def test_data_quebrada_cai_no_padrao(self):
        """Uma tela com números verdadeiros vale mais que uma página de erro."""
        periodo = relatorios.periodo_pedido(
            de="31/02/2026", ate="oi", hoje=datetime.date(2026, 3, 11)
        )
        assert periodo["preset"] == relatorios.PRESET_PADRAO
        assert periodo["ultimo_dia"] == datetime.date(2026, 3, 11)

    def test_preset_inventado_cai_no_padrao(self):
        """Link velho continua abrindo um relatório."""
        periodo = relatorios.periodo_pedido("decada", hoje=datetime.date(2026, 3, 11))
        assert periodo["preset"] == relatorios.PRESET_PADRAO

    def test_o_rotulo_do_periodo_digitado_diz_as_datas(self):
        """Sem preset não há nome pronto; a tela precisa dizer a faixa."""
        periodo = relatorios.periodo_pedido(
            de="2026-02-10", ate="2026-02-20", hoje=datetime.date(2026, 3, 11)
        )
        assert periodo["rotulo"] == "10/02/2026 a 20/02/2026"
