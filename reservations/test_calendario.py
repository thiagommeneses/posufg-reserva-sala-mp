"""Tests for the user calendar — the grid, and above all the privacy.

O que esta camada faz de arriscado é mostrar a agenda de um prédio inteiro para
alguém que só tem direito a ver a própria. Por isso a maior parte dos testes
abaixo não olha layout: olha o que **não** aparece, e o que **nem sequer sai do
banco**.

O calendário não tem estado no cliente, então tudo aqui é exercitado pela
querystring — que é também por onde um curioso tentaria burlar a tela.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from reservations import calendario
from reservations.models import BookingPolicy, MaintenanceBlock, Reservation, ReservationStatus
from spaces.models import Space

User = get_user_model()


def local(date, hora, minuto=0):
    """Return an aware datetime in the local timezone."""
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hora, minuto)))


@pytest.fixture
def policy(db):
    """Return the booking policy with the seeded defaults."""
    return BookingPolicy.carregar()


@pytest.fixture
def espaco(db):
    """Return a plain active space."""
    return Space.objects.create(name="Sala Alfa", capacity=8, location="1º andar")


@pytest.fixture
def dono(db):
    """Return the person looking at their own calendar."""
    return User.objects.create_user(username="dono", password="senha-de-teste-123")


@pytest.fixture
def outra_pessoa(db):
    """Return somebody else, whose subjects must never leak."""
    return User.objects.create_user(username="alheio", password="senha-de-teste-123")


@pytest.fixture
def logado(client, dono):
    """Return a client logged in as the owner."""
    client.force_login(dono)
    return client


@pytest.fixture
def dia_fixo():
    """Return a date that never depends on when the suite runs.

    Uma quarta-feira no meio de um mês, longe das bordas: assim a semana tem
    dias antes e depois, e a grade do mês tem vizinhos dos dois lados.
    """
    return datetime.date(2026, 3, 11)


def reserva(espaco, user, dia, inicio, fim, **extra):
    """Create a confirmed reservation on a given local day."""
    campos = {
        "space": espaco,
        "user": user,
        "start_time": local(dia, inicio),
        "end_time": local(dia, fim),
        "status": ReservationStatus.CONFIRMED,
    }
    campos.update(extra)
    return Reservation.objects.create(**campos)


class TestLeituraDaQuerystring:
    """What the screen does with what the URL says."""

    def test_vista_invalida_cai_no_mes(self):
        """Uma vista inventada não é erro do usuário: é URL editada."""
        assert calendario.normalizar_vista("trimestre") == calendario.VISTA_MES
        assert calendario.normalizar_vista(None) == calendario.VISTA_MES

    def test_vistas_validas_passam(self):
        """As três visões do pacote V2 são aceitas como vieram."""
        for vista in calendario.VISTAS:
            assert calendario.normalizar_vista(vista) == vista

    def test_data_invalida_cai_em_hoje(self):
        """Data quebrada mostra um calendário verdadeiro, não uma página de erro."""
        hoje = datetime.date(2026, 3, 11)
        assert calendario.data_pedida("31/02/2026", hoje=hoje) == hoje
        assert calendario.data_pedida("", hoje=hoje) == hoje
        assert calendario.data_pedida(None, hoje=hoje) == hoje

    def test_data_valida_e_respeitada(self):
        """Uma data legítima manda no calendário."""
        assert calendario.data_pedida("2026-07-04") == datetime.date(2026, 7, 4)


class TestGrade:
    """The shape of each view."""

    def test_mes_comeca_no_domingo(self, dia_fixo):
        """A semana brasileira começa no domingo, e a grade também."""
        dias = calendario.dias_da_grade(calendario.VISTA_MES, dia_fixo)
        assert dias[0].weekday() == 6
        assert len(dias) % 7 == 0

    def test_mes_inclui_os_vizinhos_que_aparecem_na_tela(self):
        """Abril de 2026 começa numa quarta: a primeira linha tem três dias de março.

        Eles aparecem na tela, então precisam entrar na busca — senão a grade
        mostraria dias vazios que não estão vazios.
        """
        dias = calendario.dias_da_grade(calendario.VISTA_MES, datetime.date(2026, 4, 15))
        assert dias[0] == datetime.date(2026, 3, 29)
        assert dias[-1].weekday() == 5
        # O mês inteiro está lá, do primeiro ao último dia.
        assert datetime.date(2026, 4, 1) in dias
        assert datetime.date(2026, 4, 30) in dias

    def test_mes_que_comeca_no_domingo_nao_ganha_linha_falsa(self):
        """Março de 2026 começa num domingo: a grade começa no dia 1º.

        Uma semana inteira de dias do mês anterior antes do primeiro seria uma
        linha inútil ocupando a tela.
        """
        dias = calendario.dias_da_grade(calendario.VISTA_MES, datetime.date(2026, 3, 11))
        assert dias[0] == datetime.date(2026, 3, 1)

    def test_semana_tem_sete_dias_contendo_o_pedido(self, dia_fixo):
        """A semana exibida é a do dia pedido, do domingo ao sábado."""
        dias = calendario.dias_da_grade(calendario.VISTA_SEMANA, dia_fixo)
        assert len(dias) == 7
        assert dia_fixo in dias
        assert dias[0].weekday() == 6

    def test_dia_tem_um_dia(self, dia_fixo):
        """A visão de dia mostra exatamente o dia pedido."""
        assert calendario.dias_da_grade(calendario.VISTA_DIA, dia_fixo) == [dia_fixo]

    @pytest.mark.django_db
    def test_semana_entre_dois_meses_nomeia_os_dois(self, dono, policy):
        """"30 a 5 de setembro" seria mentira: o 30 é de agosto.

        A semana de 30/08 a 05/09 de 2026 atravessa a virada do mês, e o título
        precisa dizer isso — é a única pista de onde a pessoa está.
        """
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_SEMANA, datetime.date(2026, 9, 2), policy=policy
        )
        assert contexto["titulo"] == "30 de agosto a 5 de setembro"

    @pytest.mark.django_db
    def test_semana_dentro_de_um_mes_nao_repete_o_mes(self, dono, policy):
        """Dentro do mesmo mês, dizer o nome duas vezes é ruído."""
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_SEMANA, datetime.date(2026, 3, 11), policy=policy
        )
        assert contexto["titulo"] == "8 a 14 de março"

    @pytest.mark.django_db
    def test_navegacao_do_mes_nao_pula_meses(self, dono, policy):
        """31 de março menos um mês tem de cair em fevereiro, não em 31/02.

        Somar e subtrair "um mês" a partir do dia corrente é o jeito errado
        clássico: dias 29, 30 e 31 estouram nos meses curtos.
        """
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_MES, datetime.date(2026, 3, 31), policy=policy
        )
        assert contexto["anterior"] == datetime.date(2026, 2, 1)
        assert contexto["proximo"] == datetime.date(2026, 4, 1)


@pytest.mark.django_db
class TestPrivacidade:
    """The rule the whole module exists to protect."""

    def test_reserva_de_terceiro_nao_aparece_por_padrao(
        self, dono, outra_pessoa, espaco, policy, dia_fixo
    ):
        """O padrão do pacote V2 é "próprias reservas"."""
        reserva(espaco, outra_pessoa, dia_fixo, 9, 10, title="Reunião do gabinete")
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        assert contexto["total"] == 0

    def test_reserva_de_terceiro_aparece_como_ocupado(
        self, dono, outra_pessoa, espaco, policy, dia_fixo
    ):
        """Com a ocupação ligada, o horário aparece — o assunto, não."""
        reserva(espaco, outra_pessoa, dia_fixo, 9, 10, title="Reunião do gabinete")
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, incluir_ocupacao=True, policy=policy
        )
        entradas = contexto["celula"]["entradas"]
        assert len(entradas) == 1
        assert entradas[0]["rotulo"] == calendario.OCUPADO
        assert entradas[0]["propria"] is False

    def test_o_assunto_alheio_nao_chega_a_ser_buscado(
        self, dono, outra_pessoa, espaco, policy, dia_fixo
    ):
        """A proteção é o ``values()``, não o template.

        Este teste afirma sobre o contexto inteiro, e não sobre o HTML: se o
        assunto entrasse na estrutura, bastaria um ``{{ entrada }}`` distraído
        para publicá-lo. Não estando lá, nenhum template pode vazá-lo.
        """
        reserva(espaco, outra_pessoa, dia_fixo, 9, 10, title="Sindicância 2026/44")
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, incluir_ocupacao=True, policy=policy
        )
        assert "Sindicância" not in repr(contexto)
        assert "alheio" not in repr(contexto)

    def test_entrada_alheia_nao_carrega_identificador(
        self, dono, outra_pessoa, espaco, policy, dia_fixo
    ):
        """Sem ``pk`` não há URL a construir — e não há recusa a explicar."""
        reserva(espaco, outra_pessoa, dia_fixo, 9, 10, title="Reunião")
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, incluir_ocupacao=True, policy=policy
        )
        assert contexto["celula"]["entradas"][0]["pk"] is None

    def test_a_propria_reserva_mostra_o_assunto(self, dono, espaco, policy, dia_fixo):
        """A privacidade é dos outros: a pessoa vê a própria reserva inteira."""
        minha = reserva(espaco, dono, dia_fixo, 14, 15, title="Alinhamento da equipe")
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        entrada = contexto["celula"]["entradas"][0]
        assert entrada["rotulo"] == "Alinhamento da equipe"
        assert entrada["pk"] == minha.pk
        assert entrada["propria"] is True

    def test_reserva_sem_assunto_usa_o_nome_do_espaco(self, dono, espaco, policy, dia_fixo):
        """Reservas antigas não têm assunto; inventar um seria dado falso."""
        reserva(espaco, dono, dia_fixo, 14, 15)
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        assert contexto["celula"]["entradas"][0]["rotulo"] == espaco.name

    def test_reserva_cancelada_nao_ocupa_o_calendario(self, dono, espaco, policy, dia_fixo):
        """Cancelada não segura o espaço, então não aparece como ocupação."""
        reserva(espaco, dono, dia_fixo, 9, 10, status=ReservationStatus.CANCELLED)
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, incluir_ocupacao=True, policy=policy
        )
        assert contexto["total"] == 0

    def test_manutencao_aparece_sem_o_motivo(
        self, dono, outra_pessoa, espaco, policy, dia_fixo
    ):
        """O bloqueio é ocupação real; o motivo é texto administrativo."""
        MaintenanceBlock.objects.create(
            space=espaco,
            start_time=local(dia_fixo, 8),
            end_time=local(dia_fixo, 12),
            reason="Infiltração no forro, orçamento 3312",
            created_by=outra_pessoa,
        )
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, incluir_ocupacao=True, policy=policy
        )
        entrada = contexto["celula"]["entradas"][0]
        assert entrada["rotulo"] == calendario.MANUTENCAO
        assert "Infiltração" not in repr(contexto)


@pytest.mark.django_db
class TestDistribuicao:
    """Which day each entry lands on."""

    def test_reserva_que_atravessa_a_meia_noite_aparece_nos_dois_dias(
        self, dono, espaco, policy, dia_fixo
    ):
        """Ela ocupa os dois dias na vida real; omitir o segundo esconderia isso."""
        Reservation.objects.create(
            space=espaco,
            user=dono,
            start_time=local(dia_fixo, 22),
            end_time=local(dia_fixo + datetime.timedelta(days=1), 2),
            status=ReservationStatus.CONFIRMED,
            title="Apuração",
        )
        hoje = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        amanha = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo + datetime.timedelta(days=1), policy=policy
        )
        assert hoje["celula"]["quantidade"] == 1
        assert amanha["celula"]["quantidade"] == 1

    def test_o_dia_seguinte_mostra_o_pedaco_dele(self, dono, espaco, policy, dia_fixo):
        """No dia seguinte a reserva começa à meia-noite, não às 22h.

        Sem o recorte, a grade de horas do dia seguinte seria montada em volta
        de uma hora que não acontece ali.
        """
        Reservation.objects.create(
            space=espaco,
            user=dono,
            start_time=local(dia_fixo, 22),
            end_time=local(dia_fixo + datetime.timedelta(days=1), 2),
            status=ReservationStatus.CONFIRMED,
        )
        amanha = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo + datetime.timedelta(days=1), policy=policy
        )
        entrada = amanha["celula"]["entradas"][0]
        assert entrada["inicio_no_dia"].hour == 0
        assert entrada["vem_de_ontem"] is True
        assert entrada["segue_amanha"] is False
        assert any(linha["hora"] == 0 and linha["entradas"] for linha in amanha["horas"])

    def test_reserva_que_termina_na_virada_nao_invade_o_dia_seguinte(
        self, dono, espaco, policy, dia_fixo
    ):
        """Terminar às 00:00 não ocupa nada do dia que começa ali."""
        Reservation.objects.create(
            space=espaco,
            user=dono,
            start_time=local(dia_fixo, 22),
            end_time=local(dia_fixo + datetime.timedelta(days=1), 0),
            status=ReservationStatus.CONFIRMED,
        )
        amanha = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo + datetime.timedelta(days=1), policy=policy
        )
        assert amanha["celula"]["quantidade"] == 0

    def test_na_grade_do_mes_a_virada_tambem_nao_invade(self, dono, espaco, policy, dia_fixo):
        """O mesmo caso, pelo caminho onde a reserva realmente é buscada.

        Na visão de dia, a reserva que termina à meia-noite nem chega a ser
        lida: o filtro ``end_time__gt`` já a exclui. Na grade do mês os dois
        dias estão na mesma janela, então quem precisa acertar é a
        distribuição — e é este teste que a exercita.
        """
        Reservation.objects.create(
            space=espaco,
            user=dono,
            start_time=local(dia_fixo, 22),
            end_time=local(dia_fixo + datetime.timedelta(days=1), 0),
            status=ReservationStatus.CONFIRMED,
        )
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_MES, dia_fixo, policy=policy
        )
        por_data = {celula["data"]: celula["quantidade"] for celula in contexto["celulas"]}
        assert por_data[dia_fixo] == 1
        assert por_data[dia_fixo + datetime.timedelta(days=1)] == 0

    def test_fechamento_com_minutos_estica_ate_a_hora_seguinte(
        self, dono, espaco, policy, dia_fixo
    ):
        """Fechando às 17:30, a linha das 17h precisa existir.

        Cortar em 17 esconderia a última meia hora de expediente — que é
        justamente quando ainda dá para marcar alguma coisa.
        """
        policy.closing_time = datetime.time(17, 30)
        policy.save(update_fields=["closing_time"])
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        assert contexto["horas"][-1]["hora"] == 17

    def test_hora_fora_do_expediente_ainda_aparece(self, dono, espaco, policy, dia_fixo):
        """Uma reserva antiga, feita sob outra política, continua existindo.

        Esconder o que está fora da janela atual faria a tela mentir sobre o
        dia — e é exatamente o que o usuário iria procurar ali.
        """
        Reservation.objects.create(
            space=espaco,
            user=dono,
            start_time=local(dia_fixo, 5),
            end_time=local(dia_fixo, 6),
            status=ReservationStatus.CONFIRMED,
        )
        contexto = calendario.montar_calendario(
            dono, calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        horas = {linha["hora"] for linha in contexto["horas"] if linha["entradas"]}
        assert horas == {5}


@pytest.mark.django_db
class TestCusto:
    """The calendar must not cost one query per day."""

    def test_o_mes_inteiro_custa_o_mesmo_que_um_dia(self, dono, espaco, policy, dia_fixo):
        """Uma consulta por célula seria 42 consultas para um mês.

        A grade é montada em memória a partir de duas buscas; este teste falha
        se alguém voltar a consultar dia a dia.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for dia in range(1, 28):
            reserva(espaco, dono, datetime.date(2026, 3, dia), 9, 10)

        with CaptureQueriesContext(connection) as consultas:
            contexto = calendario.montar_calendario(
                dono, calendario.VISTA_MES, dia_fixo, incluir_ocupacao=True, policy=policy
            )
        assert contexto["total"] == 27
        # Três buscas: as minhas, as alheias e as manutenções. Nada por dia.
        assert len(consultas) <= 3


