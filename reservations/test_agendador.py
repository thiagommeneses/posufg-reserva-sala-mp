"""Tests for the no-show release rule and the loop that runs it.

Duas coisas justificam este arquivo:

* **A regra vem desligada.** Ela é a única rotina que muda o estado de uma
  reserva sem ninguém pedir. Ligá-la por engano cancelaria reservas de gente
  que estava na sala.
* **O laço não pode morrer.** Um agendador que sai no primeiro erro para de
  funcionar justamente quando a aplicação mais precisa dele — e ninguém
  percebe, porque a falha é silenciosa.

O relógio aqui é congelado com ``freezegun``. Estes testes existem sobre um
"agora" preciso, e derivar esse agora do relógio real foi o que causou três
falhas em fases anteriores.
"""

import datetime
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time

from reservations.models import BookingPolicy, Reservation, ReservationStatus
from reservations.services import auto_release_no_shows
from spaces.models import Space

User = get_user_model()

#: Uma quarta-feira às 10h, em Goiás. Fixo de propósito.
AGORA = "2026-09-02 13:00:00+00:00"


@pytest.fixture
def usuario(db):
    """Return a user who can hold reservations."""
    return User.objects.create_user(username="fulano", password="senha-de-teste-123")


@pytest.fixture
def sala(db):
    """Return a room."""
    return Space.objects.create(name="Sala Alfa", capacity=8, location="1º andar")


@pytest.fixture
def politica_ligada(db):
    """Return the policy with the no-show release turned on."""
    politica = BookingPolicy.carregar()
    politica.release_no_shows = True
    politica.no_show_threshold_minutes = 15
    politica.save()
    return politica


def reserva_em(sala, usuario, minutos_atras, status=ReservationStatus.CONFIRMED):
    """Create a reservation that started a given number of minutes ago.

    Args:
        sala: O espaço.
        usuario: O dono da reserva.
        minutos_atras: Quantos minutos atrás ela começou.
        status: A situação inicial.

    Returns:
        Reservation: A reserva criada.
    """
    inicio = timezone.now() - datetime.timedelta(minutes=minutos_atras)
    return Reservation.objects.create(
        space=sala,
        user=usuario,
        start_time=inicio,
        end_time=inicio + datetime.timedelta(hours=1),
        status=status,
    )


@freeze_time(AGORA)
@pytest.mark.django_db
class TestRegraDesligada:
    """The rule ships off, like ``enforce_window`` before it."""

    def test_nao_faz_nada_com_a_politica_desligada(self, sala, usuario):
        """Ligar isto por engano cancelaria reservas de quem estava na sala."""
        reserva = reserva_em(sala, usuario, minutos_atras=120)
        assert auto_release_no_shows() == 0
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.CONFIRMED

    def test_o_padrao_do_banco_e_desligado(self, db):
        """Quem migrar não deve descobrir a regra funcionando sozinha."""
        assert BookingPolicy.carregar().release_no_shows is False

    def test_forcar_executa_mesmo_desligada(self, sala, usuario):
        """A passada manual existe para quem sabe o que está fazendo."""
        reserva = reserva_em(sala, usuario, minutos_atras=120)
        assert auto_release_no_shows(respeitar_politica=False) == 1
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.NO_SHOW


@freeze_time(AGORA)
@pytest.mark.django_db
class TestRegraLigada:
    """What the rule does once an administrator turns it on."""

    def test_libera_depois_da_tolerancia(self, sala, usuario, politica_ligada):
        """O caso que a regra existe para resolver."""
        reserva = reserva_em(sala, usuario, minutos_atras=20)
        assert auto_release_no_shows() == 1
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.NO_SHOW

    def test_respeita_a_tolerancia_da_politica(self, sala, usuario, politica_ligada):
        """Dezesseis minutos não é atraso quando a casa tolera trinta."""
        politica_ligada.no_show_threshold_minutes = 30
        politica_ligada.save(update_fields=["no_show_threshold_minutes"])
        reserva = reserva_em(sala, usuario, minutos_atras=16)
        assert auto_release_no_shows() == 0
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.CONFIRMED

    def test_dentro_da_tolerancia_continua_confirmada(self, sala, usuario, politica_ligada):
        """Dez minutos de atraso ainda é alguém a caminho."""
        reserva = reserva_em(sala, usuario, minutos_atras=10)
        assert auto_release_no_shows() == 0
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.CONFIRMED

    def test_quem_fez_check_in_nao_e_tocado(self, sala, usuario, politica_ligada):
        """A pessoa está na sala. Liberar o espaço seria expulsá-la."""
        reserva = reserva_em(sala, usuario, minutos_atras=120, status=ReservationStatus.CHECKED_IN)
        assert auto_release_no_shows() == 0
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.CHECKED_IN

    def test_cancelada_nao_vira_nao_compareceu(self, sala, usuario, politica_ligada):
        """Quem cancelou avisou; dizer que não compareceu seria outra história."""
        reserva = reserva_em(sala, usuario, minutos_atras=120, status=ReservationStatus.CANCELLED)
        assert auto_release_no_shows() == 0
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.CANCELLED

    def test_reserva_futura_nao_e_tocada(self, sala, usuario, politica_ligada):
        """Uma reserva de amanhã não está atrasada."""
        reserva = reserva_em(sala, usuario, minutos_atras=-60)
        assert auto_release_no_shows() == 0
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.CONFIRMED

    def test_o_espaco_volta_a_ficar_livre(self, sala, usuario, politica_ligada):
        """Liberar é o ponto: outra pessoa precisa conseguir reservar."""
        from reservations.services import create_reservation

        reserva = reserva_em(sala, usuario, minutos_atras=20)
        auto_release_no_shows()
        outro = User.objects.create_user(username="outro", password="senha-de-teste-123")
        nova = create_reservation(outro, sala, reserva.start_time, reserva.end_time)
        assert nova.pk


