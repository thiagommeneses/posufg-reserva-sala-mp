"""Tests for when a cancellation happened, and for the two readings of it.

O sistema passou a ter as duas coisas ao mesmo tempo, e é isso que estes testes
protegem:

* o que for cancelado a partir de agora tem data de cancelamento;
* o que já estava cancelado não tem, nem vai ter — e continua contável, pelo
  horário da reserva, que é a única âncora verdadeira do histórico.

Somar as duas parcelas sem separá-las esconderia que a mesma métrica responde a
duas perguntas diferentes. Há teste afirmando que elas voltam separadas.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from reservations.models import BookingPolicy, Reservation, ReservationStatus
from reservations.services import (
    OwnershipError,
    admin_cancel_reservation,
    cancel_reservation,
)
from spaces.models import Space

User = get_user_model()


def local(date, hora, minuto=0):
    """Return an aware datetime in the local timezone."""
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hora, minuto)))


@pytest.fixture(autouse=True)
def policy(db):
    """Open every weekday: these tests are about cancelling, not about weekdays."""
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
def dono(db):
    """Return the person who holds the reservation."""
    return User.objects.create_user(username="dono", password="senha-de-teste-123")


@pytest.fixture
def gestor(db):
    """Return a staff member."""
    return User.objects.create_user(
        username="gestor", password="senha-de-teste-123", is_staff=True
    )


@pytest.fixture
def dia():
    """Return a fixed day, so nothing here depends on when the suite runs."""
    return datetime.date(2026, 3, 11)


def reserva(espaco, user, dia, inicio=9, fim=10, **extra):
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


@pytest.mark.django_db
class TestGravacao:
    """Both cancellation doors must record the date."""

    def test_o_dono_cancelando_registra_a_data(self, espaco, dono, dia):
        """A porta comum grava quando o cancelamento aconteceu."""
        minha = reserva(espaco, dono, dia)
        antes = timezone.now()
        cancel_reservation(minha, dono)
        minha.refresh_from_db()
        assert minha.status == ReservationStatus.CANCELLED
        assert minha.cancelled_at is not None
        assert minha.cancelled_at >= antes

    def test_a_administracao_cancelando_tambem_registra(self, espaco, dono, dia):
        """A segunda porta é o lugar clássico de esquecer a data.

        As duas passam pelo mesmo escritor justamente para que uma não possa
        divergir da outra — e este teste é o que garante que continuem passando.
        """
        alheia = reserva(espaco, dono, dia)
        admin_cancel_reservation(alheia)
        alheia.refresh_from_db()
        assert alheia.cancelled_at is not None

    def test_cancelar_pela_api_registra_a_data(self, client, espaco, dono, dia):
        """Todo caminho de escrita, não só a tela."""
        minha = reserva(espaco, dono, dia)
        client.force_login(dono)
        client.post(reverse("reservation_cancel", args=[minha.pk]))
        minha.refresh_from_db()
        assert minha.status == ReservationStatus.CANCELLED
        assert minha.cancelled_at is not None

    def test_recusa_de_terceiro_nao_toca_na_reserva(self, espaco, dono, gestor, dia):
        """Uma recusa por dono não pode deixar rastro de cancelamento."""
        minha = reserva(espaco, dono, dia)
        with pytest.raises(OwnershipError):
            cancel_reservation(minha, gestor)
        minha.refresh_from_db()
        assert minha.cancelled_at is None
        assert minha.status == ReservationStatus.CONFIRMED

    def test_recusa_por_status_nao_toca_na_reserva(self, espaco, dono, dia):
        """Cancelar o que já está cancelado não reescreve a data original."""
        minha = reserva(espaco, dono, dia)
        cancel_reservation(minha, dono)
        minha.refresh_from_db()
        primeira = minha.cancelled_at
        with pytest.raises(ValidationError):
            cancel_reservation(minha, dono)
        minha.refresh_from_db()
        assert minha.cancelled_at == primeira

    def test_o_no_show_nao_e_cancelamento(self, espaco, dono, dia):
        """Não comparecer e desistir são coisas diferentes.

        Marcar ``cancelled_at`` no no-show faria o relatório de cancelamentos
        engordar com gente que só não apareceu — e sumir com a diferença que a
        administração precisa justamente para decidir o que fazer.
        """
        minha = reserva(espaco, dono, dia, status=ReservationStatus.NO_SHOW)
        assert minha.cancelled_at is None


@pytest.mark.django_db
class TestLeituraDupla:
    """The two readings, and the fact that they stay distinguishable."""

    def test_conta_pela_data_do_cancelamento_quando_existe(self, espaco, dono, dia):
        """O cancelamento entra no período em que aconteceu."""
        # Reserva marcada para daqui a um mês, cancelada hoje.
        futura = reserva(espaco, dono, dia + datetime.timedelta(days=30))
        cancel_reservation(futura, dono)

        hoje = timezone.localdate()
        inicio = local(hoje, 0)
        fim = inicio + datetime.timedelta(days=1)
        resumo = Reservation.objects.resumo_de_cancelamentos(inicio, fim)
        assert resumo["total"] == 1
        assert resumo["por_ocorrencia"] == 1
        assert resumo["sem_data"] == 0

    def test_conta_pelo_horario_da_reserva_quando_nao_ha_data(self, espaco, dono, dia):
        """O histórico anterior à coluna continua contável.

        Descartá-lo por falta de data faria o relatório dizer que não houve
        cancelamento nenhum antes da migration — o que é falso.
        """
        antiga = reserva(espaco, dono, dia, status=ReservationStatus.CANCELLED)
        assert antiga.cancelled_at is None

        inicio = local(dia, 0)
        fim = inicio + datetime.timedelta(days=1)
        resumo = Reservation.objects.resumo_de_cancelamentos(inicio, fim)
        assert resumo["total"] == 1
        assert resumo["por_ocorrencia"] == 0
        assert resumo["sem_data"] == 1

    def test_as_duas_parcelas_voltam_separadas(self, espaco, dono, dia):
        """Somá-las sem dizer que são diferentes esconderia a diferença.

        As duas respondem a perguntas distintas: uma diz quando a pessoa
        desistiu, a outra diz quanta sala foi liberada. O número único é útil, e
        por isso existe — mas a tela precisa poder dizer de que é feito.
        """
        # Uma antiga, sem data, com horário dentro da janela.
        reserva(espaco, dono, dia, inicio=9, status=ReservationStatus.CANCELLED)
        # Uma nova, cancelada dentro da mesma janela.
        nova = reserva(espaco, dono, dia, inicio=14, fim=15)
        cancel_reservation(nova, dono)
        nova.refresh_from_db()
        # Força a data do cancelamento para dentro da janela examinada.
        Reservation.objects.filter(pk=nova.pk).update(cancelled_at=local(dia, 15))

        inicio = local(dia, 0)
        fim = inicio + datetime.timedelta(days=1)
        resumo = Reservation.objects.resumo_de_cancelamentos(inicio, fim)
        assert resumo == {"total": 2, "por_ocorrencia": 1, "sem_data": 1}

    def test_a_reserva_com_data_nao_e_contada_duas_vezes(self, espaco, dono, dia):
        """Com data **e** horário na mesma janela, ela é um cancelamento só.

        O ``OR`` do filtro é o lugar onde a contagem dupla nasce: sem excluir o
        caso "tem data" do ramo do horário, a mesma linha entraria pelos dois.
        """
        minha = reserva(espaco, dono, dia, inicio=9)
        cancel_reservation(minha, dono)
        Reservation.objects.filter(pk=minha.pk).update(cancelled_at=local(dia, 10))

        inicio = local(dia, 0)
        fim = inicio + datetime.timedelta(days=1)
        assert Reservation.objects.canceladas_entre(inicio, fim).count() == 1

    def test_reserva_ativa_nao_entra(self, espaco, dono, dia):
        """Só cancelamento conta como cancelamento."""
        reserva(espaco, dono, dia)
        inicio = local(dia, 0)
        fim = inicio + datetime.timedelta(days=1)
        assert Reservation.objects.resumo_de_cancelamentos(inicio, fim)["total"] == 0

    def test_fora_da_janela_nao_entra(self, espaco, dono, dia):
        """A janela é fechada à esquerda e aberta à direita, como todo período."""
        reserva(espaco, dono, dia, status=ReservationStatus.CANCELLED)
        inicio = local(dia + datetime.timedelta(days=1), 0)
        fim = inicio + datetime.timedelta(days=1)
        assert Reservation.objects.resumo_de_cancelamentos(inicio, fim)["total"] == 0

    def test_a_api_publica_a_data(self, client, espaco, dono, dia):
        """Acrescentar campo é a direção compatível; quem não usa, ignora."""
        minha = reserva(espaco, dono, dia)
        cancel_reservation(minha, dono)
        client.force_login(dono)
        resposta = client.get(f"/api/v1/reservations/{minha.pk}/")
        assert resposta.status_code == 200
        assert resposta.json()["cancelled_at"] is not None
