"""Tests for step 2 of the booking flow: date and time.

O que esta tela não pode fazer:

* Esconder manutenção como se fosse reserva — o pacote V2 proíbe, e quem vê
  "reservado" tenta de novo amanhã, enquanto quem vê "manutenção" procura outra
  sala.
* Dizer "indisponível" e parar. As duas perguntas seguintes — "então quando?" e
  "então onde?" — precisam vir respondidas.
* Sugerir um auditório para quem procurava uma sala de quatro lugares.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from reservations.availability import (
    agrupar_por_periodo,
    espacos_equivalentes,
    gerar_slots,
    horarios_proximos,
)
from reservations.models import BookingPolicy, MaintenanceBlock, Reservation, ReservationStatus
from spaces.models import Space, SpaceType

User = get_user_model()


@pytest.fixture
def hoje():
    """Return today in the local timezone."""
    return timezone.localdate()


@pytest.fixture(autouse=True)
def policy(db):
    """Return a booking policy that opens every day of the week.

    ``autouse`` porque os testes de tela não pedem a fixture — eles batem na
    URL —, e sem ela a página renderizaria um sábado fechado.

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
def dono(db):
    """Return a user who can hold reservations and maintenance blocks."""
    return User.objects.create_user(username="dono", password="senha-de-teste-123")


@pytest.fixture
def logado(client, db):
    """Return a logged-in client."""
    User.objects.create_user(username="user", password="senha-de-teste-123")
    client.login(username="user", password="senha-de-teste-123")
    return client


@pytest.fixture
def sala(db):
    """Return a meeting room of moderate size."""
    return Space.objects.create(
        name="Sala Alfa",
        capacity=8,
        location="1º andar",
        space_type=SpaceType.objects.get(slug="sala-de-reuniao"),
    )


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


def ocupa(espaco, dono, date, hora, horas=1):
    """Book a space for a stretch of a day.

    Args:
        espaco: O espaço.
        dono: O usuário dono da reserva.
        date: O dia.
        hora: Hora local de início.
        horas: Duração em horas.
    """
    Reservation.objects.create(
        space=espaco,
        user=dono,
        start_time=local(date, hora),
        end_time=local(date, hora) + datetime.timedelta(hours=horas),
        status=ReservationStatus.CONFIRMED,
    )


@pytest.mark.django_db
class TestAgrupamentoPorPeriodo:
    """Splitting the day into morning and afternoon."""

    def test_separa_manha_e_tarde(self, sala, policy, hoje):
        """Vinte botões em fileira única são difíceis de varrer com os olhos."""
        grupos = agrupar_por_periodo(gerar_slots(sala, hoje, policy))
        assert [grupo["rotulo"] for grupo in grupos] == ["Manhã", "Tarde"]

    def test_meio_dia_cai_na_tarde(self, sala, policy, hoje):
        """O corte é meio-dia, e 12:00 já é tarde."""
        grupos = agrupar_por_periodo(gerar_slots(sala, hoje, policy))
        tarde = next(g for g in grupos if g["rotulo"] == "Tarde")
        assert timezone.localtime(tarde["slots"][0]["inicio"]).hour == 12

    def test_grupo_vazio_nao_entra(self, sala, policy, hoje):
        """Uma janela só de manhã não deve renderizar um cabeçalho "Tarde" vazio."""
        policy.opening_time = datetime.time(8, 0)
        policy.closing_time = datetime.time(11, 0)
        policy.save()
        grupos = agrupar_por_periodo(gerar_slots(sala, hoje, policy))
        assert [grupo["rotulo"] for grupo in grupos] == ["Manhã"]

    def test_nenhum_slot_nao_gera_grupo(self):
        """Sem horários, nada a agrupar."""
        assert agrupar_por_periodo([]) == []