@freeze_time(AGORA)
@pytest.mark.django_db
class TestComandoDeUmaPassada:
    """``release_no_shows`` — the manual pass."""

    def test_avisa_quando_a_regra_esta_desligada(self, sala, usuario):
        """Sair em silêncio faria parecer que a passada rodou e não achou nada."""
        saida = StringIO()
        call_command("release_no_shows", stdout=saida)
        assert "desligada" in saida.getvalue()

    def test_forcar_ignora_a_politica(self, sala, usuario):
        """Quem usa --forcar já foi avisado no help do comando."""
        reserva_em(sala, usuario, minutos_atras=120)
        saida = StringIO()
        call_command("release_no_shows", "--forcar", stdout=saida)
        assert "1 reserva(s) liberada(s)" in saida.getvalue()

    def test_threshold_da_linha_de_comando_vence(self, sala, usuario, politica_ligada):
        """A passada manual pode usar outra tolerância sem mexer na política."""
        reserva_em(sala, usuario, minutos_atras=20)
        saida = StringIO()
        call_command("release_no_shows", "--threshold", "60", stdout=saida)
        assert "0 reserva(s) liberada(s)" in saida.getvalue()
        assert "60 minutos" in saida.getvalue()


@freeze_time(AGORA)
@pytest.mark.django_db
class TestAgendador:
    """The loop, which must survive a bad pass."""

    def test_executa_a_liberacao(self, sala, usuario, politica_ligada):
        """Sem o laço, a regra continuaria escrita e nunca acontecendo."""
        reserva = reserva_em(sala, usuario, minutos_atras=20)
        call_command("agendador", "--passadas", "1", "--intervalo", "0", stdout=StringIO())
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.NO_SHOW

    def test_uma_passada_com_erro_nao_derruba_o_laco(self, sala, usuario, politica_ligada):
        """O agendador não pode morrer porque o banco piscou."""
        chamadas = []

        def falha_na_primeira(*args, **kwargs):
            chamadas.append(1)
            if len(chamadas) == 1:
                raise RuntimeError("conexão caiu")
            return 0

        erros = StringIO()
        with patch(
            "reservations.management.commands.agendador.auto_release_no_shows",
            side_effect=falha_na_primeira,
        ):
            call_command(
                "agendador", "--passadas", "2", "--intervalo", "0", stdout=StringIO(), stderr=erros
            )

        assert len(chamadas) == 2
        assert "será repetida" in erros.getvalue()

    def test_para_no_numero_de_passadas_pedido(self, sala, usuario, politica_ligada):
        """Sem isto não haveria como testar o laço sem esperar para sempre."""
        with patch(
            "reservations.management.commands.agendador.auto_release_no_shows", return_value=0
        ) as liberar:
            call_command("agendador", "--passadas", "3", "--intervalo", "0", stdout=StringIO())
        assert liberar.call_count == 3

    def test_dorme_entre_passadas(self, sala, usuario, politica_ligada):
        """O intervalo é o que impede o laço de martelar o banco."""
        with patch("reservations.management.commands.agendador.time.sleep") as dormir:
            call_command("agendador", "--passadas", "2", "--intervalo", "42", stdout=StringIO())
        dormir.assert_called_once_with(42)


@pytest.mark.django_db
class TestRelogioCongelado:
    """freezegun itself, since three failures came from not having it."""

    @freeze_time("2026-09-02 23:50:00-03:00")
    def test_a_suite_pode_rodar_perto_da_meia_noite(self, sala, usuario, politica_ligada):
        """Foi exatamente esta faixa que derrubou a suíte na Fase 12."""
        reserva = reserva_em(sala, usuario, minutos_atras=20)
        assert auto_release_no_shows() == 1
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.NO_SHOW

    @freeze_time("2026-09-02 06:00:00-03:00")
    def test_e_tambem_de_madrugada(self, sala, usuario, politica_ligada):
        """Mesma regra, outra hora, mesmo resultado."""
        reserva = reserva_em(sala, usuario, minutos_atras=20)
        assert auto_release_no_shows() == 1
        reserva.refresh_from_db()
        assert reserva.status == ReservationStatus.NO_SHOW
