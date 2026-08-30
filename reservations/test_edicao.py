"""Tests for editing a reservation after it was created.

A decisão que este arquivo protege é sobre trabalho alheio: **um pedido de
serviço que a administração já pegou não sai por o usuário desmarcar**. É a
única regra aqui que não é óbvia, e é a que um refactor futuro tenderia a
"simplificar" para um `set` de ids.

O resto é separação de responsabilidade: editar mexe no que a reserva *é*;
reagendar mexe em *quando* ela acontece, e só o segundo disputa a agenda com
outras pessoas.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from reservations.models import Reservation, ReservationStatus
from reservations.services import (
    OwnershipError,
    atualizar_detalhes,
    create_reservation,
)
from services.enums import ServiceRequestStatus
from services.models import ServiceType
from services.services import sincronizar_servicos, solicitar_servicos
from spaces.models import Space

User = get_user_model()


@pytest.fixture
def usuario(db):
    """Return the reservation owner."""
    return User.objects.create_user(username="fulano", password="senha-de-teste-123")


@pytest.fixture
def alheio(db):
    """Return somebody else."""
    return User.objects.create_user(username="alheio", password="senha-de-teste-123")


@pytest.fixture
def logado(client, usuario):
    """Return a client logged in as the owner."""
    client.force_login(usuario)
    return client


@pytest.fixture
def sala(db):
    """Return a room for eight people."""
    return Space.objects.create(name="Sala Alfa", capacity=8, location="1º andar")


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
    """Return a confirmed reservation with details filled in."""
    return create_reservation(
        usuario,
        sala,
        instante(dia_aberto, 9),
        instante(dia_aberto, 10),
        title="Reunião de alinhamento",
        attendee_count=4,
        notes="Trazer o relatório",
    )


@pytest.fixture
def cafe(sala):
    """Return a service offered in the room."""
    servico = ServiceType.objects.create(name="Café", slug="cafe-teste", sort_order=10)
    servico.spaces.add(sala)
    return servico


@pytest.fixture
def limpeza(sala):
    """Return a second service offered in the room."""
    servico = ServiceType.objects.create(name="Limpeza", slug="limpeza-teste", sort_order=20)
    servico.spaces.add(sala)
    return servico


@pytest.mark.django_db
class TestAtualizarDetalhes:
    """The domain function behind the screen."""

    def test_altera_o_que_a_reserva_e(self, reserva, usuario):
        """O caminho feliz."""
        atualizar_detalhes(
            reserva, usuario, title="Outro assunto", attendee_count=6, notes="Sem café"
        )
        reserva.refresh_from_db()
        assert reserva.title == "Outro assunto"
        assert reserva.attendee_count == 6
        assert reserva.notes == "Sem café"

    def test_nao_mexe_em_quando_acontece(self, reserva, usuario):
        """Editar não é reagendar: a agenda de terceiros não é tocada."""
        inicio, fim = reserva.start_time, reserva.end_time
        atualizar_detalhes(reserva, usuario, title="Outro", attendee_count=None, notes="")
        reserva.refresh_from_db()
        assert reserva.start_time == inicio
        assert reserva.end_time == fim

    def test_recusa_quem_nao_e_dono(self, reserva, alheio):
        """A reserva é de quem reservou."""
        with pytest.raises(OwnershipError):
            atualizar_detalhes(reserva, alheio, title="Invadida", attendee_count=None, notes="")

    def test_recusa_reserva_encerrada(self, reserva, usuario):
        """Cancelada é história; história não se edita."""
        reserva.status = ReservationStatus.CANCELLED
        reserva.save(update_fields=["status"])
        with pytest.raises(ValidationError):
            atualizar_detalhes(reserva, usuario, title="Outro", attendee_count=None, notes="")

    def test_valida_capacidade_do_espaco_atual(self, reserva, usuario):
        """Subir para 40 numa sala de 8 é o mesmo erro de sempre."""
        with pytest.raises(ValidationError):
            atualizar_detalhes(reserva, usuario, title="Outro", attendee_count=40, notes="")

    def test_aceita_esvaziar_participantes(self, reserva, usuario):
        """O campo é opcional desde a Fase 14, inclusive na edição."""
        atualizar_detalhes(reserva, usuario, title="Outro", attendee_count=None, notes="")
        reserva.refresh_from_db()
        assert reserva.attendee_count is None


@pytest.mark.django_db
class TestSincronizarServicos:
    """The rule that protects work the administration already picked up."""

    def test_acrescenta_servico_novo(self, reserva, cafe):
        """Marcar algo que não estava lá cria o pedido."""
        resultado = sincronizar_servicos(reserva, [(cafe, "")])
        assert len(resultado["criados"]) == 1
        assert reserva.service_requests.count() == 1

    def test_remove_pedido_que_ninguem_tocou(self, reserva, cafe):
        """Enquanto está só "Solicitado", desmarcar é desistir de pedir."""
        solicitar_servicos(reserva, [(cafe, "")])
        resultado = sincronizar_servicos(reserva, [])
        assert resultado["removidos"] == [cafe]
        assert reserva.service_requests.count() == 0

    def test_nao_remove_pedido_ja_recebido(self, reserva, cafe, alheio):
        """Alguém já leu e se organizou. Apagar sumiria com o trabalho da fila."""
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        pedido.status = ServiceRequestStatus.ACKNOWLEDGED
        pedido.save(update_fields=["status"])

        resultado = sincronizar_servicos(reserva, [])
        assert resultado["removidos"] == []
        assert len(resultado["mantidos"]) == 1
        assert reserva.service_requests.count() == 1
        pedido.refresh_from_db()
        assert pedido.status == ServiceRequestStatus.ACKNOWLEDGED

    def test_nao_remove_pedido_em_andamento(self, reserva, cafe):
        """Em andamento é alguém executando agora."""
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        pedido.status = ServiceRequestStatus.IN_PROGRESS
        pedido.save(update_fields=["status"])
        sincronizar_servicos(reserva, [])
        assert reserva.service_requests.count() == 1

    def test_o_motivo_diz_o_que_fazer(self, reserva, cafe):
        """Um aviso que não diz o próximo passo devolve o problema ao usuário."""
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        pedido.status = ServiceRequestStatus.ACKNOWLEDGED
        pedido.save(update_fields=["status"])
        _servico, motivo = sincronizar_servicos(reserva, [])["mantidos"][0]
        assert "Fale com" in motivo

    def test_pedido_encerrado_nao_vira_aviso(self, reserva, cafe, alheio):
        """Concluído ou recusado é história: não sai, e não precisa avisar."""
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        pedido.status = ServiceRequestStatus.COMPLETED
        pedido.save(update_fields=["status"])
        resultado = sincronizar_servicos(reserva, [])
        assert resultado["mantidos"] == []
        assert resultado["removidos"] == []
        assert reserva.service_requests.count() == 1

    def test_atualiza_o_detalhamento(self, reserva, cafe):
        """Continuar pedido e mudar o que se precisa é o caso comum."""
        solicitar_servicos(reserva, [(cafe, "Para quatro")])
        resultado = sincronizar_servicos(reserva, [(cafe, "Para oito")])
        assert len(resultado["atualizados"]) == 1
        assert reserva.service_requests.get().notes == "Para oito"

    def test_troca_um_servico_por_outro(self, reserva, cafe, limpeza):
        """Desmarcar um e marcar outro numa passada só."""
        solicitar_servicos(reserva, [(cafe, "")])
        resultado = sincronizar_servicos(reserva, [(limpeza, "")])
        assert resultado["removidos"] == [cafe]
        assert len(resultado["criados"]) == 1
        assert reserva.service_requests.get().service_type == limpeza

    def test_sem_mudanca_nao_mexe_em_nada(self, reserva, cafe):
        """Salvar sem alterar não pode recriar nem duplicar pedido."""
        pedido = solicitar_servicos(reserva, [(cafe, "Igual")])[0][0]
        resultado = sincronizar_servicos(reserva, [(cafe, "Igual")])
        assert resultado["criados"] == []
        assert resultado["removidos"] == []
        assert resultado["atualizados"] == []
        assert reserva.service_requests.get().pk == pedido.pk


@pytest.mark.django_db
class TestTelaDeEdicao:
    """The screen itself."""

    def test_abre_preenchida(self, logado, reserva, cafe):
        """Editar começa do que está lá, não de um formulário vazio."""
        solicitar_servicos(reserva, [(cafe, "Para quatro")])
        resposta = logado.get(reverse("reservation_details_edit", args=[reserva.pk]))
        assert resposta.status_code == 200
        assert resposta.context["prefill_title"] == "Reunião de alinhamento"
        assert resposta.context["prefill_attendee_count"] == "4"
        assert resposta.context["prefill_notes"] == "Trazer o relatório"
        html = resposta.content.decode()
        assert "Para quatro" in html
        assert f'value="{cafe.pk}"' in html

    def test_nao_oferece_data_nem_horario(self, logado, reserva):
        """Mudar quando é Reagendar, e a tela diz isso em vez de aceitar."""
        html = logado.get(reverse("reservation_details_edit", args=[reserva.pk])).content.decode()
        assert 'name="start_time"' not in html
        assert 'name="date"' not in html
        assert "Reagendar" in html

    def test_salva_e_volta_para_o_detalhe(self, logado, reserva):
        """O caminho feliz da tela."""
        resposta = logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {"title": "Assunto novo", "attendee_count": "6", "notes": "Outra observação"},
        )
        assert resposta.status_code == 302
        assert resposta.url == reverse("reservation_detail", args=[reserva.pk])
        reserva.refresh_from_db()
        assert reserva.title == "Assunto novo"
        assert reserva.attendee_count == 6

    def test_capacidade_invalida_volta_o_formulario(self, logado, reserva):
        """Nada é gravado, e o que foi digitado continua na tela."""
        resposta = logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {"title": "Assunto novo", "attendee_count": "40", "notes": "Nota"},
        )
        assert resposta.status_code == 200
        assert "comporta até 8" in resposta.content.decode()
        reserva.refresh_from_db()
        assert reserva.title == "Reunião de alinhamento"

    def test_participantes_escrito_e_invalido_e_recusado(self, logado, reserva):
        """Em branco é ausência; texto é engano."""
        resposta = logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {"title": "Assunto", "attendee_count": "muitas", "notes": ""},
        )
        assert resposta.status_code == 200
        reserva.refresh_from_db()
        assert reserva.attendee_count == 4

    def test_reserva_cancelada_nao_abre(self, logado, reserva):
        """História não se edita, e a tela nem chega a aparecer."""
        reserva.status = ReservationStatus.CANCELLED
        reserva.save(update_fields=["status"])
        resposta = logado.get(reverse("reservation_details_edit", args=[reserva.pk]))
        assert resposta.status_code == 302
        assert resposta.url == reverse("reservation_detail", args=[reserva.pk])

    def test_reserva_de_outro_da_404(self, client, reserva, alheio):
        """Nem editar, nem descobrir que existe."""
        client.force_login(alheio)
        resposta = client.get(reverse("reservation_details_edit", args=[reserva.pk]))
        assert resposta.status_code == 404

    def test_pedido_travado_aparece_onde_a_decisao_acontece(self, logado, reserva, cafe):
        """O aviso fica na própria caixa, e não num rodapé lido depois de tentar.

        A primeira versão desta tela punha um bloco no fim da página. A pessoa
        desmarcava o serviço, rolava, e só então descobria que não adiantava.
        """
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        pedido.status = ServiceRequestStatus.IN_PROGRESS
        pedido.save(update_fields=["status"])

        resposta = logado.get(reverse("reservation_details_edit", args=[reserva.pk]))
        assert list(resposta.context["pedidos_travados"]) == [pedido]
        html = resposta.content.decode()
        caixa = html.split(f'id="servico-{cafe.pk}"')[0].rsplit("<input", 1)[1]
        assert "disabled" in caixa
        assert "Já está com a administração" in html
        assert "em andamento" in html

    def test_travado_nao_pode_ser_desmarcado_pela_tela(self, logado, reserva, cafe):
        """A caixa desabilitada não envia; o ``hidden`` mantém o pedido no envio.

        Sem ele o servidor veria "desmarcado" e avisaria toda vez que a pessoa
        salvasse qualquer outra coisa — um alarme para uma ação que ela nem
        tentou fazer.
        """
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        pedido.status = ServiceRequestStatus.IN_PROGRESS
        pedido.save(update_fields=["status"])

        html = logado.get(reverse("reservation_details_edit", args=[reserva.pk])).content.decode()
        assert f'<input type="hidden" name="services" value="{cafe.pk}">' in html

    def test_salvar_outra_coisa_nao_alarma_sobre_o_travado(self, logado, reserva, cafe):
        """Mudar o assunto não pode disparar aviso sobre um serviço intocado."""
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        pedido.status = ServiceRequestStatus.IN_PROGRESS
        pedido.save(update_fields=["status"])

        resposta = logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {
                "title": "Assunto novo",
                "attendee_count": "4",
                "notes": "",
                "services": [str(cafe.pk)],
                f"service_notes_{cafe.pk}": "",
            },
            follow=True,
        )
        assert reserva.service_requests.count() == 1
        avisos = [str(m) for m in resposta.context["messages"]]
        assert not [aviso for aviso in avisos if "Fale com" in aviso]

    def test_post_forjado_ainda_nao_remove_o_travado(self, logado, reserva, cafe):
        """A tela protege; a regra é quem garante.

        Um POST montado à mão sem o serviço não pode apagar trabalho da fila —
        e aí sim o aviso aparece, porque alguém de fato tentou.
        """
        pedido = solicitar_servicos(reserva, [(cafe, "")])[0][0]
        pedido.status = ServiceRequestStatus.IN_PROGRESS
        pedido.save(update_fields=["status"])

        resposta = logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {"title": "Assunto", "attendee_count": "4", "notes": ""},
            follow=True,
        )
        assert reserva.service_requests.count() == 1
        avisos = [str(m) for m in resposta.context["messages"]]
        assert any("Fale com" in aviso for aviso in avisos)

    def test_detalhamento_obrigatorio_vale_na_edicao(self, logado, reserva, sala):
        """A mesma regra do passo 3, no mesmo seletor de serviços."""
        exigente = ServiceType.objects.create(
            name="Audiovisual", slug="av-edicao", requires_notes=True
        )
        exigente.spaces.add(sala)
        resposta = logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {
                "title": "Assunto",
                "attendee_count": "4",
                "notes": "",
                "services": [str(exigente.pk)],
                f"service_notes_{exigente.pk}": "",
            },
        )
        assert resposta.status_code == 200
        assert reserva.service_requests.count() == 0
        assert "Descreva o que você precisa" in resposta.content.decode()

    def test_botao_editar_aparece_no_detalhe(self, logado, reserva):
        """Sem o botão, a tela existiria e ninguém a encontraria."""
        resposta = logado.get(reverse("reservation_detail", args=[reserva.pk]))
        assert resposta.context["can_edit"] is True
        assert reverse("reservation_details_edit", args=[reserva.pk]) in resposta.content.decode()

    def test_botao_some_em_reserva_encerrada(self, logado, reserva):
        """Oferecer uma ação que vai ser recusada é pior do que não oferecer."""
        reserva.status = ReservationStatus.NO_SHOW
        reserva.save(update_fields=["status"])
        resposta = logado.get(reverse("reservation_detail", args=[reserva.pk]))
        assert resposta.context["can_edit"] is False
        assert (
            reverse("reservation_details_edit", args=[reserva.pk]) not in resposta.content.decode()
        )


@pytest.mark.django_db
class TestNaoRegressao:
    """What editing must not break."""

    def test_editar_nao_muda_o_dono(self, logado, reserva, usuario):
        """O organizador continua sendo quem reservou."""
        logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {"title": "Assunto", "attendee_count": "4", "notes": ""},
        )
        reserva.refresh_from_db()
        assert reserva.user == usuario

    def test_editar_nao_muda_a_situacao(self, logado, reserva):
        """Editar detalhes não confirma, não cancela e não faz check-in."""
        reserva.status = ReservationStatus.CHECKED_IN
        reserva.save(update_fields=["status"])
        logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {"title": "Assunto", "attendee_count": "4", "notes": ""},
        )
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.CHECKED_IN

    def test_editar_nao_libera_o_horario(self, logado, reserva, sala, alheio, dia_aberto):
        """O espaço continua ocupado enquanto a reserva vale."""
        from reservations.services import create_reservation as criar

        logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {"title": "Assunto", "attendee_count": "4", "notes": ""},
        )
        with pytest.raises(ValidationError):
            criar(alheio, sala, instante(dia_aberto, 9), instante(dia_aberto, 10))
        assert Reservation.objects.count() == 1

    def test_detalhamento_do_travado_nao_e_editavel(self, logado, reserva, cafe):
        """Um campo editável que não tem efeito é uma mentira na tela.

        A administração já leu este texto; mudá-lo sem avisá-la faria as duas
        partes trabalharem com informações diferentes.
        """
        pedido = solicitar_servicos(reserva, [(cafe, "Para quatro pessoas")])[0][0]
        pedido.status = ServiceRequestStatus.ACKNOWLEDGED
        pedido.save(update_fields=["status"])

        html = logado.get(reverse("reservation_details_edit", args=[reserva.pk])).content.decode()
        campo = html.split(f'id="servico-{cafe.pk}-notas"')[1].split(">")[0]
        assert "disabled" in campo

    def test_texto_forjado_no_travado_nao_altera_o_pedido(self, logado, reserva, cafe):
        """O campo desabilitado protege a tela; a regra protege o dado."""
        pedido = solicitar_servicos(reserva, [(cafe, "Para quatro pessoas")])[0][0]
        pedido.status = ServiceRequestStatus.ACKNOWLEDGED
        pedido.save(update_fields=["status"])

        logado.post(
            reverse("reservation_details_edit", args=[reserva.pk]),
            {
                "title": "Assunto",
                "attendee_count": "4",
                "notes": "",
                "services": [str(cafe.pk)],
                f"service_notes_{cafe.pk}": "Para quarenta pessoas",
            },
        )
        pedido.refresh_from_db()
        assert pedido.notes == "Para quatro pessoas"