@pytest.mark.django_db
class TestHorariosProximos:
    """The "then when?" answer."""

    def test_ordena_pela_distancia_ao_horario_pedido(self, sala, policy, hoje, dono):
        """Quem queria 15h prefere 14h30 a 08h."""
        ocupa(sala, dono, hoje, 15, horas=1)
        slots = gerar_slots(sala, hoje, policy)
        sugestoes = horarios_proximos(slots, local(hoje, 15))
        horas = [timezone.localtime(slot["inicio"]).strftime("%H:%M") for slot in sugestoes]
        assert horas[0] in {"14:30", "16:00"}
        assert "08:00" not in horas

    def test_nao_sugere_horario_ocupado(self, sala, policy, hoje, dono):
        """Sugerir o que também está ocupado seria pior do que não sugerir."""
        ocupa(sala, dono, hoje, 15, horas=1)
        slots = gerar_slots(sala, hoje, policy)
        for slot in horarios_proximos(slots, local(hoje, 15)):
            assert slot["disponivel"]

    def test_respeita_o_limite(self, sala, policy, hoje):
        """Uma lista longa de sugestões deixa de ser sugestão."""
        slots = gerar_slots(sala, hoje, policy)
        assert len(horarios_proximos(slots, local(hoje, 15), limite=3)) == 3

    def test_dia_lotado_nao_sugere_nada(self, sala, policy, hoje, dono):
        """Sem horário livre, não há o que oferecer."""
        ocupa(sala, dono, hoje, 8, horas=10)
        slots = gerar_slots(sala, hoje, policy)
        assert horarios_proximos(slots, local(hoje, 15)) == []


