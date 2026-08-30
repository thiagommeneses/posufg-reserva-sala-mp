"""Tests for the reservation detail fields and the user profile.

Duas coisas guiam esta fase:

* **O histórico não pode ser invalidado.** As reservas anteriores não têm
  assunto nem número de participantes. Os campos são opcionais no banco, e
  inventar valores para elas seria criar dado falso.
* **O organizador não é um campo de formulário.** É quem está logado. Nome e
  lotação saem do perfil — o pacote V2 proíbe pedir de novo o que o sistema já
  pode saber.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Profile, nome_de_exibicao
from reservations.models import Reservation, ReservationStatus
from reservations.services import create_reservation
from reservations.validators import (
    ATTENDEE_COUNT_INVALID_CODE,
    ATTENDEE_COUNT_OVER_CAPACITY_CODE,
    validate_attendee_count,
)
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


@pytest.mark.django_db
class TestValidacaoDeParticipantes:
    """The attendee-count rule, which lives in the domain."""

    def test_aceita_dentro_da_capacidade(self, sala):
        """O caso normal."""
        validate_attendee_count(sala, 8)

    def test_recusa_acima_da_capacidade(self, sala):
        """Uma reserva para 20 numa sala de 8 não cabe."""
        with pytest.raises(ValidationError) as exc:
            validate_attendee_count(sala, 20)
        assert exc.value.code == ATTENDEE_COUNT_OVER_CAPACITY_CODE
        assert "8" in exc.value.messages[0]

    def test_recusa_zero(self, sala):
        """Reserva para ninguém não é reserva."""
        with pytest.raises(ValidationError) as exc:
            validate_attendee_count(sala, 0)
        assert exc.value.code == ATTENDEE_COUNT_INVALID_CODE

    def test_aceita_ausencia(self, sala):
        """As reservas anteriores à Fase 10 não têm esse dado."""
        validate_attendee_count(sala, None)

    def test_o_modelo_aplica_a_regra(self, sala, usuario, dia_aberto):
        """A mesma regra precisa valer em qualquer caminho de escrita."""
        reserva = Reservation(
            space=sala,
            user=usuario,
            start_time=instante(dia_aberto, 9),
            end_time=instante(dia_aberto, 10),
            attendee_count=20,
        )
        with pytest.raises(ValidationError):
            reserva.full_clean()


@pytest.mark.django_db
class TestServico:
    """The service layer, shared by the web form and the API."""

    def test_grava_os_campos_novos(self, sala, usuario, dia_aberto):
        """O caminho feliz."""
        reserva = create_reservation(
            usuario,
            sala,
            instante(dia_aberto, 9),
            instante(dia_aberto, 10),
            title="Reunião de alinhamento",
            attendee_count=6,
            notes="Precisa de café",
        )
        assert reserva.title == "Reunião de alinhamento"
        assert reserva.attendee_count == 6
        assert reserva.notes == "Precisa de café"

    def test_continua_funcionando_sem_os_campos(self, sala, usuario, dia_aberto):
        """O contrato anterior à Fase 10 não pode ter quebrado."""
        reserva = create_reservation(
            usuario, sala, instante(dia_aberto, 9), instante(dia_aberto, 10)
        )
        assert reserva.pk is not None
        assert reserva.title == ""
        assert reserva.attendee_count is None

    def test_recusa_participantes_acima_da_capacidade(self, sala, usuario, dia_aberto):
        """A regra é aplicada antes de gravar, não depois."""
        with pytest.raises(ValidationError):
            create_reservation(
                usuario,
                sala,
                instante(dia_aberto, 9),
                instante(dia_aberto, 10),
                attendee_count=20,
            )
        assert Reservation.objects.count() == 0


@pytest.mark.django_db
class TestPerfil:
    """The profile, which exists so step 3 does not ask for the organiser."""

    def test_criado_sob_demanda(self, usuario):
        """Sem sinal e sem migration de dados: quem precisa, pede."""
        assert not Profile.objects.exists()
        perfil = Profile.carregar(usuario)
        assert perfil.user == usuario
        assert Profile.objects.count() == 1

    def test_carregar_e_idempotente(self, usuario):
        """Chamar duas vezes não cria dois perfis."""
        Profile.carregar(usuario)
        Profile.carregar(usuario)
        assert Profile.objects.count() == 1

    def test_nome_cai_para_o_usuario_quando_vazio(self, usuario):
        """Um perfil em branco não pode deixar a tela sem nome."""
        assert Profile.carregar(usuario).nome_de_exibicao == "fulano"

    def test_nome_do_perfil_vence_o_do_django(self, usuario):
        """Quem preencheu o perfil quer ver o que preencheu."""
        usuario.first_name = "Maria"
        usuario.last_name = "Silva"
        usuario.save()
        perfil = Profile.carregar(usuario)
        perfil.full_name = "Maria da Silva Santos"
        perfil.save()
        assert perfil.nome_de_exibicao == "Maria da Silva Santos"

    def test_helper_funciona_sem_perfil(self, usuario):
        """Um template não tem como tratar RelatedObjectDoesNotExist."""
        assert nome_de_exibicao(usuario) == "fulano"

    def test_helper_usa_o_nome_do_django_quando_nao_ha_perfil(self, usuario):
        """O ``User`` já traz nome; o perfil só acrescenta a lotação."""
        usuario.first_name = "Maria"
        usuario.last_name = "Silva"
        usuario.save()
        assert nome_de_exibicao(usuario) == "Maria Silva"


@pytest.mark.django_db
class TestTelaDePerfil:
    """The screen that keeps the profile from being a field nobody fills."""

    def test_exige_login(self, client):
        """O perfil é pessoal."""
        resposta = client.get(reverse("accounts:profile"))
        assert resposta.status_code == 302
        assert "/accounts/login/" in resposta.url

    def test_abre_mesmo_sem_perfil_existente(self, logado):
        """A primeira visita cria o perfil vazio."""
        resposta = logado.get(reverse("accounts:profile"))
        assert resposta.status_code == 200
        assert Profile.objects.count() == 1

    def test_salva_nome_e_lotacao(self, logado, usuario):
        """O que se preenche aqui é o que o passo 3 deixa de perguntar."""
        resposta = logado.post(
            reverse("accounts:profile"),
            {"full_name": "Maria da Silva", "department": "3ª Promotoria de Justiça"},
        )
        assert resposta.status_code == 302
        perfil = Profile.objects.get(user=usuario)
        assert perfil.full_name == "Maria da Silva"
        assert perfil.department == "3ª Promotoria de Justiça"

    def test_campos_sao_opcionais(self, logado):
        """Lotação em branco é um estado legítimo."""
        resposta = logado.post(reverse("accounts:profile"), {"full_name": "", "department": ""})
        assert resposta.status_code == 302

    def test_link_no_menu_lateral(self, logado):
        """Sem entrada no menu, ninguém encontraria a tela."""
        conteudo = logado.get(reverse("inicio")).content.decode()
        assert "/accounts/profile/" in conteudo

    def test_menu_mostra_a_lotacao_quando_preenchida(self, logado, usuario):
        """O menu confirma, de relance, que o dado está lá."""
        Profile.objects.create(user=usuario, department="Corregedoria")
        conteudo = logado.get(reverse("inicio")).content.decode()
        assert "Corregedoria" in conteudo


@pytest.mark.django_db
class TestFormularioDeReserva:
    """The web form, which requires what the package asks for."""

    def _dados(self, sala, dia_aberto, **extras):
        """Build a valid POST payload.

        Args:
            sala: O espaço.
            dia_aberto: O dia da reserva.
            **extras: Campos a sobrescrever.

        Returns:
            dict: Dados do formulário.
        """
        dados = {
            "space": sala.pk,
            "date": dia_aberto.isoformat(),
            "start_time": "09:00",
            "end_time": "10:00",
            "title": "Reunião de alinhamento",
            "attendee_count": "6",
            "notes": "",
        }
        dados.update(extras)
        return dados

    def test_cria_com_os_campos_novos(self, logado, sala, dia_aberto):
        """O caminho feliz da tela."""
        resposta = logado.post(reverse("reservation_create"), self._dados(sala, dia_aberto))
        assert resposta.status_code == 302
        reserva = Reservation.objects.get()
        assert reserva.title == "Reunião de alinhamento"
        assert reserva.attendee_count == 6

    def test_recusa_participantes_acima_da_capacidade(self, logado, sala, dia_aberto):
        """A sala de 8 não recebe 20 pessoas."""
        resposta = logado.post(
            reverse("reservation_create"), self._dados(sala, dia_aberto, attendee_count="20")
        )
        assert resposta.status_code == 200
        assert "comporta até 8" in resposta.content.decode()
        assert not Reservation.objects.exists()

    def test_aceita_participantes_em_branco(self, logado, sala, dia_aberto):
        """Quem ainda não sabe quantas pessoas vêm não perde a sala por isso.

        Reverte a decisão da Fase 10, a pedido: o campo passou a ser opcional
        também no formulário, e não só no banco. O que sobrou de obrigatório é
        a coerência — ver o teste seguinte.
        """
        resposta = logado.post(
            reverse("reservation_create"), self._dados(sala, dia_aberto, attendee_count="")
        )
        assert resposta.status_code == 302
        assert Reservation.objects.get().attendee_count is None

    def test_recusa_participantes_escrito_e_invalido(self, logado, sala, dia_aberto):
        """Em branco é ausência; texto é engano, e engano se avisa."""
        resposta = logado.post(
            reverse("reservation_create"), self._dados(sala, dia_aberto, attendee_count="muitas")
        )
        assert resposta.status_code == 200
        assert not Reservation.objects.exists()

    def test_recusa_participantes_zero(self, logado, sala, dia_aberto):
        """Reserva para ninguém não é reserva."""
        resposta = logado.post(
            reverse("reservation_create"), self._dados(sala, dia_aberto, attendee_count="0")
        )
        assert resposta.status_code == 200
        assert not Reservation.objects.exists()

    def test_formulario_nao_exige_mais_o_campo(self, logado, sala):
        """Um ``required`` no HTML tornaria a regra nova inalcançável."""
        conteudo = logado.get(reverse("reservation_create"), {"space": sala.pk}).content.decode()
        campo = conteudo.split('id="id_attendee_count"')[1].split(">")[0]
        assert "required" not in campo

    def test_preserva_o_que_foi_digitado_no_erro(self, logado, sala, dia_aberto):
        """Perder o preenchimento a cada erro faz a pessoa desistir."""
        resposta = logado.post(
            reverse("reservation_create"),
            self._dados(sala, dia_aberto, attendee_count="20", notes="Precisa de café"),
        )
        conteudo = resposta.content.decode()
        assert "Reunião de alinhamento" in conteudo
        assert "Precisa de café" in conteudo

    def test_titulo_e_cortado_no_limite(self, logado, sala, dia_aberto):
        """Um título gigante não pode estourar a coluna do banco."""
        logado.post(reverse("reservation_create"), self._dados(sala, dia_aberto, title="A" * 400))
        assert len(Reservation.objects.get().title) == 160

    def test_participantes_vem_do_passo_1(self, logado, sala):
        """Quem já respondeu "quantas pessoas?" não deve responder de novo."""
        resposta = logado.get(reverse("reservation_create"), {"space": sala.pk, "people": "5"})
        assert resposta.context["prefill_attendee_count"] == 5

    def test_participantes_do_passo_1_maior_que_a_sala_fica_em_branco(self, logado, sala):
        """Preencher com um valor que o próprio formulário recusaria não ajuda."""
        resposta = logado.get(reverse("reservation_create"), {"space": sala.pk, "people": "50"})
        assert resposta.context["prefill_attendee_count"] == ""

    def test_nao_pergunta_o_organizador(self, logado, sala):
        """Exigência explícita do pacote V2."""
        conteudo = logado.get(reverse("reservation_create"), {"space": sala.pk}).content.decode()
        assert 'name="organizer"' not in conteudo
        assert 'name="department"' not in conteudo
        assert 'name="email"' not in conteudo


@pytest.mark.django_db
class TestTelaDeDetalhe:
    """The detail screen, which must not show empty labels."""

    def _reserva(self, usuario, sala, dia_aberto, **extras):
        """Create a reservation.

        Args:
            usuario: O dono.
            sala: O espaço.
            dia_aberto: O dia.
            **extras: Campos a sobrescrever.

        Returns:
            Reservation: A reserva criada.
        """
        return Reservation.objects.create(
            space=sala,
            user=usuario,
            start_time=instante(dia_aberto, 9),
            end_time=instante(dia_aberto, 10),
            status=ReservationStatus.CONFIRMED,
            **extras,
        )

    def test_mostra_os_campos_quando_existem(self, logado, usuario, sala, dia_aberto):
        """O caso das reservas novas."""
        reserva = self._reserva(
            usuario,
            sala,
            dia_aberto,
            title="Reunião de alinhamento",
            attendee_count=6,
            notes="Precisa de café",
        )
        conteudo = logado.get(reverse("reservation_detail", args=[reserva.pk])).content.decode()
        assert "Reunião de alinhamento" in conteudo
        assert "Participantes" in conteudo
        assert "Precisa de café" in conteudo

    def test_omite_os_campos_quando_ausentes(self, logado, usuario, sala, dia_aberto):
        """Rótulo com valor vazio é pior do que rótulo ausente."""
        reserva = self._reserva(usuario, sala, dia_aberto)
        conteudo = logado.get(reverse("reservation_detail", args=[reserva.pk])).content.decode()
        assert "Assunto" not in conteudo
        assert "Observações" not in conteudo

    def test_mostra_o_organizador(self, logado, usuario, sala, dia_aberto):
        """O organizador é quem reservou, não um campo digitado."""
        Profile.objects.create(user=usuario, full_name="Maria da Silva", department="Corregedoria")
        reserva = self._reserva(usuario, sala, dia_aberto)
        resposta = logado.get(reverse("reservation_detail", args=[reserva.pk]))
        assert resposta.context["organizador"] == "Maria da Silva"
        assert resposta.context["organizador_lotacao"] == "Corregedoria"
        assert "Corregedoria" in resposta.content.decode()

    def test_organizador_sem_perfil_nao_quebra(self, logado, usuario, sala, dia_aberto):
        """A maioria dos usuários ainda não tem perfil."""
        reserva = self._reserva(usuario, sala, dia_aberto)
        resposta = logado.get(reverse("reservation_detail", args=[reserva.pk]))
        assert resposta.status_code == 200
        assert resposta.context["organizador"] == "fulano"
        assert resposta.context["organizador_lotacao"] == ""


@pytest.mark.django_db
class TestApi:
    """The REST contract, which must stay backwards compatible."""

    @pytest.fixture
    def api(self, usuario):
        """Return an authenticated API client."""
        cliente = APIClient()
        cliente.force_authenticate(user=usuario)
        return cliente

    def test_cria_sem_os_campos_novos(self, api, sala, dia_aberto):
        """Um cliente antigo continua funcionando."""
        resposta = api.post(
            "/api/v1/reservations/",
            {
                "space": sala.pk,
                "start_time": instante(dia_aberto, 9).isoformat(),
                "end_time": instante(dia_aberto, 10).isoformat(),
            },
            format="json",
        )
        assert resposta.status_code == 201
        assert resposta.json()["title"] == ""
        assert resposta.json()["attendee_count"] is None

    def test_aceita_os_campos_novos(self, api, sala, dia_aberto):
        """E um cliente novo pode informá-los."""
        resposta = api.post(
            "/api/v1/reservations/",
            {
                "space": sala.pk,
                "start_time": instante(dia_aberto, 9).isoformat(),
                "end_time": instante(dia_aberto, 10).isoformat(),
                "title": "Reunião",
                "attendee_count": 6,
                "notes": "Café",
            },
            format="json",
        )
        assert resposta.status_code == 201
        assert Reservation.objects.get().attendee_count == 6

    def test_recusa_acima_da_capacidade_no_campo_certo(self, api, sala, dia_aberto):
        """O erro precisa apontar para o campo, não para o formulário inteiro."""
        resposta = api.post(
            "/api/v1/reservations/",
            {
                "space": sala.pk,
                "start_time": instante(dia_aberto, 9).isoformat(),
                "end_time": instante(dia_aberto, 10).isoformat(),
                "attendee_count": 50,
            },
            format="json",
        )
        assert resposta.status_code == 400
        assert "attendee_count" in resposta.json()