@pytest.mark.django_db
class TestTela:
    """The screen itself."""

    def test_exige_login(self, client):
        """Calendário é agenda pessoal: anônimo não entra."""
        resposta = client.get(reverse("calendar"))
        assert resposta.status_code == 302
        assert "/accounts/login/" in resposta["Location"]

    def test_abre_no_mes(self, logado):
        """Sem parâmetro nenhum, a tela abre no mês corrente."""
        resposta = logado.get(reverse("calendar"))
        assert resposta.status_code == 200
        assert resposta.context["vista"] == calendario.VISTA_MES

    def test_as_tres_visoes_respondem(self, logado):
        """Mês, semana e dia são telas de verdade, não promessas."""
        for vista in calendario.VISTAS:
            resposta = logado.get(reverse("calendar"), {"vista": vista})
            assert resposta.status_code == 200, vista
            assert resposta.context["vista"] == vista

    def test_a_aba_atual_e_anunciada(self, logado):
        """``aria-selected`` diz ao leitor de tela onde a pessoa está."""
        html = logado.get(reverse("calendar"), {"vista": "semana"}).content.decode()
        assert 'aria-selected="true"' in html
        assert html.count('aria-selected="false"') == 2

    def test_a_ocupacao_e_explicada_antes_de_ser_lida(self, logado):
        """Quem liga a ocupação precisa saber que não vai ver quem reservou."""
        html = logado.get(reverse("calendar"), {"ocupacao": "1"}).content.decode()
        assert "Ocupado" in html
        assert "não são exibidos" in html

    def test_a_tela_nao_publica_o_assunto_alheio(
        self, logado, outra_pessoa, espaco, dia_fixo
    ):
        """O teste de ponta a ponta da regra: HTML renderizado, nada dentro."""
        reserva(espaco, outra_pessoa, dia_fixo, 9, 10, title="Sindicância 2026/44")
        html = logado.get(
            reverse("calendar"),
            {"vista": "dia", "data": dia_fixo.isoformat(), "ocupacao": "1"},
        ).content.decode()
        assert "Ocupado" in html
        assert "Sindicância" not in html
        assert "alheio" not in html

    def test_o_dia_de_uma_reserva_leva_ao_detalhe(self, logado, dono, espaco, dia_fixo):
        """A própria reserva é link; a de terceiro não tem para onde levar."""
        minha = reserva(espaco, dono, dia_fixo, 9, 10, title="Meu assunto")
        html = logado.get(
            reverse("calendar"), {"vista": "dia", "data": dia_fixo.isoformat()}
        ).content.decode()
        assert reverse("reservation_detail", args=[minha.pk]) in html
        assert "Meu assunto" in html

    def test_a_navegacao_preserva_a_ocupacao(self, logado):
        """Trocar de mês não pode desligar em silêncio o que a pessoa ligou."""
        resposta = logado.get(reverse("calendar"), {"ocupacao": "1"})
        assert "ocupacao=1" in resposta.context["url_proximo"]
        assert "ocupacao=1" in resposta.context["url_anterior"]

    def test_a_troca_de_visao_preserva_o_dia(self, logado, dia_fixo):
        """Ir de mês para dia tem de cair no dia que estava na tela."""
        resposta = logado.get(reverse("calendar"), {"data": dia_fixo.isoformat()})
        for aba in resposta.context["vistas"]:
            assert dia_fixo.isoformat() in aba["url"]

    def test_o_menu_tem_calendario(self, logado):
        """O item de menu entra junto com a tela — nunca antes."""
        html = logado.get(reverse("calendar")).content.decode()
        assert 'href="/calendario/"' in html
        assert "Calendário" in html


