"""Tests for the administration's general calendar.

Duas coisas precisam ser verdade ao mesmo tempo, e é fácil quebrar uma ao
consertar a outra:

* a administração **vê** assunto e quem reservou, porque precisa saber a quem
  ligar quando a sala cai;
* o calendário do usuário continua **não vendo** nada disso.

Como as duas telas passaram a compartilhar a mesma grade na Fase 19b, há teste
afirmando os dois lados — a regressão perigosa é a máquina comum começar a
carregar detalhe demais e o calendário do usuário publicá-lo sem querer.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from reservations import calendario
from reservations.models import BookingPolicy, MaintenanceBlock, Reservation, ReservationStatus
from spaces.models import Space, SpaceType

User = get_user_model()


def local(date, hora, minuto=0):
    """Return an aware datetime in the local timezone."""
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hora, minuto)))


@pytest.fixture
def policy(db):
    """Return the booking policy with the seeded defaults."""
    return BookingPolicy.carregar()


@pytest.fixture
def tipo(db):
    """Return a space type to filter by.

    Nome inventado de propósito: o catálogo já vem semeado com os tipos reais,
    e reutilizar um deles faria o teste esbarrar na unicidade do nome.
    """
    return SpaceType.objects.create(name="Tipo de teste")


@pytest.fixture
def sala(db):
    """Return a space on the first floor, with no type."""
    return Space.objects.create(name="Sala Alfa", capacity=8, location="1º andar")


@pytest.fixture
def auditorio(db, tipo):
    """Return a typed space on another floor."""
    return Space.objects.create(
        name="Auditório Central", capacity=120, location="Térreo", space_type=tipo
    )


@pytest.fixture
def servidor(db):
    """Return an ordinary user who holds reservations."""
    return User.objects.create_user(username="servidor", password="senha-de-teste-123")


@pytest.fixture
def gestor(db):
    """Return a staff member."""
    return User.objects.create_user(
        username="gestor", password="senha-de-teste-123", is_staff=True
    )


@pytest.fixture
def logado(client, gestor):
    """Return a client logged in as staff."""
    client.force_login(gestor)
    return client


@pytest.fixture
def dia_fixo():
    """Return a date that never depends on when the suite runs."""
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


@pytest.mark.django_db
class TestPermissao:
    """Who may open the general calendar."""

    def test_anonimo_nao_entra(self, client):
        """Sem sessão, não há administração."""
        resposta = client.get(reverse("admin_dashboard:calendar"))
        assert resposta.status_code in (302, 403)

    def test_usuario_comum_nao_entra(self, client, servidor):
        """O pacote V2 exige permissão explícita, e ela é a de staff.

        Sem este teste, o Calendário Geral seria o caminho mais curto para ler
        a agenda inteira do prédio com assunto e nome — exatamente o que o
        calendário do usuário foi construído para não permitir.
        """
        client.force_login(servidor)
        resposta = client.get(reverse("admin_dashboard:calendar"))
        assert resposta.status_code in (302, 403)

    def test_staff_entra(self, logado):
        """Quem administra a agenda abre a tela."""
        assert logado.get(reverse("admin_dashboard:calendar")).status_code == 200


@pytest.mark.django_db
class TestDetalheDaAdministracao:
    """What staff may see — and what stays out even for them."""

    def test_mostra_assunto_e_quem_reservou(self, gestor, servidor, sala, policy, dia_fixo):
        """Quem administra precisa saber a quem ligar quando a sala cai."""
        reserva(sala, servidor, dia_fixo, 9, 10, title="Reunião do comitê")
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        entrada = contexto["celula"]["entradas"][0]
        assert entrada["assunto"] == "Reunião do comitê"
        assert entrada["pessoa"] == "servidor"
        assert contexto["total_reservas"] == 1

    def test_reserva_sem_assunto_nao_repete_o_nome_da_sala(
        self, logado, servidor, sala, dia_fixo
    ):
        """Reservas antigas não têm assunto, e a linha some em vez de duplicar.

        A verificação visual pegou isto: com ``title or space.name``, o cartão
        imprimia "Sala Beta" no lugar do espaço e "Sala Beta" de novo no lugar
        do assunto, como se fossem duas informações.
        """
        import re

        reserva(sala, servidor, dia_fixo, 9, 10)
        html = logado.get(
            reverse("admin_dashboard:calendar"),
            {"vista": "dia", "data": dia_fixo.isoformat()},
        ).content.decode()
        # Só o corpo do cartão: o nome da sala também aparece — legitimamente —
        # no ``title`` do link e na lista do filtro de espaços.
        cartao = re.search(r'<a [^>]*bg-primary/5[^>]*>(.*?)</a>', html, re.S)
        assert cartao, "o cartão da reserva não foi renderizado"
        assert cartao.group(1).count(sala.name) == 1

    def test_as_observacoes_ficam_de_fora(self, gestor, servidor, sala, policy, dia_fixo):
        """Observação não é operação de sala.

        É o campo onde as pessoas escrevem coisas sem relação com a sala, e
        nenhuma tela de calendário — que fica aberta na mesa de quem
        administra — precisa delas.
        """
        reserva(
            sala,
            servidor,
            dia_fixo,
            9,
            10,
            title="Reunião",
            notes="Levar o laudo médico do periciado",
        )
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        assert "laudo" not in repr(contexto)

    def test_a_manutencao_mostra_o_motivo(self, gestor, sala, policy, dia_fixo):
        """O motivo é texto que a administração escreveu para ela mesma ler."""
        MaintenanceBlock.objects.create(
            space=sala,
            start_time=local(dia_fixo, 8),
            end_time=local(dia_fixo, 12),
            reason="Troca do ar-condicionado",
            created_by=gestor,
        )
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        entrada = contexto["celula"]["entradas"][0]
        assert entrada["motivo"] == "Troca do ar-condicionado"
        assert contexto["total_manutencoes"] == 1
        assert contexto["total_reservas"] == 0

    def test_reserva_cancelada_nao_ocupa(self, gestor, servidor, sala, policy, dia_fixo):
        """Cancelada não segura o espaço; mostrá-la faria a sala parecer cheia."""
        reserva(sala, servidor, dia_fixo, 9, 10, status=ReservationStatus.CANCELLED)
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        assert contexto["total"] == 0

    def test_o_calendario_do_usuario_continua_cego(
        self, servidor, gestor, sala, policy, dia_fixo
    ):
        """A grade virou comum na Fase 19b; a privacidade não podia vir junto.

        Esta é a regressão que o compartilhamento tornou possível: alimentar a
        máquina comum com as entradas completas e servi-las na tela do usuário.
        """
        reserva(sala, gestor, dia_fixo, 9, 10, title="Sindicância 2026/44")
        contexto = calendario.montar_calendario(
            servidor, calendario.VISTA_DIA, dia_fixo, incluir_ocupacao=True, policy=policy
        )
        assert contexto["celula"]["entradas"][0]["rotulo"] == calendario.OCUPADO
        assert "Sindicância" not in repr(contexto)


@pytest.mark.django_db
class TestFiltros:
    """Space, type and location."""

    def test_sem_filtro_mostra_todos_os_espacos(
        self, servidor, sala, auditorio, policy, dia_fixo
    ):
        """O padrão do Calendário Geral é geral."""
        reserva(sala, servidor, dia_fixo, 9, 10)
        reserva(auditorio, servidor, dia_fixo, 14, 15)
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        assert contexto["total_reservas"] == 2

    def test_filtro_por_espaco(self, servidor, sala, auditorio, policy, dia_fixo):
        """Um espaço escolhido esconde os outros."""
        reserva(sala, servidor, dia_fixo, 9, 10)
        reserva(auditorio, servidor, dia_fixo, 14, 15)
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, espaco=sala.pk, policy=policy
        )
        assert contexto["total_reservas"] == 1
        assert contexto["celula"]["entradas"][0]["espaco"] == sala.name

    def test_filtro_por_tipo(self, servidor, sala, auditorio, tipo, policy, dia_fixo):
        """Tipo é o filtro de quem pensa por categoria de espaço."""
        reserva(sala, servidor, dia_fixo, 9, 10)
        reserva(auditorio, servidor, dia_fixo, 14, 15)
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, tipo=tipo.pk, policy=policy
        )
        assert contexto["total_reservas"] == 1
        assert contexto["celula"]["entradas"][0]["espaco"] == auditorio.name

    def test_filtro_por_localizacao(self, servidor, sala, auditorio, policy, dia_fixo):
        """Localização é o filtro de quem administra um andar."""
        reserva(sala, servidor, dia_fixo, 9, 10)
        reserva(auditorio, servidor, dia_fixo, 14, 15)
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, local="Térreo", policy=policy
        )
        assert contexto["total_reservas"] == 1
        assert contexto["celula"]["entradas"][0]["espaco"] == auditorio.name

    def test_o_filtro_vale_tambem_para_a_manutencao(
        self, gestor, servidor, sala, auditorio, policy, dia_fixo
    ):
        """As duas metades da tela precisam concordar sobre quais espaços entram.

        O filtro é montado sobre ``Space`` justamente por isso: aplicá-lo só
        nas reservas deixaria manutenções de outro andar aparecendo numa tela
        que diz estar mostrando o térreo.
        """
        MaintenanceBlock.objects.create(
            space=sala,
            start_time=local(dia_fixo, 8),
            end_time=local(dia_fixo, 12),
            reason="Pintura",
            created_by=gestor,
        )
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, local="Térreo", policy=policy
        )
        assert contexto["total_manutencoes"] == 0

    def test_espaco_inativo_continua_no_calendario(
        self, servidor, sala, policy, dia_fixo
    ):
        """Desativar um espaço não apaga as reservas já marcadas nele.

        Escondê-las faria a administração descobrir o problema pela reclamação
        de quem apareceu na porta.
        """
        reserva(sala, servidor, dia_fixo, 9, 10, title="Marcada antes de desativar")
        sala.is_active = False
        sala.save(update_fields=["is_active"])
        contexto = calendario.montar_calendario_geral(
            calendario.VISTA_DIA, dia_fixo, policy=policy
        )
        assert contexto["total_reservas"] == 1


@pytest.mark.django_db
class TestTela:
    """The screen itself."""

    def test_as_tres_visoes_respondem(self, logado):
        """Dia, semana e mês, como o pacote V2 pede para o admin."""
        for vista in calendario.VISTAS:
            resposta = logado.get(reverse("admin_dashboard:calendar"), {"vista": vista})
            assert resposta.status_code == 200, vista
            assert resposta.context["vista"] == vista

    def test_filtro_invalido_nao_derruba_a_tela(self, logado):
        """URL editada ou link velho mostra o calendário, não uma exceção."""
        resposta = logado.get(
            reverse("admin_dashboard:calendar"), {"espaco": "abacaxi", "tipo": "-"}
        )
        assert resposta.status_code == 200
        assert resposta.context["ha_filtro"] is False

    def test_a_navegacao_preserva_os_filtros(self, logado, sala):
        """Trocar de mês não pode desfazer em silêncio o filtro escolhido."""
        resposta = logado.get(reverse("admin_dashboard:calendar"), {"espaco": sala.pk})
        assert f"espaco={sala.pk}" in resposta.context["url_proximo"]
        assert f"espaco={sala.pk}" in resposta.context["url_anterior"]
        for aba in resposta.context["vistas"]:
            assert f"espaco={sala.pk}" in aba["url"]

    def test_limpar_remove_os_filtros_e_mantem_o_dia(self, logado, sala, dia_fixo):
        """Limpar é sobre os filtros, não sobre onde a pessoa estava olhando."""
        resposta = logado.get(
            reverse("admin_dashboard:calendar"),
            {"espaco": sala.pk, "vista": "semana", "data": dia_fixo.isoformat()},
        )
        limpar = resposta.context["url_limpar"]
        assert "espaco" not in limpar
        assert "vista=semana" in limpar
        assert dia_fixo.isoformat() in limpar

    def test_a_tela_mostra_assunto_pessoa_e_motivo(
        self, logado, gestor, servidor, sala, dia_fixo
    ):
        """De ponta a ponta: o HTML renderizado carrega o que o staff pode ver."""
        reserva(sala, servidor, dia_fixo, 9, 10, title="Reunião do comitê")
        MaintenanceBlock.objects.create(
            space=sala,
            start_time=local(dia_fixo, 14),
            end_time=local(dia_fixo, 16),
            reason="Troca do ar-condicionado",
            created_by=gestor,
        )
        html = logado.get(
            reverse("admin_dashboard:calendar"),
            {"vista": "dia", "data": dia_fixo.isoformat()},
        ).content.decode()
        assert "Reunião do comitê" in html
        assert "servidor" in html
        assert "Troca do ar-condicionado" in html

    def test_as_contas_de_reserva_e_manutencao_ficam_separadas(
        self, logado, gestor, servidor, sala, dia_fixo
    ):
        """Somar as duas esconderia qual delas cresceu."""
        reserva(sala, servidor, dia_fixo, 9, 10)
        MaintenanceBlock.objects.create(
            space=sala,
            start_time=local(dia_fixo, 14),
            end_time=local(dia_fixo, 16),
            reason="Pintura",
            created_by=gestor,
        )
        resposta = logado.get(
            reverse("admin_dashboard:calendar"),
            {"vista": "dia", "data": dia_fixo.isoformat()},
        )
        assert resposta.context["total_reservas"] == 1
        assert resposta.context["total_manutencoes"] == 1

    def test_o_subtitulo_para_de_dizer_todos_quando_ha_filtro(self, logado, sala):
        """A tela não pode afirmar "todos os espaços" enquanto mostra um só.

        A verificação visual pegou isto: o subtítulo ficou dizendo o contrário
        do que a grade mostrava.
        """
        sem_filtro = logado.get(reverse("admin_dashboard:calendar")).content.decode()
        assert "de todos os espaços" in sem_filtro

        com_filtro = logado.get(
            reverse("admin_dashboard:calendar"), {"espaco": sala.pk}
        ).content.decode()
        assert "de todos os espaços" not in com_filtro
        assert "selecionados no filtro" in com_filtro

    def test_o_menu_admin_tem_calendario_geral(self, logado):
        """O item de menu entra junto com a tela — nunca antes."""
        html = logado.get(reverse("admin_dashboard:calendar")).content.decode()
        assert 'href="/admin-dashboard/calendario/"' in html
        assert "Calendário Geral" in html