@pytest.mark.django_db
class TestEspacosEquivalentes:
    """The "then where?" answer."""

    @pytest.fixture
    def vizinhas(self, db):
        """Create neighbouring spaces of various kinds and sizes."""
        reuniao = SpaceType.objects.get(slug="sala-de-reuniao")
        auditorio = SpaceType.objects.get(slug="auditorio")
        return {
            "menor": Space.objects.create(
                name="Sala Pequena", capacity=4, location="1º andar", space_type=reuniao
            ),
            "igual": Space.objects.create(
                name="Sala Beta", capacity=8, location="2º andar", space_type=reuniao
            ),
            "maior": Space.objects.create(
                name="Sala Gama", capacity=12, location="3º andar", space_type=reuniao
            ),
            "outro_tipo": Space.objects.create(
                name="Auditório Central", capacity=200, location="Térreo", space_type=auditorio
            ),
        }

    def test_sugere_espaco_do_mesmo_tipo(self, sala, vizinhas, policy, hoje):
        """Trocar de sala não deveria virar trocar de categoria."""
        sugeridos = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy)
        nomes = {espaco.name for espaco in sugeridos}
        assert "Sala Beta" in nomes
        assert "Auditório Central" not in nomes

    def test_nao_sugere_espaco_menor(self, sala, vizinhas, policy, hoje):
        """Quem cabia em 8 não cabe em 4."""
        sugeridos = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy)
        assert "Sala Pequena" not in {espaco.name for espaco in sugeridos}

    def test_nao_sugere_o_proprio_espaco(self, sala, vizinhas, policy, hoje):
        """O usuário já está olhando para ele."""
        sugeridos = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy)
        assert sala not in sugeridos

    def test_nao_sugere_espaco_ocupado_no_horario(self, sala, vizinhas, policy, hoje, dono):
        """Sugerir o que também está ocupado seria trocar um problema por outro."""
        ocupa(vizinhas["igual"], dono, hoje, 15, horas=1)
        sugeridos = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy)
        assert "Sala Beta" not in {espaco.name for espaco in sugeridos}
        assert "Sala Gama" in {espaco.name for espaco in sugeridos}

    def test_nao_sugere_espaco_desativado(self, sala, vizinhas, policy, hoje):
        """O atalho levaria a uma tela que recusaria a reserva."""
        vizinhas["igual"].is_active = False
        vizinhas["igual"].save()
        sugeridos = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy)
        assert "Sala Beta" not in {espaco.name for espaco in sugeridos}

    def test_considera_a_duracao_pedida(self, sala, vizinhas, policy, hoje, dono):
        """Uma sala livre às 15h pode não estar livre até as 17h."""
        ocupa(vizinhas["igual"], dono, hoje, 16, horas=1)
        curto = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy, duracao_minutos=30)
        longo = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy, duracao_minutos=120)
        assert "Sala Beta" in {espaco.name for espaco in curto}
        assert "Sala Beta" not in {espaco.name for espaco in longo}

    def test_inclui_espaco_ainda_nao_classificado(self, sala, vizinhas, policy, hoje):
        """A classificação é revisada por humanos e vai ficando pronta aos poucos.

        Excluir o que ainda não tem tipo esconderia salas boas por uma pendência
        administrativa que o usuário não tem como ver nem resolver.
        """
        Space.objects.create(name="Sala Sem Tipo", capacity=10, location="4º andar")
        sugeridos = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy)
        assert "Sala Sem Tipo" in {espaco.name for espaco in sugeridos}

    def test_mesmo_tipo_vem_antes_do_nao_classificado(self, sala, vizinhas, policy, hoje):
        """A sugestão mais segura aparece primeiro."""
        Space.objects.create(name="Sala Sem Tipo", capacity=8, location="4º andar")
        sugeridos = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy)
        assert sugeridos[0].space_type_id == sala.space_type_id

    def test_nao_sugere_espaco_grande_demais(self, sala, vizinhas, policy, hoje):
        """Um auditório de 50 lugares para quem queria 8 não é "a mesma coisa com folga"."""
        Space.objects.create(name="Salão Enorme", capacity=200, location="Térreo")
        sugeridos = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy)
        assert "Salão Enorme" not in {espaco.name for espaco in sugeridos}

    def test_o_teto_nao_vale_para_o_mesmo_tipo(self, sala, vizinhas, policy, hoje):
        """Quem procurava um auditório e recebe um auditório maior recebeu o que pediu."""
        grande = Space.objects.create(
            name="Sala Enorme", capacity=200, location="Térreo", space_type=sala.space_type
        )
        sugeridos = espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy, limite=10)
        assert grande in sugeridos

    def test_espaco_sem_tipo_nao_restringe_por_tipo(self, vizinhas, policy, hoje):
        """Sem tipo cadastrado, o critério que sobra é a capacidade."""
        sem_tipo = Space.objects.create(name="Sala Focus", capacity=4, location="1º andar")
        sugeridos = espacos_equivalentes(sem_tipo, hoje, datetime.time(15, 0), policy)
        assert sugeridos

    def test_custo_nao_cresce_com_o_numero_de_candidatos(
        self, sala, vizinhas, policy, hoje, django_assert_max_num_queries
    ):
        """Uma consulta por sugestão seria o N+1 de novo, num lugar diferente."""
        for indice in range(20):
            Space.objects.create(
                name=f"Sala {indice}",
                capacity=10,
                location="4º andar",
                space_type=sala.space_type,
            )
        with django_assert_max_num_queries(3):
            espacos_equivalentes(sala, hoje, datetime.time(15, 0), policy)