@pytest.mark.django_db
class TestSaidaDoPassoQuatro:
    """The V2 criterion: success offers "Ver reserva / Calendário"."""

    def test_o_detalhe_oferece_o_calendario_no_dia_certo(
        self, logado, dono, espaco, dia_fixo
    ):
        """Depois de confirmar, a pessoa está vendo a reserva — e alcança o dia dela."""
        minha = reserva(espaco, dono, dia_fixo, 9, 10, title="Meu assunto")
        resposta = logado.get(reverse("reservation_detail", args=[minha.pk]))
        assert resposta.context["url_calendario"] == (
            f"{reverse('calendar')}?vista=dia&data={dia_fixo.isoformat()}"
        )
        assert "Ver no calendário" in resposta.content.decode()

    def test_o_dia_do_link_e_o_dia_local(self, logado, dono, espaco):
        """Uma reserva das 21h tem data em UTC no dia seguinte.

        Este é o mesmo erro que a Fase 18b encontrou no reagendamento: usar o
        instante gravado em vez do horário local manda o usuário para o dia
        errado, e a tela do dia seguinte parece vazia.
        """
        dia = datetime.date(2026, 3, 11)
        minha = reserva(espaco, dono, dia, 21, 22, title="Plantão")
        resposta = logado.get(reverse("reservation_detail", args=[minha.pk]))
        assert f"data={dia.isoformat()}" in resposta.context["url_calendario"]
