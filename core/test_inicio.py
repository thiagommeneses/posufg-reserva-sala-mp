"""Tests for the user's home screen.

Os riscos desta tela são de honestidade, não de cálculo: mostrar como "próxima"
uma reserva cancelada, oferecer check-in fora da janela em que ele seria aceito,
sugerir "reservar novamente" um espaço desativado, ou exibir uma regra que o
sistema não aplica. Cada um desses tem teste.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from core.dashboard import (
    espacos_para_repetir,
    informacoes_uteis,
    proxima_reserva,
    proximas_reservas,
)
from reservations.models import BookingPolicy, Reservation, ReservationStatus
from reservations.services import CHECK_IN_WINDOW_MINUTES
from spaces.models import Space

User = get_user_model()


@pytest.fixture
def usuario(db):
    """Return a regular user."""
    return User.objects.create_user(username="fulano", password="senha-de-teste-123")


@pytest.fixture
def logado(client, usuario):
    """Return a client logged in as that user."""
    client.force_login(usuario)
    return client


@pytest.fixture
def espaco(db):
    """Return an active space."""
    return Space.objects.create(name="Sala Alfa", capacity=8, location="1º andar")


@pytest.fixture
def agora():
    """Return a fixed reference instant."""
    return timezone.now()


def reserva(usuario, espaco, inicio, duracao_minutos=60, status=ReservationStatus.CONFIRMED):
    """Create a reservation.

    Args:
        usuario: Dono da reserva.
        espaco: Espaço reservado.
        inicio: Início.
        duracao_minutos: Duração.
        status: Situação da reserva.

    Returns:
        Reservation: A reserva criada.
    """
    return Reservation.objects.create(
        space=espaco,
        user=usuario,
        start_time=inicio,
        end_time=inicio + datetime.timedelta(minutes=duracao_minutos),
        status=status,
    )


@pytest.mark.django_db
class TestProximaReserva:
    """Which reservation the screen calls "next"."""

    def test_a_mais_proxima_no_futuro(self, usuario, espaco, agora):
        """Entre duas futuras, vence a mais próxima."""
        longe = reserva(usuario, espaco, agora + datetime.timedelta(days=3))
        perto = reserva(usuario, espaco, agora + datetime.timedelta(hours=2))
        assert proxima_reserva(usuario, agora) == perto
        assert longe not in [perto]

    def test_a_que_ja_comecou_e_a_proxima(self, usuario, espaco, agora):
        """Durante a reunião, o que interessa é ela — não a de amanhã."""
        em_curso = reserva(usuario, espaco, agora - datetime.timedelta(minutes=20))
        reserva(usuario, espaco, agora + datetime.timedelta(days=1))
        assert proxima_reserva(usuario, agora) == em_curso

    def test_ignora_reserva_encerrada(self, usuario, espaco, agora):
        """Uma reserva que já terminou não é a próxima de ninguém."""
        reserva(usuario, espaco, agora - datetime.timedelta(hours=3))
        assert proxima_reserva(usuario, agora) is None

    def test_ignora_cancelada(self, usuario, espaco, agora):
        """Mostrar uma cancelada como próxima faria a pessoa comparecer à toa."""
        reserva(
            usuario,
            espaco,
            agora + datetime.timedelta(hours=2),
            status=ReservationStatus.CANCELLED,
        )
        assert proxima_reserva(usuario, agora) is None

    def test_ignora_reserva_de_outro_usuario(self, usuario, espaco, agora):
        """A tela é pessoal."""
        outro = User.objects.create_user(username="beltrano", password="senha-de-teste-123")
        reserva(outro, espaco, agora + datetime.timedelta(hours=2))
        assert proxima_reserva(usuario, agora) is None

    def test_check_in_realizado_continua_sendo_a_proxima(self, usuario, espaco, agora):
        """Quem já fez check-in ainda precisa ver onde está."""
        atual = reserva(
            usuario,
            espaco,
            agora - datetime.timedelta(minutes=10),
            status=ReservationStatus.CHECKED_IN,
        )
        assert proxima_reserva(usuario, agora) == atual


@pytest.mark.django_db
class TestProximasReservas:
    """The list after the most imminent one."""

    def test_exclui_a_primeira(self, usuario, espaco, agora):
        """A próxima já tem o seu bloco; repeti-la seria ruído."""
        primeira = reserva(usuario, espaco, agora + datetime.timedelta(hours=1))
        segunda = reserva(usuario, espaco, agora + datetime.timedelta(days=1))
        seguintes = proximas_reservas(usuario, agora)
        assert primeira not in seguintes
        assert segunda in seguintes

    def test_ordena_da_mais_proxima_para_a_mais_distante(self, usuario, espaco, agora):
        """A ordem da lista é a ordem em que as coisas acontecem."""
        reserva(usuario, espaco, agora + datetime.timedelta(hours=1))
        for dias in [5, 2, 3]:
            reserva(usuario, espaco, agora + datetime.timedelta(days=dias))
        seguintes = proximas_reservas(usuario, agora)
        assert [r.start_time for r in seguintes] == sorted(r.start_time for r in seguintes)

    def test_respeita_o_limite(self, usuario, espaco, agora):
        """A tela é resumo; a lista inteira está em Minhas Reservas."""
        for horas in range(1, 12):
            reserva(usuario, espaco, agora + datetime.timedelta(hours=horas * 24))
        assert len(proximas_reservas(usuario, agora, limite=4)) == 4


@pytest.mark.django_db
class TestReservarNovamente:
    """Which spaces the shortcut offers."""

    def test_oferece_espaco_efetivamente_usado(self, usuario, espaco, agora):
        """Só entra o que aconteceu."""
        reserva(
            usuario,
            espaco,
            agora - datetime.timedelta(days=2),
            status=ReservationStatus.COMPLETED,
        )
        assert espacos_para_repetir(usuario) == [espaco]

    def test_nao_oferece_espaco_de_reserva_cancelada(self, usuario, espaco, agora):
        """Sugerir de volta o que a pessoa descartou é o oposto de ajudar."""
        reserva(
            usuario,
            espaco,
            agora - datetime.timedelta(days=2),
            status=ReservationStatus.CANCELLED,
        )
        assert espacos_para_repetir(usuario) == []

    def test_nao_oferece_espaco_de_nao_comparecimento(self, usuario, espaco, agora):
        """Não comparecer não é sinal de que a pessoa quer aquele espaço."""
        reserva(
            usuario,
            espaco,
            agora - datetime.timedelta(days=2),
            status=ReservationStatus.NO_SHOW,
        )
        assert espacos_para_repetir(usuario) == []

    def test_nao_oferece_espaco_desativado(self, usuario, espaco, agora):
        """O atalho levaria a uma tela que recusaria a reserva."""
        reserva(
            usuario,
            espaco,
            agora - datetime.timedelta(days=2),
            status=ReservationStatus.COMPLETED,
        )
        espaco.is_active = False
        espaco.save()
        assert espacos_para_repetir(usuario) == []

    def test_nao_repete_o_mesmo_espaco(self, usuario, espaco, agora):
        """Cinco reuniões na mesma sala são uma sugestão, não cinco."""
        for dias in [2, 5, 9]:
            reserva(
                usuario,
                espaco,
                agora - datetime.timedelta(days=dias),
                status=ReservationStatus.COMPLETED,
            )
        assert espacos_para_repetir(usuario) == [espaco]

    def test_ordena_pelo_uso_mais_recente(self, usuario, agora):
        """O que a pessoa usou ontem é mais provável do que o de três meses atrás."""
        antigo = Space.objects.create(name="Sala Antiga", capacity=4, location="1º andar")
        recente = Space.objects.create(name="Sala Recente", capacity=4, location="2º andar")
        reserva(
            usuario,
            antigo,
            agora - datetime.timedelta(days=60),
            status=ReservationStatus.COMPLETED,
        )
        reserva(
            usuario,
            recente,
            agora - datetime.timedelta(days=1),
            status=ReservationStatus.COMPLETED,
        )
        assert espacos_para_repetir(usuario) == [recente, antigo]

    def test_sem_historico_devolve_vazio(self, usuario):
        """Usuário novo não vê um bloco vazio."""
        assert espacos_para_repetir(usuario) == []


@pytest.mark.django_db
class TestInformacoesUteis:
    """The rules block, which must only state what the system enforces."""

    def test_reflete_a_politica_vigente(self):
        """Mudar a política muda o texto da tela — não há como envelhecer."""
        politica = BookingPolicy.carregar()
        politica.opening_time = datetime.time(7, 0)
        politica.closing_time = datetime.time(19, 0)
        politica.save()
        valores = [item["valor"] for item in informacoes_uteis(politica)]
        assert "07:00 às 19:00" in valores

    def test_todos_os_icones_existem(self):
        """Um ícone inválido renderizaria um espaço em branco."""
        from spaces.validators import ICONES_DISPONIVEIS

        politica = BookingPolicy.carregar()
        for item in informacoes_uteis(politica):
            assert item["icone"] in ICONES_DISPONIVEIS

    def test_nao_promete_liberacao_automatica_por_nao_comparecimento(self):
        """A liberação depende de um agendador externo que ainda não existe.

        Enquanto ninguém chamar ``manage.py release_no_shows`` periodicamente,
        prometer liberação automática seria informação falsa na tela.
        """
        politica = BookingPolicy.carregar()
        texto = " ".join(f"{i['rotulo']} {i['valor']}" for i in informacoes_uteis(politica))
        assert "automat" not in texto.lower()
        assert "no-show" not in texto.lower()


@pytest.mark.django_db
class TestTelaDeInicio:
    """The rendered screen."""

    def test_exige_login(self, client):
        """A tela é pessoal e não abre para anônimo."""
        resposta = client.get(reverse("inicio"))
        assert resposta.status_code == 302
        assert "/accounts/login/" in resposta.url

    def test_usuario_sem_reservas_ve_convite(self, logado):
        """Estado vazio precisa dizer o que fazer, não ficar em branco."""
        resposta = logado.get(reverse("inicio"))
        assert resposta.status_code == 200
        assert resposta.context["proxima"] is None
        assert "Você não tem nenhuma reserva marcada." in resposta.content.decode()

    def test_mostra_a_proxima_reserva(self, logado, usuario, espaco, agora):
        """O bloco principal traz espaço, data e horário."""
        reserva(usuario, espaco, agora + datetime.timedelta(days=1))
        conteudo = logado.get(reverse("inicio")).content.decode()
        assert "Sala Alfa" in conteudo
        assert "1º andar" in conteudo

    def test_oferece_check_in_dentro_da_janela(self, logado, usuario, espaco):
        """Dentro da janela, o botão aparece."""
        inicio = timezone.now() + datetime.timedelta(minutes=CHECK_IN_WINDOW_MINUTES - 5)
        reserva(usuario, espaco, inicio)
        resposta = logado.get(reverse("inicio"))
        assert resposta.context["pode_check_in"] is True
        assert "Fazer check-in" in resposta.content.decode()

    def test_nao_oferece_check_in_fora_da_janela(self, logado, usuario, espaco):
        """Oferecer um botão que o servidor recusaria é pior do que não oferecer."""
        reserva(usuario, espaco, timezone.now() + datetime.timedelta(days=1))
        resposta = logado.get(reverse("inicio"))
        assert resposta.context["pode_check_in"] is False
        assert "Fazer check-in" not in resposta.content.decode()

    def test_nao_oferece_check_in_para_quem_ja_fez(self, logado, usuario, espaco):
        """Check-in não se faz duas vezes."""
        reserva(
            usuario,
            espaco,
            timezone.now() - datetime.timedelta(minutes=5),
            status=ReservationStatus.CHECKED_IN,
        )
        resposta = logado.get(reverse("inicio"))
        assert resposta.context["pode_check_in"] is False
        assert "Check-in realizado" in resposta.content.decode()

    def test_check_in_pela_tela_de_inicio_funciona(self, logado, usuario, espaco):
        """O botão precisa levar a um POST que o servidor aceita de verdade."""
        agendada = reserva(usuario, espaco, timezone.now() + datetime.timedelta(minutes=5))
        resposta = logado.post(reverse("reservation_checkin", args=[agendada.pk]))
        assert resposta.status_code in (200, 302)
        agendada.refresh_from_db()
        assert agendada.status == ReservationStatus.CHECKED_IN

    def test_mostra_informacoes_uteis(self, logado):
        """As regras aparecem mesmo para quem não tem reserva nenhuma."""
        conteudo = logado.get(reverse("inicio")).content.decode()
        assert "Horário de funcionamento" in conteudo
        assert "Check-in" in conteudo

    def test_bloco_de_repetir_some_sem_historico(self, logado):
        """Sem histórico não há bloco vazio ocupando a tela."""
        conteudo = logado.get(reverse("inicio")).content.decode()
        assert "Reservar novamente" not in conteudo

    def test_bloco_de_repetir_aparece_com_historico(self, logado, usuario, espaco, agora):
        """Com histórico, o atalho aparece."""
        reserva(
            usuario,
            espaco,
            agora - datetime.timedelta(days=2),
            status=ReservationStatus.COMPLETED,
        )
        assert "Reservar novamente" in logado.get(reverse("inicio")).content.decode()

    def test_nao_exibe_kpi_de_vaidade(self, logado, usuario, espaco, agora):
        """Exigência explícita do pacote V2."""
        for dias in [2, 5, 9]:
            reserva(
                usuario,
                espaco,
                agora - datetime.timedelta(days=dias),
                status=ReservationStatus.COMPLETED,
            )
        conteudo = logado.get(reverse("inicio")).content.decode()
        for proibido in ["Total de reservas", "reservas realizadas", "Taxa de", "stat-value"]:
            assert proibido not in conteudo

    def test_raiz_leva_ao_inicio(self, logado):
        """A raiz do site é a porta de entrada."""
        resposta = logado.get("/")
        assert resposta.status_code == 302
        assert resposta.url == reverse("inicio")


@pytest.mark.django_db
class TestRedirecionamentoPosLogin:
    """Where each role lands after signing in."""

    def test_usuario_comum_cai_no_inicio(self, client, usuario):
        """A pergunta mais frequente de quem entra é "tenho algo agora?"."""
        resposta = client.post(
            reverse("accounts:login"),
            {"username": "fulano", "password": "senha-de-teste-123"},
        )
        assert resposta.url == reverse("inicio")

    def test_staff_continua_indo_para_o_painel(self, client, db):
        """A mudança não pode ter mexido no destino do administrador."""
        User.objects.create_user(username="chefe", password="senha-de-teste-123", is_staff=True)
        resposta = client.post(
            reverse("accounts:login"),
            {"username": "chefe", "password": "senha-de-teste-123"},
        )
        assert resposta.url == reverse("admin_dashboard:admin_dashboard")