@pytest.mark.django_db
class TestTelaDoPasso2:
    """The rendered screen."""

    def test_mostra_periodos(self, logado, sala):
        """Manhã e tarde ganham cabeçalho próprio."""
        conteudo = logado.get(reverse("space_detail", args=[sala.pk])).content.decode()
        assert "Manhã" in conteudo
        assert "Tarde" in conteudo

    def test_manutencao_nao_se_disfarca_de_reserva(self, logado, sala, dono, hoje):
        """Exigência explícita do pacote V2."""
        MaintenanceBlock.objects.create(
            space=sala,
            start_time=local(hoje, 14),
            end_time=local(hoje, 15),
            reason="Troca do projetor",
            created_by=dono,
        )
        conteudo = logado.get(reverse("space_detail", args=[sala.pk])).content.decode()
        assert "Manutenção" in conteudo
        assert "bloqueado para manutenção" in conteudo

    def test_sem_horario_pedido_nao_ha_alternativas(self, logado, sala):
        """Sugestão sem problema a resolver é ruído."""
        resposta = logado.get(reverse("space_detail", args=[sala.pk]))
        assert resposta.context["horario_pedido"] is None
        assert "Alternativas" not in resposta.content.decode()

    def test_horario_pedido_livre_e_confirmado(self, logado, sala):
        """Quem chegou pedindo 15h e encontrou 15h livre precisa saber disso."""
        resposta = logado.get(reverse("space_detail", args=[sala.pk]), {"start": "15:00"})
        assert resposta.context["horario_disponivel"] is True
        conteudo = resposta.content.decode()
        assert "está livre" in conteudo
        assert "Alternativas" not in conteudo

    def test_horario_pedido_ocupado_traz_alternativas(self, logado, sala, dono, hoje):
        """As duas perguntas seguintes vêm respondidas."""
        Space.objects.create(
            name="Sala Beta", capacity=8, location="2º andar", space_type=sala.space_type
        )
        ocupa(sala, dono, hoje, 15, horas=1)
        resposta = logado.get(reverse("space_detail", args=[sala.pk]), {"start": "15:00"})
        assert resposta.context["horario_disponivel"] is False
        assert resposta.context["horarios_alternativos"]
        assert resposta.context["espacos_alternativos"]
        conteudo = resposta.content.decode()
        assert "não está disponível" in conteudo
        assert "Horários próximos" in conteudo
        assert "Outros espaços livres" in conteudo

    def test_sem_alternativa_nenhuma_diz_isso(self, logado, sala, dono, hoje):
        """Uma seção "Alternativas" vazia seria pior do que uma frase honesta."""
        ocupa(sala, dono, hoje, 8, horas=10)
        resposta = logado.get(reverse("space_detail", args=[sala.pk]), {"start": "15:00"})
        assert resposta.context["horarios_alternativos"] == []
        assert resposta.context["espacos_alternativos"] == []
        assert "Tente outra data" in resposta.content.decode()

    def test_horario_fora_do_expediente_e_ignorado(self, logado, sala):
        """Pedir 22h não pode gerar erro nem uma seção de alternativas absurda."""
        resposta = logado.get(reverse("space_detail", args=[sala.pk]), {"start": "22:00"})
        assert resposta.status_code == 200
        assert resposta.context["horario_pedido"] is None

    def test_horario_malformado_e_ignorado(self, logado, sala):
        """A tela não pode cair por um parâmetro digitado errado."""
        resposta = logado.get(reverse("space_detail", args=[sala.pk]), {"start": "tarde"})
        assert resposta.status_code == 200
        assert resposta.context["horario_pedido"] is None

    def test_horario_sobrevive_a_troca_de_data(self, logado, sala):
        """Trocar o dia não pode apagar o horário que a pessoa pediu."""
        conteudo = logado.get(
            reverse("space_detail", args=[sala.pk]), {"start": "15:00"}
        ).content.decode()
        assert 'id="horario-pedido"' in conteudo
        assert 'value="15:00"' in conteudo

    def test_fragmento_htmx_traz_as_alternativas(self, logado, sala, dono, hoje):
        """Trocar a data precisa recalcular as sugestões junto."""
        ocupa(sala, dono, hoje, 15, horas=1)
        resposta = logado.get(
            reverse("space_detail", args=[sala.pk]),
            {"start": "15:00"},
            HTTP_HX_REQUEST="true",
        )
        conteudo = resposta.content.decode()
        assert "spaces/_availability.html" in [t.name for t in resposta.templates]
        assert "Alternativas" in conteudo
        assert "<html" not in conteudo

    def test_capacidade_em_linguagem_humana(self, logado, sala):
        """Mesmo texto do cartão do passo 1."""
        assert (
            "Até 8 pessoas" in logado.get(reverse("space_detail", args=[sala.pk])).content.decode()
        )

    def test_slot_livre_leva_ao_passo_seguinte(self, logado, sala):
        """O botão precisa carregar início e fim, não só o início."""
        conteudo = logado.get(reverse("space_detail", args=[sala.pk])).content.decode()
        assert f"/reservations/new/?space={sala.pk}&start=" in conteudo
        assert "&end=" in conteudo
