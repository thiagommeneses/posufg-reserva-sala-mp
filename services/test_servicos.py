"""Tests for the service catalog, the request queue and the booking screen.

Três decisões desta fase são testadas aqui porque são exatamente as que um
refactor futuro tenderia a desfazer:

* **Serviço não derruba reserva.** Pedir café sem antecedência não pode custar
  a sala. O pedido é recusado; a reserva fica.
* **Serviço não oferecido não aparece — e não é aceito.** Nem pela tela, nem por
  um POST montado à mão.
* **Cancelar a reserva cancela a fila.** Sem isso a copa prepara café para uma
  reunião que não vai acontecer.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from reservations.models import MaintenanceBlock, Reservation, ReservationStatus
from reservations.services import (
    admin_cancel_reservation,
    cancel_reservation,
    create_reservation,
)
from services.enums import STATUS_ENCERRADOS, STATUS_PENDENTES, ServiceRequestStatus
from services.models import ReservationServiceRequest, ServiceType
from services.services import (
    NOTES_REQUIRED_CODE,
    ServiceNotesRequiredError,
    antecedencia_suficiente,
    atualizar_situacao,
    cancelar_pedidos_da_reserva,
    montar_pedidos,
    servicos_do_espaco,
    solicitar_servicos,
)
from spaces.models import Space

User = get_user_model()


@pytest.fixture
def usuario(db):
    """Return a regular user."""
    return User.objects.create_user(username="fulano", password="senha-de-teste-123")


@pytest.fixture
def administrador(db):
    """Return a staff user."""
    return User.objects.create_user(username="chefia", password="senha-de-teste-123", is_staff=True)


@pytest.fixture
def logado(client, usuario):
    """Return a client logged in as the regular user."""
    client.force_login(usuario)
    return client


@pytest.fixture
def sala(db):
    """Return a room for eight people."""
    return Space.objects.create(name="Sala Alfa", capacity=8, location="1º andar")


@pytest.fixture
def outra_sala(db):
    """Return a second room, offering nothing."""
    return Space.objects.create(name="Sala Beta", capacity=6, location="2º andar")


@pytest.fixture
def cafe(sala):
    """Return a service offered in the room, with no lead time and no notes."""
    servico = ServiceType.objects.create(
        name="Café",
        slug="cafe-teste",
        category="Apoio",
        description="Café e água durante o encontro.",
        sort_order=10,
    )
    servico.spaces.add(sala)
    return servico


@pytest.fixture
def audiovisual(sala):
    """Return a service that requires notes and four hours of lead time."""
    servico = ServiceType.objects.create(
        name="Apoio audiovisual",
        slug="av-teste",
        category="Apoio",
        requires_notes=True,
        min_lead_time_hours=4,
        sort_order=20,
    )
    servico.spaces.add(sala)
    return servico


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


def instante(date, hora):
    """Return an aware datetime in the local timezone.

    Args:
        date: O dia.
        hora: A hora local.

    Returns:
        datetime: Instante ciente do fuso local.
    """
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hora, 0)))


@pytest.fixture
def reserva(sala, usuario, dia_aberto):
    """Return a confirmed reservation for tomorrow morning."""
    return create_reservation(
        usuario,
        sala,
        instante(dia_aberto, 9),
        instante(dia_aberto, 10),
        title="Reunião de alinhamento",
        attendee_count=4,
    )


@pytest.mark.django_db
class TestCatalogo:
    """What the catalog offers, and where."""

    def test_so_mostra_servicos_do_espaco(self, sala, outra_sala, cafe):
        """Serviço não aplicável não aparece ao usuário."""
        assert list(servicos_do_espaco(sala)) == [cafe]
        assert list(servicos_do_espaco(outra_sala)) == []

    def test_esconde_servico_inativo(self, sala, cafe):
        """Desativar é a forma de aposentar um serviço sem apagar histórico."""
        cafe.is_active = False
        cafe.save(update_fields=["is_active"])
        assert list(servicos_do_espaco(sala)) == []

    def test_respeita_a_ordem_do_catalogo(self, sala, cafe, audiovisual):
        """``sort_order`` é a decisão do administrador sobre o que vem antes."""
        cafe.sort_order = 99
        cafe.save(update_fields=["sort_order"])
        assert list(servicos_do_espaco(sala)) == [audiovisual, cafe]

    def test_migration_semeia_o_catalogo_sem_vincular_espacos(self):
        """O catálogo inicial existe, e de propósito não é oferecido em lugar nenhum.

        Quais salas oferecem café é decisão do MPGO. Vincular aqui faria a tela
        prometer, no primeiro dia, serviço que ninguém combinou executar.
        """
        semeados = ServiceType.objects.filter(slug="copeira")
        assert semeados.exists()
        for servico in ServiceType.objects.filter(
            slug__in=["copeira", "apoio-audiovisual", "acessibilidade"]
        ):
            assert servico.spaces.count() == 0
            assert servico.min_lead_time_hours == 0

    def test_acessibilidade_nao_exige_justificativa(self):
        """O pacote V2 proíbe coletar motivo médico ou dado sensível."""
        acessibilidade = ServiceType.objects.get(slug="acessibilidade")
        assert acessibilidade.requires_notes is False

    def test_icones_do_catalogo_existem(self):
        """Um ícone fora do catálogo renderiza nada e ninguém descobre sem olhar."""
        for servico in ServiceType.objects.exclude(icon_name=""):
            servico.full_clean()


@pytest.mark.django_db
class TestAntecedencia:
    """The lead-time rule."""

    def test_sem_exigencia_sempre_cabe(self, cafe, dia_aberto):
        """Zero hora significa sem exigência."""
        assert antecedencia_suficiente(cafe, instante(dia_aberto, 9)) is True

    def test_aceita_com_folga(self, audiovisual, dia_aberto):
        """Quatro horas exigidas, um dia de folga."""
        assert antecedencia_suficiente(audiovisual, instante(dia_aberto, 9)) is True

    def test_recusa_em_cima_da_hora(self, audiovisual):
        """Uma hora antes não dá para quem precisa de quatro."""
        agora = timezone.now()
        assert antecedencia_suficiente(audiovisual, agora + datetime.timedelta(hours=1)) is False


@pytest.mark.django_db
class TestSolicitacao:
    """Creating requests without ever endangering the reservation."""

    def test_cria_o_pedido(self, reserva, cafe):
        """O caminho feliz."""
        criados, recusados = solicitar_servicos(reserva, [(cafe, "")])
        assert len(criados) == 1
        assert recusados == []
        assert criados[0].status == ServiceRequestStatus.REQUESTED

    def test_guarda_o_detalhamento(self, reserva, audiovisual):
        """O que o usuário descreveu é o que a fila precisa ler."""
        criados, _ = solicitar_servicos(reserva, [(audiovisual, "Projetor e microfone")])
        assert criados[0].notes == "Projetor e microfone"

    def test_recusa_sem_antecedencia_mas_mantem_a_reserva(self, sala, usuario, audiovisual):
        """A sala está livre; o serviço é que não dá. Recusar tudo puniria o usuário."""
        daqui_a_pouco = timezone.now() + datetime.timedelta(hours=1)
        reserva = create_reservation(
            usuario,
            sala,
            daqui_a_pouco,
            daqui_a_pouco + datetime.timedelta(hours=1),
            title="Urgente",
            attendee_count=2,
        )
        criados, recusados = solicitar_servicos(reserva, [(audiovisual, "Projetor")])
        assert criados == []
        assert len(recusados) == 1
        assert "4 horas" in recusados[0][1]
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.CONFIRMED
        assert reserva.service_requests.count() == 0

    def test_recusa_servico_de_outro_espaco(self, reserva, outra_sala, db):
        """Um pedido que a tela nunca ofereceu não vira tarefa para ninguém."""
        alheio = ServiceType.objects.create(name="Alheio", slug="alheio")
        alheio.spaces.add(outra_sala)
        criados, recusados = solicitar_servicos(reserva, [(alheio, "")])
        assert criados == []
        assert "não é oferecido" in recusados[0][1]

    def test_nao_duplica_o_mesmo_pedido(self, reserva, cafe):
        """Pedir duas vezes é o mesmo pedido — duplicar mostraria trabalho inexistente."""
        solicitar_servicos(reserva, [(cafe, "")])
        criados, _ = solicitar_servicos(reserva, [(cafe, "")])
        assert criados == []
        assert reserva.service_requests.count() == 1


@pytest.mark.django_db
class TestMontarPedidos:
    """Turning form input into requests, with the notes rule."""

    def test_monta_os_pares(self, sala, cafe):
        """O caso normal."""
        pedidos = montar_pedidos(sala, [(str(cafe.pk), " sem açúcar ")])
        assert pedidos == [(cafe, "sem açúcar")]

    def test_exige_detalhamento_quando_o_servico_exige(self, sala, audiovisual):
        """O campo é revelado por CSS; a exigência é do servidor."""
        with pytest.raises(ValidationError) as exc:
            montar_pedidos(sala, [(str(audiovisual.pk), "   ")])
        assert exc.value.code == NOTES_REQUIRED_CODE
        assert audiovisual.name in exc.value.messages[0]

    def test_descarta_selecao_desconhecida(self, sala, cafe):
        """Um id inventado não é erro do usuário — é ruído a ignorar."""
        assert montar_pedidos(sala, [("99999", "")]) == []

    def test_descarta_servico_inativo(self, sala, cafe):
        """Desativado deixa de ser oferecido, inclusive para um POST montado à mão."""
        cafe.is_active = False
        cafe.save(update_fields=["is_active"])
        assert montar_pedidos(sala, [(str(cafe.pk), "")]) == []


@pytest.mark.django_db
class TestFila:
    """The operational queue."""

    def test_atendimento_registra_quem_e_quando(self, reserva, cafe, administrador):
        """Sem isso não existe fila de trabalho, só um booleano."""
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        atualizar_situacao(pedido, ServiceRequestStatus.COMPLETED, administrador)
        pedido.refresh_from_db()
        assert pedido.status == ServiceRequestStatus.COMPLETED
        assert pedido.processed_by == administrador
        assert pedido.processed_at is not None

    def test_voltar_para_a_fila_apaga_o_registro_de_conclusao(self, reserva, cafe, administrador):
        """Ele não foi atendido; dizer quem atendeu seria falso."""
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        atualizar_situacao(pedido, ServiceRequestStatus.COMPLETED, administrador)
        atualizar_situacao(pedido, ServiceRequestStatus.IN_PROGRESS, administrador)
        pedido.refresh_from_db()
        assert pedido.processed_by is None
        assert pedido.processed_at is None

    def test_situacoes_pendentes_e_encerradas_nao_se_sobrepoem(self):
        """A fila é o complemento exato do histórico."""
        assert set(STATUS_PENDENTES).isdisjoint(STATUS_ENCERRADOS)
        assert len(STATUS_PENDENTES) + len(STATUS_ENCERRADOS) == len(ServiceRequestStatus)

    def test_cancelar_reserva_cancela_os_pedidos(self, reserva, cafe, usuario):
        """A copa não prepara café para reunião que não vai acontecer."""
        solicitar_servicos(reserva, [(cafe, "")])
        cancel_reservation(reserva, usuario)
        pedido = reserva.service_requests.get()
        assert pedido.status == ServiceRequestStatus.CANCELLED

    def test_cancelamento_administrativo_tambem_cancela(self, reserva, cafe):
        """O mesmo vale quando quem cancela é a administração."""
        solicitar_servicos(reserva, [(cafe, "")])
        admin_cancel_reservation(reserva)
        assert reserva.service_requests.get().status == ServiceRequestStatus.CANCELLED

    def test_nao_reabre_pedido_ja_concluido(self, reserva, cafe, administrador, usuario):
        """Concluído é história, não fila."""
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        atualizar_situacao(pedido, ServiceRequestStatus.COMPLETED, administrador)
        cancelar_pedidos_da_reserva(reserva)
        pedido.refresh_from_db()
        assert pedido.status == ServiceRequestStatus.COMPLETED

    def test_apagar_a_reserva_leva_os_pedidos(self, reserva, cafe):
        """Pedido sem reserva é tarefa órfã."""
        solicitar_servicos(reserva, [(cafe, "")])
        Reservation.objects.filter(pk=reserva.pk).delete()
        assert ReservationServiceRequest.objects.count() == 0


@pytest.mark.django_db
class TestTelaDeReserva:
    """The booking form, which is where the queue gets its work."""

    def test_formulario_mostra_os_servicos_do_espaco(self, logado, sala, cafe, outra_sala):
        """O que é oferecido ali, e só."""
        alheio = ServiceType.objects.create(name="Alheio", slug="alheio")
        alheio.spaces.add(outra_sala)
        resposta = logado.get(reverse("reservation_create"), {"space": sala.pk})
        assert resposta.status_code == 200
        html = resposta.content.decode()
        assert cafe.name in html
        assert "Alheio" not in html

    def test_espaco_sem_servico_nao_mostra_a_seccao(self, logado, outra_sala):
        """Um título "Serviços" com nada embaixo é ruído."""
        resposta = logado.get(reverse("reservation_create"), {"space": outra_sala.pk})
        assert "Serviços" not in resposta.content.decode()

    def test_reservar_cria_os_pedidos(self, logado, sala, cafe, dia_aberto, usuario):
        """Sem este caminho a fila administrativa nunca receberia nada."""
        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": dia_aberto.isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Reunião",
                "attendee_count": "4",
                "services": [str(cafe.pk)],
                f"service_notes_{cafe.pk}": "Para seis pessoas",
            },
        )
        assert resposta.status_code == 302
        reserva = Reservation.objects.get(user=usuario)
        pedido = reserva.service_requests.get()
        assert pedido.service_type == cafe
        assert pedido.notes == "Para seis pessoas"

    def test_reservar_sem_servico_continua_funcionando(self, logado, sala, cafe, dia_aberto):
        """Serviço é opcional; a reserva não depende dele."""
        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": dia_aberto.isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Reunião",
                "attendee_count": "4",
            },
        )
        assert resposta.status_code == 302
        assert ReservationServiceRequest.objects.count() == 0

    def test_detalhamento_faltando_nao_cria_a_reserva(self, logado, sala, audiovisual, dia_aberto):
        """O formulário volta antes de gravar qualquer coisa."""
        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": dia_aberto.isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Reunião",
                "attendee_count": "4",
                "services": [str(audiovisual.pk)],
                f"service_notes_{audiovisual.pk}": "",
            },
        )
        assert resposta.status_code == 200
        assert audiovisual.name in resposta.content.decode()
        assert Reservation.objects.count() == 0

    def test_formulario_devolvido_preserva_a_selecao(
        self, logado, sala, cafe, audiovisual, dia_aberto
    ):
        """Perder o que já foi preenchido é o jeito mais rápido de fazer alguém desistir."""
        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": dia_aberto.isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Reunião",
                "attendee_count": "4",
                "services": [str(cafe.pk), str(audiovisual.pk)],
                f"service_notes_{cafe.pk}": "Sem açúcar",
                f"service_notes_{audiovisual.pk}": "",
            },
        )
        html = resposta.content.decode()
        assert f'value="{cafe.pk}"' in html
        assert "Sem açúcar" in html

    def test_servico_recusado_avisa_e_mantem_a_reserva(
        self, logado, sala, audiovisual, usuario, dia_aberto
    ):
        """A reserva vale; o serviço é que não coube — e isso é dito em voz alta.

        O que torna o pedido impossível é uma antecedência absurda, e não uma
        reserva "daqui a pouco" calculada a partir do relógio. A versão anterior
        somava uma hora a ``localtime()``: rodando às 23h, o término caía no dia
        seguinte enquanto a data postada continuava sendo a de hoje, e o
        formulário recusava a reserva inteira por término anterior ao início.
        O horário aqui é fixo; quem varia é a regra.
        """
        audiovisual.min_lead_time_hours = 24 * 365
        audiovisual.save(update_fields=["min_lead_time_hours"])

        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": dia_aberto.isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Urgente",
                "attendee_count": "2",
                "services": [str(audiovisual.pk)],
                f"service_notes_{audiovisual.pk}": "Projetor",
            },
            follow=True,
        )
        assert Reservation.objects.filter(user=usuario).exists()
        assert ReservationServiceRequest.objects.count() == 0
        avisos = [str(m) for m in resposta.context["messages"]]
        assert any("antecedência" in aviso for aviso in avisos)

    def test_detalhe_da_reserva_mostra_os_servicos(self, logado, reserva, cafe):
        """Pedido invisível para quem pediu é dado morto."""
        solicitar_servicos(reserva, [(cafe, "Para seis pessoas")])
        resposta = logado.get(reverse("reservation_detail", args=[reserva.pk]))
        html = resposta.content.decode()
        assert cafe.name in html
        assert "Para seis pessoas" in html
        assert "Solicitado" in html


@pytest.mark.django_db
class TestTelasAdministrativas:
    """The admin catalog and queue."""

    def test_catalogo_lista(self, client, administrador, cafe):
        """A tela existe e mostra o serviço."""
        client.force_login(administrador)
        resposta = client.get(reverse("admin_dashboard:service_type_list"))
        assert resposta.status_code == 200
        assert cafe.name in resposta.content.decode()

    def test_catalogo_exige_administrador(self, logado):
        """Criar serviço é operação de administrador."""
        resposta = logado.get(reverse("admin_dashboard:service_type_list"))
        assert resposta.status_code in (302, 403)

    def test_fila_mostra_pedido_pendente(self, client, administrador, reserva, cafe):
        """A fila é a razão de o pedido ser uma linha e não um booleano."""
        solicitar_servicos(reserva, [(cafe, "")])
        client.force_login(administrador)
        resposta = client.get(reverse("admin_dashboard:service_queue"))
        assert resposta.status_code == 200
        assert cafe.name in resposta.content.decode()

    def test_fila_exige_administrador(self, logado):
        """A fila operacional não é do usuário final."""
        resposta = logado.get(reverse("admin_dashboard:service_queue"))
        assert resposta.status_code in (302, 403)


@pytest.mark.django_db
class TestFocoNoCampoComErro:
    """Pointing the user at the field that is missing."""

    def test_a_excecao_diz_qual_servico(self, sala, audiovisual):
        """Um aviso no topo sem destino é um erro que o usuário não encontra."""
        with pytest.raises(ServiceNotesRequiredError) as exc:
            montar_pedidos(sala, [(str(audiovisual.pk), "")])
        assert exc.value.service_type == audiovisual

    def test_continua_sendo_um_validation_error(self, sala, audiovisual):
        """Quem só quer a mensagem não precisa conhecer a classe nova."""
        with pytest.raises(ValidationError):
            montar_pedidos(sala, [(str(audiovisual.pk), "")])

    def test_nome_com_porcentagem_nao_quebra_a_mensagem(self, sala):
        """``params`` do Django aplicaria ``mensagem % params`` e derrubaria isto."""
        servico = ServiceType.objects.create(
            name="Coffee break 10% reduzido",
            slug="coffee-10",
            requires_notes=True,
        )
        servico.spaces.add(sala)
        with pytest.raises(ServiceNotesRequiredError) as exc:
            montar_pedidos(sala, [(str(servico.pk), "")])
        assert "10%" in exc.value.messages[0]

    def test_o_formulario_marca_o_campo(self, logado, sala, audiovisual, dia_aberto):
        """O campo volta com foco, ``aria-invalid`` e destaque visual."""
        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": dia_aberto.isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Reunião",
                "attendee_count": "4",
                "services": [str(audiovisual.pk)],
                f"service_notes_{audiovisual.pk}": "",
            },
        )
        html = resposta.content.decode()
        assert 'aria-invalid="true"' in html
        assert "autofocus" in html
        assert "textarea-error" in html


@pytest.mark.django_db
class TestRepresentacaoTextual:
    """What these objects look like in the Django admin and in logs."""

    def test_servico_se_identifica_pelo_nome(self, cafe):
        """No admin, um serviço sem ``__str__`` apareceria como "ServiceType object (1)"."""
        assert str(cafe) == cafe.name

    def test_pedido_diz_o_servico_e_a_reserva(self, reserva, cafe):
        """Uma linha da fila precisa dizer o que é e para quem, sem abrir."""
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        assert cafe.name in str(pedido)
        assert str(reserva) in str(pedido)


@pytest.mark.django_db
class TestResumoPersistente:
    """The summary panel the V2 package asks for on every step."""

    def test_mostra_o_espaco_e_o_horario_escolhidos(self, logado, sala, dia_aberto):
        """O resumo responde "o que eu já escolhi?" sem obrigar a voltar."""
        resposta = logado.get(
            reverse("reservation_create"),
            {"space": sala.pk, "start": instante(dia_aberto, 9).isoformat()},
        )
        resumo = resposta.context["resumo"]
        assert resumo["espaco"] == sala
        assert resumo["inicio"].strftime("%H:%M") == "09:00"
        html = resposta.content.decode()
        assert "Resumo da reserva" in html
        assert sala.name in html

    def test_link_alterar_leva_ao_passo_2_com_a_data(self, logado, sala, dia_aberto):
        """O link é ajuste de uma escolha do passo 2, não desfazer o passo 3."""
        resposta = logado.get(
            reverse("reservation_create"),
            {"space": sala.pk, "start": instante(dia_aberto, 9).isoformat()},
        )
        url = resposta.context["resumo"]["url_do_horario"]
        assert url == f"{reverse('space_detail', args=[sala.pk])}?date={dia_aberto.isoformat()}"
        assert url in resposta.content.decode()

    def test_sem_espaco_nao_ha_para_onde_alterar(self, logado):
        """O passo 2 é a tela de um espaço; sem espaço, o link mentiria."""
        resposta = logado.get(reverse("reservation_create"))
        assert resposta.context["resumo"]["url_do_horario"] is None

    def test_data_pela_metade_nao_quebra_o_resumo(self, logado, sala, dia_aberto):
        """O resumo não é lugar de reportar erro — quem reporta é o formulário."""
        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": "2026-",
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Reunião",
                "attendee_count": "4",
            },
        )
        assert resposta.status_code == 200
        assert resposta.context["resumo"]["inicio"] is None


@pytest.mark.django_db
class TestBlocoDeHorario:
    """The collapsed date/time block — progressive disclosure applied to it too."""

    def test_fechado_para_quem_ja_escolheu_no_passo_2(self, logado, sala, dia_aberto):
        """Reabrir seria pedir para confirmar o que a pessoa acabou de decidir."""
        resposta = logado.get(
            reverse("reservation_create"),
            {"space": sala.pk, "start": instante(dia_aberto, 9).isoformat()},
        )
        assert resposta.context["abrir_horario"] is False

    def test_aberto_para_quem_chegou_sem_horario(self, logado, sala):
        """Sem isso a tela não teria saída: os campos ficariam escondidos."""
        resposta = logado.get(reverse("reservation_create"), {"space": sala.pk})
        assert resposta.context["abrir_horario"] is True

    def test_reabre_quando_o_erro_e_de_horario(self, logado, sala, dia_aberto):
        """Mandar corrigir algo escondido é o mesmo que não dizer nada."""
        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": dia_aberto.isoformat(),
                "start_time": "10:00",
                "end_time": "09:00",
                "title": "Reunião",
                "attendee_count": "4",
            },
        )
        assert resposta.context["abrir_horario"] is True
        assert "<details" in resposta.content.decode()

    def test_nao_reabre_quando_o_erro_e_de_outro_campo(self, logado, sala, dia_aberto):
        """Abrir o horário por causa da capacidade apontaria para o lugar errado."""
        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": dia_aberto.isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Reunião",
                "attendee_count": "999",
            },
        )
        assert resposta.context["abrir_horario"] is False

    def test_campos_de_horario_continuam_existindo(self, logado, sala, dia_aberto):
        """O passo 2 só oferece horários do incremento da política.

        Quem precisa de 09:15 às 10:45 não conseguiria pedir se os campos
        sumissem — por isso eles são escondidos, e não removidos.
        """
        conteudo = logado.get(
            reverse("reservation_create"),
            {"space": sala.pk, "start": instante(dia_aberto, 9).isoformat()},
        ).content.decode()
        for campo in ['name="date"', 'name="start_time"', 'name="end_time"']:
            assert campo in conteudo

        resposta = logado.post(
            reverse("reservation_create"),
            {
                "space": sala.pk,
                "date": dia_aberto.isoformat(),
                "start_time": "09:15",
                "end_time": "10:45",
                "title": "Reunião fora do slot",
                "attendee_count": "4",
            },
        )
        assert resposta.status_code == 302
        reserva = Reservation.objects.get()
        assert timezone.localtime(reserva.start_time).strftime("%H:%M") == "09:15"


@pytest.mark.django_db
class TestBlocosDaTela:
    """The named blocks the V2 package specifies for step 3."""

    def test_tem_os_blocos_com_os_nomes_do_pacote(self, logado, sala, cafe):
        """O título fala da pessoa, não do catálogo da administração."""
        conteudo = logado.get(reverse("reservation_create"), {"space": sala.pk}).content.decode()
        assert "Sobre a reserva" in conteudo
        assert "Precisa de algum apoio?" in conteudo
        assert "Data e horário" in conteudo

    def test_diz_que_o_organizador_e_quem_esta_logado(self, logado, sala):
        """Exigência do pacote: não pedir o que o sistema já sabe — e dizer isso."""
        conteudo = logado.get(reverse("reservation_create"), {"space": sala.pk}).content.decode()
        assert "organizador" in conteudo
        assert 'name="organizer"' not in conteudo


@pytest.mark.django_db
class TestPassoQuatro:
    """Step 4 — the review screen, and the write it guards."""

    def _dados(self, sala, dia_aberto, **extra):
        """Return a valid step 3 POST body."""
        corpo = {
            "space": sala.pk,
            "date": dia_aberto.isoformat(),
            "start_time": "09:00",
            "end_time": "10:00",
            "title": "Reunião de alinhamento",
            "attendee_count": "4",
            "notes": "Trazer o relatório",
        }
        corpo.update(extra)
        return corpo

    def test_revisar_nao_cria_a_reserva(self, logado, sala, dia_aberto):
        """A frase "Nada foi reservado ainda" precisa ser verdade."""
        resposta = logado.post(reverse("reservation_review"), self._dados(sala, dia_aberto))
        assert resposta.status_code == 200
        assert Reservation.objects.count() == 0

    def test_revisao_mostra_tudo(self, logado, sala, dia_aberto, cafe):
        """A revisão completa que o pacote V2 pede."""
        resposta = logado.post(
            reverse("reservation_review"),
            self._dados(
                sala,
                dia_aberto,
                services=[str(cafe.pk)],
                **{f"service_notes_{cafe.pk}": "Para seis"},
            ),
        )
        html = resposta.content.decode()
        assert sala.name in html
        assert "Reunião de alinhamento" in html
        assert "09:00" in html
        assert "10:00" in html
        assert "Trazer o relatório" in html
        assert cafe.name in html
        assert "Para seis" in html

    def test_revisao_e_a_etapa_4_de_4(self, logado, sala, dia_aberto):
        """Stepper 4/4 — critério de aceite do pacote."""
        resposta = logado.post(reverse("reservation_review"), self._dados(sala, dia_aberto))
        assert resposta.context["etapa_atual"] == 4
        assert resposta.context["total_etapas"] == 4

    def test_passo_3_agora_e_3_de_4(self, logado, sala):
        """O stepper virou; o passo 3 deixou de ser o último."""
        resposta = logado.get(reverse("reservation_create"), {"space": sala.pk})
        assert resposta.context["etapa_atual"] == 3
        assert resposta.context["total_etapas"] == 4

    def test_erro_no_passo_3_nao_chega_a_revisao(self, logado, sala, dia_aberto):
        """A revisão nunca mostra uma reserva impossível."""
        resposta = logado.post(
            reverse("reservation_review"), self._dados(sala, dia_aberto, attendee_count="999")
        )
        assert resposta.status_code == 200
        assert "Confira antes de confirmar" not in resposta.content.decode()
        assert resposta.context["etapa_atual"] == 3

    def test_horario_ocupado_nao_chega_a_revisao(self, logado, sala, dia_aberto, django_user_model):
        """Entre escolher e revisar cabe uma reserva concorrente."""
        outro = django_user_model.objects.create_user(
            username="concorrente", password="senha-de-teste-123"
        )
        create_reservation(
            outro, sala, instante(dia_aberto, 9), instante(dia_aberto, 10), title="Antes"
        )
        resposta = logado.post(reverse("reservation_review"), self._dados(sala, dia_aberto))
        assert resposta.context["etapa_atual"] == 3
        assert "reservado" in resposta.context["error"]

    def test_confirmar_cria_a_reserva(self, logado, sala, dia_aberto, usuario, cafe):
        """O POST final é quem grava."""
        resposta = logado.post(
            reverse("reservation_create"),
            self._dados(sala, dia_aberto, services=[str(cafe.pk)], confirmar="1"),
        )
        assert resposta.status_code == 302
        reserva = Reservation.objects.get(user=usuario)
        assert reserva.title == "Reunião de alinhamento"
        assert reserva.service_requests.count() == 1

    def test_confirmacao_revalida_conflito_e_nao_apaga_dados(
        self, logado, sala, dia_aberto, django_user_model
    ):
        """Critério do pacote: conflito concorrente não apaga o que foi preenchido."""
        outro = django_user_model.objects.create_user(
            username="concorrente", password="senha-de-teste-123"
        )
        create_reservation(
            outro, sala, instante(dia_aberto, 9), instante(dia_aberto, 10), title="Antes"
        )

        resposta = logado.post(reverse("reservation_create"), self._dados(sala, dia_aberto))
        assert resposta.status_code == 200
        assert Reservation.objects.filter(title="Reunião de alinhamento").count() == 0
        html = resposta.content.decode()
        assert "Reunião de alinhamento" in html
        assert "Trazer o relatório" in html
        assert resposta.context["abrir_horario"] is True

    def test_confirmacao_revalida_capacidade(self, logado, sala, dia_aberto):
        """Capacidade também é revalidada na gravação, não só na revisão."""
        resposta = logado.post(
            reverse("reservation_create"), self._dados(sala, dia_aberto, attendee_count="999")
        )
        assert resposta.status_code == 200
        assert Reservation.objects.count() == 0

    def test_confirmacao_revalida_manutencao(self, logado, sala, dia_aberto, administrador):
        """Um bloqueio criado depois da revisão impede a gravação."""
        MaintenanceBlock.objects.create(
            space=sala,
            start_time=instante(dia_aberto, 9),
            end_time=instante(dia_aberto, 10),
            reason="Pintura",
            created_by=administrador,
        )
        resposta = logado.post(reverse("reservation_create"), self._dados(sala, dia_aberto))
        assert resposta.status_code == 200
        assert Reservation.objects.count() == 0
        assert "manutenção" in resposta.context["error"]


@pytest.mark.django_db
class TestAlterarVoltaAoPontoCerto:
    """Voltar ao ponto certo mantendo estado — critério de aceite do pacote."""

    def _dados(self, sala, dia_aberto, **extra):
        """Return a valid step 3 POST body."""
        corpo = {
            "space": sala.pk,
            "date": dia_aberto.isoformat(),
            "start_time": "09:00",
            "end_time": "10:00",
            "title": "Reunião de alinhamento",
            "attendee_count": "4",
            "notes": "Trazer o relatório",
        }
        corpo.update(extra)
        return corpo

    def test_editar_devolve_o_passo_3_preenchido(self, logado, sala, dia_aberto, cafe):
        """Um link comum levaria a pessoa a um formulário vazio."""
        resposta = logado.post(
            reverse("reservation_edit"),
            self._dados(
                sala,
                dia_aberto,
                services=[str(cafe.pk)],
                **{f"service_notes_{cafe.pk}": "Para seis"},
            ),
        )
        assert resposta.status_code == 200
        assert resposta.context["etapa_atual"] == 3
        assert resposta.context["prefill_title"] == "Reunião de alinhamento"
        assert resposta.context["prefill_notes"] == "Trazer o relatório"
        assert resposta.context["prefill_attendee_count"] == "4"
        html = resposta.content.decode()
        assert "Para seis" in html

    def test_editar_nao_reclama_de_nada(self, logado, sala, dia_aberto):
        """Quem clicou em Alterar já sabe que quer mexer; erro aqui é ruído."""
        resposta = logado.post(reverse("reservation_edit"), self._dados(sala, dia_aberto))
        assert resposta.context["error"] is None

    def test_editar_nao_cria_nada(self, logado, sala, dia_aberto):
        """Voltar para editar não é gravar."""
        logado.post(reverse("reservation_edit"), self._dados(sala, dia_aberto))
        assert Reservation.objects.count() == 0

    def test_alterar_espaco_leva_ao_passo_1_com_data_e_pessoas(self, logado, sala, dia_aberto):
        """Trocar de espaço não pode custar a data escolhida duas telas atrás."""
        resposta = logado.post(reverse("reservation_review"), self._dados(sala, dia_aberto))
        url = resposta.context["url_dos_espacos"]
        assert url.startswith(reverse("space_list"))
        assert f"date={dia_aberto.isoformat()}" in url
        assert "people=4" in url
        # O ``&`` sai escapado no HTML — é o autoescape do Django fazendo
        # o certo, e comparar com a URL crua daria falso negativo.
        assert escape(url) in resposta.content.decode()

    def test_a_revisao_carrega_o_estado_inteiro(self, logado, sala, dia_aberto, cafe):
        """Sem os campos escondidos, a revisão seria um beco sem saída."""
        html = logado.post(
            reverse("reservation_review"),
            self._dados(sala, dia_aberto, services=[str(cafe.pk)]),
        ).content.decode()
        escondidos = [
            "date",
            "start_time",
            "end_time",
            "title",
            "attendee_count",
            "notes",
            "services",
        ]
        for campo in escondidos:
            assert f'name="{campo}"' in html

    def test_espaco_ausente_volta_para_a_lista(self, logado):
        """Nem revisão nem edição fazem sentido sem espaço."""
        for rota in ["reservation_review", "reservation_edit"]:
            resposta = logado.post(reverse(rota), {})
            assert resposta.status_code == 302
            assert resposta.url == reverse("space_list")
