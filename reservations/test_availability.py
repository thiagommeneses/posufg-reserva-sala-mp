"""Tests for the booking policy and the availability derivation.

Três coisas dão errado com facilidade nesta camada e por isso concentram os
testes:

* **N+1** — o resumo da listagem precisa custar o mesmo com 3 ou com 30 espaços.
  Há teste contando consultas.
* **Fuso** — "hoje" é o dia do calendário do usuário, não o dia em UTC. Um teste
  roda às 23h locais de propósito.
* **Status derivado de ``is_active``** — o pacote V2 proíbe, e é o erro mais
  fácil de cometer sem perceber. Há teste afirmando o contrário.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from reservations.availability import (
    LIVRE,
    MANUTENCAO,
    RESERVADO,
    ROTULOS,
    STATUS_ENCERRADO,
    STATUS_FECHADO,
    STATUS_LIVRE,
    STATUS_LOTADO,
    STATUS_MANUTENCAO,
    STATUS_POUCOS,
    data_dentro_do_horizonte,
    duracao_valida,
    duracoes_oferecidas,
    gerar_slots,
    janela_do_dia,
    marcar_cabimento,
    proximo_dia_aberto,
    resumo_em_lote,
    rotulo_de_duracao,
)
from reservations.models import BookingPolicy, MaintenanceBlock, Reservation, ReservationStatus
from reservations.validators import (
    CLOSED_DAY_CODE,
    DURATION_TOO_LONG_CODE,
    DURATION_TOO_SHORT_CODE,
    OUTSIDE_HORIZON_CODE,
    OUTSIDE_OPERATING_HOURS_CODE,
    validate_booking_policy,
)
from spaces.models import Space

User = get_user_model()


def local(date, hora, minuto=0):
    """Return an aware datetime in the local timezone.

    Args:
        date: O dia.
        hora: A hora local.
        minuto: O minuto local.

    Returns:
        datetime: Instante ciente do fuso local.
    """
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hora, minuto)))


#: Os dias de funcionamento como um navegador os enviaria: caixa marcada vira
#: "on", caixa desmarcada simplesmente não vai no POST. Um teste que omite
#: todos desliga o prédio inteiro — e a política, com razão, recusa.
DIAS_UTEIS = {
    "opens_monday": "on",
    "opens_tuesday": "on",
    "opens_wednesday": "on",
    "opens_thursday": "on",
    "opens_friday": "on",
}


@pytest.fixture
def hoje():
    """Return today in the local timezone."""
    return timezone.localdate()


@pytest.fixture
def policy(db):
    """Return a booking policy that opens every day of the week.

    Os sete dias abertos são deliberados: os testes deste arquivo são sobre
    mecânica de horário — fatiamento, ocupação, custo de consulta —, e nenhum
    deles é sobre dia da semana. Com a política padrão (segunda a sexta) eles
    passariam a depender do dia em que a suíte roda e falhariam aos sábados,
    por um motivo que não tem relação nenhuma com o que afirmam.

    Quem testa a regra de dia da semana declara os dias que assume, em vez de
    herdá-los daqui.
    """
    politica = BookingPolicy.carregar()
    politica.opens_saturday = True
    politica.opens_sunday = True
    politica.save(update_fields=["opens_saturday", "opens_sunday"])
    return politica


@pytest.fixture
def espaco(db):
    """Return a plain active space."""
    return Space.objects.create(name="Sala Alfa", capacity=8, location="1º andar")


@pytest.fixture
def usuario(db):
    """Return a user who can hold reservations."""
    return User.objects.create_user(username="dono", password="senha-de-teste-123")


@pytest.fixture
def dia_aberto():
    """Return the next day the building opens, so slots always exist.

    Era ``amanha`` — e amanhã, duas vezes por semana, cai num dia em que o
    prédio não abre. Desde que a política ganhou dias de funcionamento, um
    teste ancorado em "amanhã" passa de segunda a quinta e falha de sexta a
    domingo. O que estes testes sempre quiseram é "um dia inteiro, no futuro,
    com janela de funcionamento" — que é o que esta fixture devolve.
    """
    from reservations.availability import proximo_dia_aberto

    return proximo_dia_aberto(timezone.localdate() + datetime.timedelta(days=1))


@pytest.fixture
def logado(client, usuario):
    """Return a client logged in as that user."""
    client.force_login(usuario)
    return client


@pytest.mark.django_db
class TestPolicy:
    """The policy model itself."""

    def test_migration_cria_a_politica(self):
        """A política precisa existir num banco recém-migrado."""
        assert BookingPolicy.objects.count() == 1

    def test_carregar_e_idempotente(self):
        """Chamar duas vezes não pode criar uma segunda política."""
        BookingPolicy.carregar()
        BookingPolicy.carregar()
        assert BookingPolicy.objects.count() == 1

    def test_salvar_nunca_cria_segunda_linha(self):
        """Uma segunda política competiria com a primeira sem ninguém notar."""
        nova = BookingPolicy(opening_time=datetime.time(7, 0))
        nova.save()
        assert BookingPolicy.objects.count() == 1
        assert BookingPolicy.carregar().opening_time == datetime.time(7, 0)

    def test_recusa_fechamento_antes_da_abertura(self, policy):
        """Uma janela invertida não geraria horário nenhum."""
        policy.closing_time = datetime.time(7, 0)
        with pytest.raises(ValidationError) as exc:
            policy.full_clean()
        assert "closing_time" in exc.value.message_dict

    def test_recusa_duracao_minima_maior_que_a_maxima(self, policy):
        """Limites invertidos tornariam qualquer reserva impossível."""
        policy.min_duration_minutes = 120
        policy.max_duration_minutes = 60
        with pytest.raises(ValidationError) as exc:
            policy.full_clean()
        assert "max_duration_minutes" in exc.value.message_dict

    def test_recusa_minima_que_nao_e_multiplo_do_incremento(self, policy):
        """Nenhum horário oferecido serviria se a mínima não fechasse com o passo."""
        policy.slot_minutes = 30
        policy.min_duration_minutes = 45
        with pytest.raises(ValidationError) as exc:
            policy.full_clean()
        assert "min_duration_minutes" in exc.value.message_dict

    def test_str_descreve_a_janela(self, policy):
        """O ``__str__`` aparece em log e no Django Admin."""
        assert str(policy) == "08:00 – 18:00, de 30 min"


@pytest.mark.django_db
class TestGerarSlots:
    """Slicing the operating window."""

    def test_dia_vazio_gera_a_janela_inteira_fatiada(self, espaco, policy, hoje):
        """Das 8h às 18h em passos de 30 min são 20 pedaços — não um único bloco."""
        slots = gerar_slots(espaco, hoje, policy)
        assert len(slots) == 20
        assert all(slot["disponivel"] for slot in slots)
        assert slots[0]["inicio"] == local(hoje, 8)
        assert slots[-1]["fim"] == local(hoje, 18)

    def test_nao_gera_mais_o_bloco_de_meia_noite_a_meia_noite(self, espaco, policy, hoje):
        """A regressão que motivou a fase: o botão único "00:00 – 00:00"."""
        slots = gerar_slots(espaco, hoje, policy)
        assert not any(slot["inicio"].hour == 0 for slot in slots)

    def test_respeita_o_incremento_configurado(self, espaco, policy, hoje):
        """Mudar o incremento muda a oferta, sem tocar em código."""
        policy.slot_minutes = 60
        policy.save()
        slots = gerar_slots(espaco, hoje, policy)
        assert len(slots) == 10

    def test_marca_pedaco_reservado(self, espaco, policy, usuario, hoje):
        """Um pedaço tocado por reserva ativa não pode ser oferecido."""
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(hoje, 9),
            end_time=local(hoje, 10),
            status=ReservationStatus.CONFIRMED,
        )
        slots = gerar_slots(espaco, hoje, policy)
        por_hora = {slot["inicio"]: slot for slot in slots}
        assert por_hora[local(hoje, 9)]["situacao"] == RESERVADO
        assert por_hora[local(hoje, 9, 30)]["situacao"] == RESERVADO
        assert por_hora[local(hoje, 10)]["situacao"] == LIVRE
        assert por_hora[local(hoje, 8, 30)]["situacao"] == LIVRE

    def test_reserva_cancelada_nao_bloqueia(self, espaco, policy, usuario, hoje):
        """Só status ativo segura o espaço — a regra não pode ser reescrita aqui."""
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(hoje, 9),
            end_time=local(hoje, 10),
            status=ReservationStatus.CANCELLED,
        )
        slots = gerar_slots(espaco, hoje, policy)
        assert all(slot["disponivel"] for slot in slots)

    def test_marca_manutencao(self, espaco, policy, usuario, hoje):
        """Manutenção precisa ser visualmente distinta de reserva."""
        MaintenanceBlock.objects.create(
            space=espaco,
            start_time=local(hoje, 14),
            end_time=local(hoje, 15),
            reason="Troca do projetor",
            created_by=usuario,
        )
        slots = {slot["inicio"]: slot for slot in gerar_slots(espaco, hoje, policy)}
        assert slots[local(hoje, 14)]["situacao"] == MANUTENCAO
        assert slots[local(hoje, 13, 30)]["situacao"] == LIVRE

    def test_manutencao_vence_reserva_no_mesmo_pedaco(self, espaco, policy, usuario, hoje):
        """Quando as duas tocam o pedaço, mostra a informação mais restritiva."""
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(hoje, 9),
            end_time=local(hoje, 10),
            status=ReservationStatus.CONFIRMED,
        )
        MaintenanceBlock.objects.create(
            space=espaco,
            start_time=local(hoje, 9, 30),
            end_time=local(hoje, 10),
            reason="Vazamento",
            created_by=usuario,
        )
        slots = {slot["inicio"]: slot for slot in gerar_slots(espaco, hoje, policy)}
        assert slots[local(hoje, 9)]["situacao"] == RESERVADO
        assert slots[local(hoje, 9, 30)]["situacao"] == MANUTENCAO

    def test_reserva_de_outro_dia_nao_interfere(self, espaco, policy, usuario, hoje):
        """A janela é do dia pedido, não de uma vizinhança vaga."""
        dia_aberto = hoje + datetime.timedelta(days=1)
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(dia_aberto, 9),
            end_time=local(dia_aberto, 10),
            status=ReservationStatus.CONFIRMED,
        )
        assert all(slot["disponivel"] for slot in gerar_slots(espaco, hoje, policy))

    def test_janela_que_nao_fecha_um_incremento_nao_gera_pedaco_parcial(self, espaco, policy, hoje):
        """Oferecer meio período seria oferecer o que não se pode reservar."""
        policy.opening_time = datetime.time(8, 0)
        policy.closing_time = datetime.time(8, 45)
        policy.save()
        slots = gerar_slots(espaco, hoje, policy)
        assert len(slots) == 1
        assert slots[0]["fim"] == local(hoje, 8, 30)

    def test_janela_do_dia_usa_o_fuso_local(self, policy, hoje):
        """A janela precisa ser 08:00 no relógio do usuário, não em UTC."""
        inicio, fim = janela_do_dia(hoje, policy)
        assert timezone.localtime(inicio).hour == 8
        assert timezone.localtime(fim).hour == 18


@pytest.mark.django_db
class TestResumoEmLote:
    """The batch summary that feeds the listing."""

    @pytest.fixture
    def espacos(self, db):
        """Return three spaces."""
        return [
            Space.objects.create(name=f"Sala {letra}", capacity=8, location="1º andar")
            for letra in "ABC"
        ]

    def test_duas_consultas_para_qualquer_quantidade(
        self, espacos, policy, hoje, django_assert_num_queries
    ):
        """O ponto principal da função: nada de uma consulta por cartão."""
        with django_assert_num_queries(2):
            resumo_em_lote(espacos, hoje, policy)

    def test_o_custo_nao_cresce_com_o_numero_de_espacos(self, espacos, policy, hoje):
        """Trinta espaços custam o mesmo que três."""
        muitos = espacos + [
            Space.objects.create(name=f"Sala {i}", capacity=4, location="2º andar")
            for i in range(27)
        ]
        with CaptureQueriesContext(connection) as consultas:
            resumo_em_lote(muitos, hoje, policy)
        assert len(consultas) == 2

    def test_espaco_livre(self, espacos, policy, hoje):
        """Dia inteiro vazio no começo do expediente é "Disponível"."""
        resumo = resumo_em_lote(espacos, hoje, policy, agora=local(hoje, 8))
        assert resumo[espacos[0].pk]["status"] == STATUS_LIVRE
        assert resumo[espacos[0].pk]["rotulo"] == ROTULOS[STATUS_LIVRE]
        assert resumo[espacos[0].pk]["slots_livres"] == 20
        assert resumo[espacos[0].pk]["minutos_livres"] == 600

    def test_poucos_horarios(self, espacos, policy, usuario, hoje):
        """Abaixo do limiar configurado o cartão avisa que está quase cheio."""
        espaco = espacos[0]
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(hoje, 8),
            end_time=local(hoje, 17),
            status=ReservationStatus.CONFIRMED,
        )
        resumo = resumo_em_lote([espaco], hoje, policy, agora=local(hoje, 8))
        assert resumo[espaco.pk]["status"] == STATUS_POUCOS
        assert resumo[espaco.pk]["slots_livres"] == 2

    def test_limiar_de_poucos_e_configuravel(self, espacos, policy, usuario, hoje):
        """Baixar o limiar tira o aviso, sem alterar código."""
        espaco = espacos[0]
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(hoje, 8),
            end_time=local(hoje, 17),
            status=ReservationStatus.CONFIRMED,
        )
        policy.few_slots_threshold = 1
        policy.save()
        resumo = resumo_em_lote([espaco], hoje, policy, agora=local(hoje, 8))
        assert resumo[espaco.pk]["status"] == STATUS_LIVRE

    def test_lotado(self, espacos, policy, usuario, hoje):
        """Sem nenhum pedaço livre no dia, o cartão diz isso."""
        espaco = espacos[0]
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(hoje, 8),
            end_time=local(hoje, 18),
            status=ReservationStatus.CONFIRMED,
        )
        resumo = resumo_em_lote([espaco], hoje, policy, agora=local(hoje, 8))
        assert resumo[espaco.pk]["status"] == STATUS_LOTADO
        assert resumo[espaco.pk]["proxima_janela"] is None

    def test_em_manutencao_o_dia_inteiro(self, espacos, policy, usuario, hoje):
        """Manutenção integral é um estado próprio, não "lotado"."""
        espaco = espacos[0]
        MaintenanceBlock.objects.create(
            space=espaco,
            start_time=local(hoje, 8),
            end_time=local(hoje, 18),
            reason="Reforma",
            created_by=usuario,
        )
        resumo = resumo_em_lote([espaco], hoje, policy, agora=local(hoje, 8))
        assert resumo[espaco.pk]["status"] == STATUS_MANUTENCAO

    def test_expediente_encerrado(self, espacos, policy, hoje):
        """Depois do fechamento havia horário, mas já passou — não é "lotado"."""
        resumo = resumo_em_lote([espacos[0]], hoje, policy, agora=local(hoje, 19))
        assert resumo[espacos[0].pk]["status"] == STATUS_ENCERRADO
        assert resumo[espacos[0].pk]["slots_livres"] == 0

    def test_horario_que_ja_passou_nao_conta_como_disponivel(self, espacos, policy, hoje):
        """Às 12h, a manhã não é mais uma opção."""
        resumo = resumo_em_lote([espacos[0]], hoje, policy, agora=local(hoje, 12))
        assert resumo[espacos[0].pk]["slots_livres"] == 12
        assert resumo[espacos[0].pk]["proxima_janela"] == local(hoje, 12)

    def test_proxima_janela_pula_o_que_esta_ocupado(self, espacos, policy, usuario, hoje):
        """A próxima janela é a próxima de verdade, não a primeira do dia."""
        espaco = espacos[0]
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(hoje, 8),
            end_time=local(hoje, 11),
            status=ReservationStatus.CONFIRMED,
        )
        resumo = resumo_em_lote([espaco], hoje, policy, agora=local(hoje, 8))
        assert resumo[espaco.pk]["proxima_janela"] == local(hoje, 11)

    def test_status_nao_deriva_de_is_active(self, espacos, policy, hoje):
        """Exigência explícita do pacote V2: são eixos independentes."""
        espaco = espacos[0]
        espaco.is_active = False
        espaco.save()
        resumo = resumo_em_lote([espaco], hoje, policy, agora=local(hoje, 8))
        assert resumo[espaco.pk]["status"] == STATUS_LIVRE

    def test_lista_vazia_nao_consulta_o_banco(self, policy, hoje, django_assert_num_queries):
        """Sem espaços não há o que resumir."""
        with django_assert_num_queries(0):
            assert resumo_em_lote([], hoje, policy) == {}

    def test_cada_espaco_recebe_o_proprio_resumo(self, espacos, policy, usuario, hoje):
        """A reserva de um espaço não pode contaminar o cartão do vizinho."""
        Reservation.objects.create(
            space=espacos[0],
            user=usuario,
            start_time=local(hoje, 8),
            end_time=local(hoje, 18),
            status=ReservationStatus.CONFIRMED,
        )
        resumo = resumo_em_lote(espacos, hoje, policy, agora=local(hoje, 8))
        assert resumo[espacos[0].pk]["status"] == STATUS_LOTADO
        assert resumo[espacos[1].pk]["status"] == STATUS_LIVRE


@pytest.mark.django_db
class TestHorizonte:
    """The booking horizon."""

    def test_hoje_esta_dentro(self, policy, hoje):
        """Reservar para hoje é o caso mais comum."""
        assert data_dentro_do_horizonte(hoje, policy, hoje=hoje)

    def test_ontem_esta_fora(self, policy, hoje):
        """Não se reserva o passado."""
        assert not data_dentro_do_horizonte(hoje - datetime.timedelta(days=1), policy, hoje=hoje)

    def test_ultimo_dia_do_horizonte_esta_dentro(self, policy, hoje):
        """O limite é inclusivo."""
        limite = hoje + datetime.timedelta(days=policy.horizon_days)
        assert data_dentro_do_horizonte(limite, policy, hoje=hoje)

    def test_depois_do_horizonte_esta_fora(self, policy, hoje):
        """Um dia além do limite já não é oferecido."""
        alem = hoje + datetime.timedelta(days=policy.horizon_days + 1)
        assert not data_dentro_do_horizonte(alem, policy, hoje=hoje)


@pytest.mark.django_db
class TestEnforceWindow:
    """Write-time enforcement, which is opt-in."""

    def test_desligado_por_padrao_nao_recusa_nada(self, policy, hoje):
        """O padrão preserva o comportamento atual do sistema."""
        assert policy.enforce_window is False
        validate_booking_policy(local(hoje, 22), local(hoje, 23), policy)

    def test_ligado_recusa_fora_do_horario(self, policy, hoje):
        """Com a regra ligada, 22h fica fora da janela de funcionamento."""
        policy.enforce_window = True
        with pytest.raises(ValidationError) as exc:
            validate_booking_policy(local(hoje, 22), local(hoje, 23), policy)
        assert exc.value.code == OUTSIDE_OPERATING_HOURS_CODE

    def test_ligado_aceita_dentro_do_horario(self, policy, hoje):
        """A regra não pode recusar o que está dentro da janela."""
        policy.enforce_window = True
        validate_booking_policy(local(hoje, 9), local(hoje, 10), policy)

    def test_ligado_recusa_reserva_curta_demais(self, policy, hoje):
        """A duração mínima passa a valer também na escrita."""
        policy.enforce_window = True
        with pytest.raises(ValidationError) as exc:
            validate_booking_policy(local(hoje, 9), local(hoje, 9, 10), policy)
        assert exc.value.code == DURATION_TOO_SHORT_CODE

    def test_ligado_recusa_reserva_longa_demais(self, policy, hoje):
        """Idem para a duração máxima."""
        policy.enforce_window = True
        policy.max_duration_minutes = 60
        with pytest.raises(ValidationError) as exc:
            validate_booking_policy(local(hoje, 9), local(hoje, 14), policy)
        assert exc.value.code == DURATION_TOO_LONG_CODE

    def test_ligado_recusa_alem_do_horizonte(self, policy, hoje):
        """Reservar para daqui a um ano não é oferecido nem aceito."""
        policy.enforce_window = True
        longe = hoje + datetime.timedelta(days=policy.horizon_days + 5)
        with pytest.raises(ValidationError) as exc:
            validate_booking_policy(local(longe, 9), local(longe, 10), policy)
        assert exc.value.code == OUTSIDE_HORIZON_CODE

    def test_criacao_pela_api_respeita_a_regra_quando_ligada(self, espaco, usuario, hoje, policy):
        """A regra vale para todo caminho de escrita, não só para a tela."""
        from reservations.services import create_reservation

        politica = BookingPolicy.carregar()
        politica.enforce_window = True
        politica.save()
        with pytest.raises(ValidationError) as exc:
            create_reservation(usuario, espaco, local(hoje, 22), local(hoje, 23))
        assert exc.value.code == OUTSIDE_OPERATING_HOURS_CODE

    def test_criacao_fora_da_janela_continua_valendo_com_a_regra_desligada(
        self, espaco, usuario, hoje
    ):
        """Nada do que funcionava antes desta fase pode ter parado de funcionar."""
        from reservations.services import create_reservation

        reserva = create_reservation(usuario, espaco, local(hoje, 22), local(hoje, 23))
        assert reserva.pk is not None


@pytest.mark.django_db
class TestTelas:
    """The screens that consume the new layer."""

    @pytest.fixture
    def logado(self, client, db):
        """Return a logged-in client."""
        User.objects.create_user(username="user", password="senha-de-teste-123")
        client.login(username="user", password="senha-de-teste-123")
        return client

    def test_lista_traz_o_resumo_de_hoje(self, logado, espaco, hoje):
        """O cartão precisa falar da data corrente, não de um dia genérico."""
        resposta = logado.get(reverse("space_list"))
        assert resposta.context["selected_date"] == hoje
        assert espaco.pk in resposta.context["availability_summary"]

    def test_lista_aceita_data_por_querystring(self, logado, espaco, hoje):
        """O seletor visual chega na Fase 7; o parâmetro precisa existir antes."""
        dia_aberto = hoje + datetime.timedelta(days=1)
        resposta = logado.get(reverse("space_list"), {"date": dia_aberto.isoformat()})
        assert resposta.context["selected_date"] == dia_aberto

    def test_data_invalida_cai_em_hoje(self, logado, espaco, hoje):
        """O resumo é informativo: uma data quebrada não pode virar erro 500."""
        resposta = logado.get(reverse("space_list"), {"date": "dia_aberto"})
        assert resposta.status_code == 200
        assert resposta.context["selected_date"] == hoje

    def test_data_fora_do_horizonte_cai_em_hoje(self, logado, espaco, hoje, policy):
        """Não se resume um dia que nem pode ser reservado."""
        longe = hoje + datetime.timedelta(days=policy.horizon_days + 10)
        resposta = logado.get(reverse("space_list"), {"date": longe.isoformat()})
        assert resposta.context["selected_date"] == hoje

    def test_cartao_mostra_o_rotulo_de_situacao(self, logado, espaco):
        """O estado vem escrito, não apenas colorido."""
        conteudo = logado.get(reverse("space_list")).content.decode()
        assert any(rotulo in conteudo for rotulo in ROTULOS.values())

    def test_detalhe_mostra_horarios_fatiados(self, logado, espaco, hoje, policy):
        """A tela do espaço precisa oferecer botões reserváveis."""
        resposta = logado.get(reverse("space_detail", args=[espaco.pk]))
        assert len(resposta.context["slots"]) == 20
        assert "00:00" not in resposta.context["slots"][0]["inicio"].strftime("%H:%M")

    def test_detalhe_limita_o_seletor_de_data_ao_horizonte(self, logado, espaco, hoje, policy):
        """Não se oferece um dia que a política não deixaria reservar."""
        resposta = logado.get(reverse("space_detail", args=[espaco.pk]))
        limite = hoje + datetime.timedelta(days=policy.horizon_days)
        conteudo = resposta.content.decode()
        assert f'min="{hoje.isoformat()}"' in conteudo
        assert f'max="{limite.isoformat()}"' in conteudo

    def test_detalhe_marca_horario_ocupado(self, logado, espaco, usuario, hoje, policy):
        """Um horário reservado aparece desabilitado, com rótulo escrito."""
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(hoje, 9),
            end_time=local(hoje, 10),
            status=ReservationStatus.CONFIRMED,
        )
        conteudo = logado.get(reverse("space_detail", args=[espaco.pk])).content.decode()
        assert "Reservado" in conteudo
        assert "disabled" in conteudo

    def test_tela_de_politica_exige_staff(self, logado):
        """Configurar a política não é operação de usuário comum."""
        resposta = logado.get(reverse("admin_dashboard:booking_policy"))
        assert resposta.status_code == 403

    def test_staff_edita_a_politica(self, client, db):
        """A edição precisa chegar ao banco e valer para a próxima tela."""
        User.objects.create_user(username="staff", password="senha-de-teste-123", is_staff=True)
        client.login(username="staff", password="senha-de-teste-123")
        resposta = client.post(
            reverse("admin_dashboard:booking_policy"),
            {
                "opening_time": "07:00",
                "closing_time": "19:00",
                "slot_minutes": 60,
                "min_duration_minutes": 60,
                "max_duration_minutes": 180,
                "horizon_days": 30,
                "few_slots_threshold": 2,
                "no_show_threshold_minutes": 15,
                **DIAS_UTEIS,
            },
        )
        assert resposta.status_code == 302
        politica = BookingPolicy.carregar()
        assert politica.opening_time == datetime.time(7, 0)
        assert politica.slot_minutes == 60
        assert BookingPolicy.objects.count() == 1

    def test_os_interruptores_da_politica_aparecem_na_tela(self, client, db):
        """Uma regra que muda reservas sozinha precisa ser visível e desligável."""
        User.objects.create_user(username="staff", password="senha-de-teste-123", is_staff=True)
        client.login(username="staff", password="senha-de-teste-123")
        conteudo = client.get(reverse("admin_dashboard:booking_policy")).content.decode()
        assert "Liberar reservas sem check-in" in conteudo
        assert "Tolerância para o check-in" in conteudo
        assert "Recusar reservas fora da janela" in conteudo

    def test_ligar_a_liberacao_pela_tela(self, client, db):
        """O administrador liga a regra aqui, e não editando código."""
        User.objects.create_user(username="staff", password="senha-de-teste-123", is_staff=True)
        client.login(username="staff", password="senha-de-teste-123")
        client.post(
            reverse("admin_dashboard:booking_policy"),
            {
                "opening_time": "08:00",
                "closing_time": "18:00",
                "slot_minutes": 30,
                "min_duration_minutes": 30,
                "max_duration_minutes": 240,
                "horizon_days": 90,
                "few_slots_threshold": 3,
                "no_show_threshold_minutes": 20,
                "release_no_shows": "on",
                **DIAS_UTEIS,
            },
        )
        politica = BookingPolicy.carregar()
        assert politica.release_no_shows is True
        assert politica.no_show_threshold_minutes == 20

    def test_politica_invalida_nao_e_gravada(self, client, db):
        """Uma janela invertida precisa voltar como erro de formulário."""
        User.objects.create_user(username="staff", password="senha-de-teste-123", is_staff=True)
        client.login(username="staff", password="senha-de-teste-123")
        resposta = client.post(
            reverse("admin_dashboard:booking_policy"),
            {
                "opening_time": "19:00",
                "closing_time": "07:00",
                "slot_minutes": 30,
                "min_duration_minutes": 30,
                "max_duration_minutes": 180,
                "horizon_days": 30,
                "few_slots_threshold": 2,
            },
        )
        assert resposta.status_code == 200
        assert BookingPolicy.carregar().opening_time == datetime.time(8, 0)

    def test_formulario_de_reserva_sugere_a_duracao_minima(self, logado, espaco, hoje):
        """O término sugerido vinha de uma hora fixa no código."""
        inicio = local(hoje, 9)
        resposta = logado.get(
            "/reservations/new/", {"space": espaco.pk, "start": inicio.isoformat()}
        )
        assert resposta.context["prefill_start_time"] == "09:00"
        assert resposta.context["prefill_end_time"] == "09:30"

    def test_formulario_de_reserva_respeita_o_termino_do_link(self, logado, espaco, hoje):
        """Quando o link diz o término, é ele que vale."""
        resposta = logado.get(
            "/reservations/new/",
            {
                "space": espaco.pk,
                "start": local(hoje, 9).isoformat(),
                "end": local(hoje, 11).isoformat(),
            },
        )
        assert resposta.context["prefill_end_time"] == "11:00"


@pytest.mark.django_db
class TestDuracaoEscolhida:
    """Choosing the length before the time, so one click books the whole range."""

    def test_rotulo_fala_como_gente(self):
        """Minutos crus são corretos e ninguém fala assim."""
        assert rotulo_de_duracao(30) == "30 min"
        assert rotulo_de_duracao(60) == "1h"
        assert rotulo_de_duracao(90) == "1h30"
        assert rotulo_de_duracao(240) == "4h"

    def test_opcoes_saem_da_politica(self, db):
        """Uma lista fixa contradiria a configuração no dia em que ela mudasse."""
        politica = BookingPolicy.carregar()
        politica.min_duration_minutes = 60
        politica.max_duration_minutes = 120
        politica.slot_minutes = 30
        politica.save()
        assert [opcao["minutos"] for opcao in duracoes_oferecidas(politica)] == [60, 90, 120]

    def test_opcoes_nao_viram_lista_para_procurar(self, db):
        """Oito já enche uma linha; mais do que isso não é escolher, é caçar."""
        politica = BookingPolicy.carregar()
        politica.min_duration_minutes = 30
        politica.max_duration_minutes = 600
        politica.slot_minutes = 30
        politica.save()
        assert len(duracoes_oferecidas(politica)) == 8

    def test_duracao_fora_da_politica_e_recusada(self, db):
        """O que a regra não permite não vira estado de tela."""
        politica = BookingPolicy.carregar()
        assert duracao_valida("30", politica) == 30
        assert duracao_valida("15", politica) is None
        assert duracao_valida("9999", politica) is None
        assert duracao_valida("abc", politica) is None
        assert duracao_valida("", politica) is None


@pytest.mark.django_db
class TestCabimento:
    """Marking which start times can actually hold the chosen length."""

    def test_dia_livre_cabe_ate_o_fim_da_janela(self, espaco, dia_aberto):
        """O último pedaço do dia é o limite, ainda que "sobre" tempo no relógio."""
        politica = BookingPolicy.carregar()
        slots = marcar_cabimento(gerar_slots(espaco, dia_aberto, politica), 60)
        assert slots[0]["cabe"] is True
        assert slots[0]["fim_da_reserva"] == slots[1]["fim"]
        # Uma hora a partir do penúltimo pedaço terminaria depois do fechamento.
        assert slots[-1]["cabe"] is False
        assert slots[-1]["fim_da_reserva"] is None

    def test_reserva_seguinte_derruba_o_cabimento(self, espaco, dia_aberto, usuario):
        """Livre às 9h não basta se as 9h30 já estão ocupadas."""
        politica = BookingPolicy.carregar()
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(dia_aberto, 9, 30),
            end_time=local(dia_aberto, 10, 0),
            status=ReservationStatus.CONFIRMED,
        )
        slots = marcar_cabimento(gerar_slots(espaco, dia_aberto, politica), 60)
        por_hora = {timezone.localtime(s["inicio"]).strftime("%H:%M"): s for s in slots}
        assert por_hora["09:00"]["disponivel"] is True
        assert por_hora["09:00"]["cabe"] is False
        assert por_hora["10:00"]["cabe"] is True

    def test_pedaco_ocupado_nunca_cabe(self, espaco, dia_aberto, usuario):
        """O que já está reservado não vira ponto de partida."""
        politica = BookingPolicy.carregar()
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(dia_aberto, 9, 0),
            end_time=local(dia_aberto, 9, 30),
            status=ReservationStatus.CONFIRMED,
        )
        slots = marcar_cabimento(gerar_slots(espaco, dia_aberto, politica), 30)
        por_hora = {timezone.localtime(s["inicio"]).strftime("%H:%M"): s for s in slots}
        assert por_hora["09:00"]["cabe"] is False

    def test_duracao_minima_sempre_cabe_onde_esta_livre(self, espaco, dia_aberto, usuario):
        """Com o menor compromisso, livre e cabível são a mesma coisa."""
        politica = BookingPolicy.carregar()
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(dia_aberto, 9, 0),
            end_time=local(dia_aberto, 11, 0),
            status=ReservationStatus.CONFIRMED,
        )
        slots = marcar_cabimento(
            gerar_slots(espaco, dia_aberto, politica), politica.min_duration_minutes
        )
        for slot in slots:
            assert slot["cabe"] == slot["disponivel"]


@pytest.mark.django_db
class TestTelaComDuracao:
    """The step 2 screen, where the click now books a range."""

    def test_default_e_a_duracao_minima(self, logado, espaco):
        """Quem não escolheu está pedindo o menor compromisso possível."""
        politica = BookingPolicy.carregar()
        resposta = logado.get(reverse("space_detail", args=[espaco.pk]))
        assert resposta.context["duracao_escolhida"] == politica.min_duration_minutes

    def test_a_duracao_vem_da_querystring(self, logado, espaco):
        """Estado de servidor: recarregar e compartilhar reproduzem a tela."""
        resposta = logado.get(reverse("space_detail", args=[espaco.pk]), {"duration": "120"})
        assert resposta.context["duracao_escolhida"] == 120
        assert resposta.context["rotulo_da_duracao"] == "2h"

    def test_duracao_invalida_cai_para_a_minima(self, logado, espaco):
        """Um valor fora da política não pode virar uma tela mentirosa."""
        politica = BookingPolicy.carregar()
        resposta = logado.get(reverse("space_detail", args=[espaco.pk]), {"duration": "9999"})
        assert resposta.context["duracao_escolhida"] == politica.min_duration_minutes

    def test_o_link_reserva_a_faixa_inteira(self, logado, espaco, dia_aberto):
        """O botão significa "das 9h às 11h", não "os trinta minutos das 9h"."""
        resposta = logado.get(
            reverse("space_detail", args=[espaco.pk]),
            {"date": dia_aberto.isoformat(), "duration": "120"},
        )
        html = resposta.content.decode()
        inicio = local(dia_aberto, 8, 0)
        fim = local(dia_aberto, 10, 0)
        assert f"start={inicio.isoformat()}" in html.replace("&amp;", "&")
        assert f"end={fim.isoformat()}" in html.replace("&amp;", "&")

    def test_horario_curto_demais_nao_e_oferecido(self, logado, espaco, dia_aberto, usuario):
        """Clicar num horário que o passo 3 recusaria é uma promessa falsa."""
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(dia_aberto, 9, 30),
            end_time=local(dia_aberto, 10, 0),
            status=ReservationStatus.CONFIRMED,
        )
        resposta = logado.get(
            reverse("space_detail", args=[espaco.pk]),
            {"date": dia_aberto.isoformat(), "duration": "60"},
        )
        assert resposta.context["tem_nao_cabe"] is True
        assert "Não cabe" in resposta.content.decode()

    def test_legenda_omite_o_estado_que_nao_esta_na_tela(self, logado, espaco, dia_aberto):
        """Explicar um estado ausente é ruído."""
        resposta = logado.get(
            reverse("space_detail", args=[espaco.pk]), {"date": dia_aberto.isoformat()}
        )
        assert resposta.context["tem_nao_cabe"] is False
        assert "Livre, mas curto" not in resposta.content.decode()

    def test_avisa_quando_nada_comporta_a_duracao(self, logado, espaco, dia_aberto, usuario):
        """Uma grade inteira apagada sem explicação devolve o problema ao usuário."""
        politica = BookingPolicy.carregar()
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(dia_aberto, 8, 30),
            end_time=timezone.make_aware(
                datetime.datetime.combine(dia_aberto, politica.closing_time)
            ),
            status=ReservationStatus.CONFIRMED,
        )
        resposta = logado.get(
            reverse("space_detail", args=[espaco.pk]),
            {"date": dia_aberto.isoformat(), "duration": "120"},
        )
        assert resposta.context["cabe_algum"] is False
        assert "nenhum comporta" in resposta.content.decode()


@pytest.mark.django_db
class TestDiasDeFuncionamento:
    """The weekday rule — the policy's newest axis.

    Ela existe porque o denominador da ocupação precisava saber quantos dias o
    prédio abre. Mas, uma vez que a política sabe disso, esconder a informação
    das telas seria pior do que não tê-la: o sistema continuaria oferecendo
    horário no domingo enquanto o relatório contava o domingo como fechado.
    """

    @pytest.fixture
    def policy(self, db):
        """Return a policy that opens Monday to Friday.

        Esta classe **é** sobre dia da semana, então declara os dias que assume
        em vez de herdar a fixture do módulo, que abre a semana inteira para
        não contaminar os testes de mecânica de horário.
        """
        politica = BookingPolicy.carregar()
        politica.opens_saturday = False
        politica.opens_sunday = False
        politica.save(update_fields=["opens_saturday", "opens_sunday"])
        return politica

    @staticmethod
    def _domingo(hoje):
        """Return the next Sunday from a reference day."""
        return hoje + datetime.timedelta(days=(6 - hoje.weekday()) % 7 or 7)

    def test_dia_fechado_nao_oferece_pedaco_nenhum(self, espaco, policy, hoje):
        """Fechado é vazio, não é uma janela toda marcada como ocupada.

        Devolver a janela inteira ocupada encheria a tela de trinta botões
        cinzentos onde a resposta certa cabe numa frase.
        """
        domingo = self._domingo(hoje)
        assert gerar_slots(espaco, domingo, policy) == []

    def test_dia_aberto_continua_oferecendo(self, espaco, policy, dia_aberto):
        """A regra nova não pode ter comido os dias que sempre funcionaram."""
        assert gerar_slots(espaco, dia_aberto, policy)

    def test_o_resumo_diz_fechado_e_nao_lotado(self, espaco, policy, hoje):
        """"Sem horários" descreve agenda cheia; "Fechado" descreve prédio fechado.

        A diferença não é de redação: a primeira manda a pessoa procurar outra
        sala no mesmo domingo, onde também não vai achar nada.
        """
        resumo = resumo_em_lote([espaco], self._domingo(hoje), policy)
        assert resumo[espaco.pk]["status"] == STATUS_FECHADO
        assert resumo[espaco.pk]["rotulo"] == "Fechado"
        assert resumo[espaco.pk]["proxima_janela"] is None

    def test_o_resumo_do_dia_fechado_nao_consulta_o_banco(self, espaco, policy, hoje):
        """A resposta é a mesma para todos os espaços, então não custa consulta.

        Sem o atalho, um domingo pagaria duas consultas para descobrir o que a
        política já sabia antes de olhar o banco.
        """
        with CaptureQueriesContext(connection) as consultas:
            resumo_em_lote([espaco], self._domingo(hoje), policy)
        assert len(consultas) == 0

    def test_horario_pedido_num_dia_fechado_tambem_diz_fechado(self, espaco, policy, hoje):
        """Perguntar por 15h no domingo não muda a resposta sobre o domingo."""
        resumo = resumo_em_lote(
            [espaco], self._domingo(hoje), policy, inicio=datetime.time(15, 0)
        )
        assert resumo[espaco.pk]["status"] == STATUS_FECHADO

    def test_a_gravacao_recusa_dia_fechado_quando_a_janela_e_exigida(
        self, espaco, policy, usuario, hoje
    ):
        """A recusa fica atrás de ``enforce_window``, como as outras da janela.

        É o mesmo interruptor porque é o mesmo conceito — "o prédio está
        aberto?" —, e separá-los faria o administrador ligar duas coisas para
        obter uma regra só.
        """
        policy.enforce_window = True
        policy.save(update_fields=["enforce_window"])
        domingo = self._domingo(hoje)
        with pytest.raises(ValidationError) as erro:
            validate_booking_policy(local(domingo, 9), local(domingo, 10), policy)
        assert erro.value.code == CLOSED_DAY_CODE

    def test_sem_a_janela_exigida_a_gravacao_passa(self, espaco, policy, usuario, hoje):
        """O padrão não muda comportamento de gravação em base que já existe.

        Uma reserva de domingo já gravada continua podendo ser reagendada; quem
        decide apertar a regra é o administrador, não esta migration.
        """
        assert policy.enforce_window is False
        domingo = self._domingo(hoje)
        validate_booking_policy(local(domingo, 9), local(domingo, 10), policy)

    def test_a_recusa_diz_quais_dias_abrem(self, policy, hoje):
        """Recusar sem dizer o que serve faz a pessoa tentar 11h, e 12h, e 13h."""
        policy.enforce_window = True
        policy.save(update_fields=["enforce_window"])
        domingo = self._domingo(hoje)
        with pytest.raises(ValidationError) as erro:
            validate_booking_policy(local(domingo, 9), local(domingo, 10), policy)
        mensagem = erro.value.messages[0]
        assert "Domingo" in mensagem
        assert "de segunda-feira a sexta-feira" in mensagem

    def test_politica_sem_nenhum_dia_e_recusada(self, policy):
        """Sem dia aberto o sistema inteiro para; não tem como ser o que se quis."""
        for campo in BookingPolicy.CAMPOS_DE_DIA:
            setattr(policy, campo, False)
        with pytest.raises(ValidationError) as erro:
            policy.full_clean()
        assert "opens_monday" in erro.value.error_dict

    def test_dias_abertos_usa_a_convencao_do_python(self, policy):
        """Segunda é 0. O teste existe porque essa é a troca que erra fácil."""
        assert policy.dias_abertos() == frozenset({0, 1, 2, 3, 4})
        assert policy.abre_em(datetime.date(2026, 3, 9)) is True  # segunda
        assert policy.abre_em(datetime.date(2026, 3, 15)) is False  # domingo

    def test_proximo_dia_aberto_pula_o_fim_de_semana(self, policy):
        """Sábado devolve a segunda seguinte, não o próprio sábado."""
        sabado = datetime.date(2026, 3, 14)
        assert proximo_dia_aberto(sabado, policy) == datetime.date(2026, 3, 16)

    def test_proximo_dia_aberto_devolve_o_proprio_dia_quando_aberto(self, policy):
        """Numa terça, o próximo dia aberto é a própria terça."""
        terca = datetime.date(2026, 3, 10)
        assert proximo_dia_aberto(terca, policy) == terca

    def test_o_calendario_diz_que_o_predio_esta_fechado(self, client, usuario, hoje):
        """Grade de horas desenhada num dia fechado é uma tela mentindo.

        Ela mostraria 08:00–18:00 vazias, como se bastasse escolher um horário.
        """
        client.force_login(usuario)
        domingo = self._domingo(hoje)
        conteudo = client.get(
            reverse("calendar"), {"vista": "dia", "data": domingo.isoformat()}
        ).content.decode()
        assert "O prédio não abre neste dia" in conteudo

    def test_o_calendario_mostra_o_que_ja_estava_marcado_num_dia_fechado(
        self, client, usuario, espaco, hoje
    ):
        """Reserva feita antes de o dia virar fechado continua existindo.

        Escondê-la faria a pessoa descobri-la pela porta trancada.
        """
        domingo = self._domingo(hoje)
        Reservation.objects.create(
            space=espaco,
            user=usuario,
            start_time=local(domingo, 9),
            end_time=local(domingo, 10),
            status=ReservationStatus.CONFIRMED,
            title="Marcada antes da regra",
        )
        client.force_login(usuario)
        conteudo = client.get(
            reverse("calendar"), {"vista": "dia", "data": domingo.isoformat()}
        ).content.decode()
        assert "O prédio não abre neste dia" in conteudo
        assert "Marcada antes da regra" in conteudo

    def test_a_tela_da_politica_oferece_os_dias(self, client, db):
        """O administrador muda os dias aqui, e não editando código."""
        User.objects.create_user(username="staff", password="senha-de-teste-123", is_staff=True)
        client.login(username="staff", password="senha-de-teste-123")
        conteudo = client.get(reverse("admin_dashboard:booking_policy")).content.decode()
        assert "Dias de funcionamento" in conteudo
        assert "Sábado" in conteudo
        assert "Domingo" in conteudo

    def test_o_administrador_abre_o_sabado_pela_tela(self, client, db):
        """Uma instalação que funciona no sábado marca a caixa e pronto."""
        User.objects.create_user(username="staff", password="senha-de-teste-123", is_staff=True)
        client.login(username="staff", password="senha-de-teste-123")
        client.post(
            reverse("admin_dashboard:booking_policy"),
            {
                "opening_time": "08:00",
                "closing_time": "18:00",
                "slot_minutes": 30,
                "min_duration_minutes": 30,
                "max_duration_minutes": 240,
                "horizon_days": 90,
                "few_slots_threshold": 3,
                "no_show_threshold_minutes": 15,
                **DIAS_UTEIS,
                "opens_saturday": "on",
            },
        )
        politica = BookingPolicy.carregar()
        assert politica.opens_saturday is True
        assert politica.opens_sunday is False
