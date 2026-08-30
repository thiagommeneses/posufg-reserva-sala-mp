"""Tests for step 1 of the booking flow.

Três coisas precisam continuar verdadeiras enquanto a tela muda de forma:

* **Nada some da URL.** Aba, data, pessoas, filtros e o espaço escolhido são
  estado de servidor. Recarregar, voltar pelo histórico ou compartilhar o link
  precisa reproduzir a mesma tela.
* **A seleção nunca mente.** Se o espaço escolhido sai do resultado por causa de
  um filtro, a seleção cai junto — resumo apontando para um cartão que não está
  mais na lista é a tela contradizendo a si mesma.
* **O contrato antigo continua valendo.** ``min_capacity``/``max_capacity``
  saíram da interface, mas não da URL: links guardados e a API continuam
  funcionando.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from reservations.availability import (
    ROTULOS,
    STATUS_DE_HORARIO,
    STATUS_ENCERRADO,
    proximo_dia_aberto,
    resumo_em_lote,
)
from reservations.models import BookingPolicy, Reservation, ReservationStatus
from spaces.models import Attribute, Space, SpaceAttribute, SpaceType

User = get_user_model()


@pytest.fixture(autouse=True)
def politica_abre_todo_dia(db):
    """Open every weekday for the tests in this module.

    Os testes daqui são sobre cartões e horários, não sobre dia da semana. Com
    a política padrão (segunda a sexta) eles passariam a depender do dia em que
    a suíte roda e falhariam aos sábados, por um motivo sem relação com o que
    afirmam. O teste que **é** sobre dia da semana declara os dias que assume.
    """
    politica = BookingPolicy.carregar()
    politica.opens_saturday = True
    politica.opens_sunday = True
    politica.save(update_fields=["opens_saturday", "opens_sunday"])
    return politica



@pytest.fixture
def logado(client, db):
    """Return a logged-in client."""
    User.objects.create_user(username="user", password="senha-de-teste-123")
    client.login(username="user", password="senha-de-teste-123")
    return client


@pytest.fixture
def acervo(db):
    """Create three spaces of different sizes and types."""
    reuniao = SpaceType.objects.get(slug="sala-de-reuniao")
    auditorio = SpaceType.objects.get(slug="auditorio")
    return {
        "pequena": Space.objects.create(
            name="Sala Pequena", capacity=4, location="1º andar", space_type=reuniao
        ),
        "media": Space.objects.create(
            name="Sala Média", capacity=10, location="2º andar", space_type=reuniao
        ),
        "auditorio": Space.objects.create(
            name="Auditório Central", capacity=200, location="Térreo", space_type=auditorio
        ),
    }


def nomes(resposta):
    """Return the names of the spaces in the response context.

    Args:
        resposta: A resposta HTTP.

    Returns:
        set[str]: Nomes dos espaços listados.
    """
    return {espaco.name for espaco in resposta.context["spaces"]}


@pytest.mark.django_db
class TestQuantasPessoas:
    """The people field, which replaced min/max capacity in the interface."""

    def test_filtra_por_capacidade_suficiente(self, logado, acervo):
        """Pedir para 8 pessoas quer dizer "que caibam", não "que tenham exatamente"."""
        resposta = logado.get(reverse("space_list"), {"people": "8"})
        assert nomes(resposta) == {"Sala Média", "Auditório Central"}

    def test_valor_volta_para_o_campo(self, logado, acervo):
        """O que a pessoa digitou continua na tela depois da busca."""
        resposta = logado.get(reverse("space_list"), {"people": "8"})
        assert resposta.context["people"] == 8
        assert 'value="8"' in resposta.content.decode()

    def test_ignora_valor_sem_sentido(self, logado, acervo):
        """Texto ou zero não pode virar erro: o campo é auxílio de busca."""
        for invalido in ["abc", "0", "-3"]:
            resposta = logado.get(reverse("space_list"), {"people": invalido})
            assert resposta.status_code == 200
            assert nomes(resposta) == {"Sala Pequena", "Sala Média", "Auditório Central"}

    def test_capacidade_minima_e_maxima_continuam_aceitas(self, logado, acervo):
        """Saíram da interface, não do contrato: links guardados seguem valendo."""
        resposta = logado.get(reverse("space_list"), {"min_capacity": "5", "max_capacity": "50"})
        assert nomes(resposta) == {"Sala Média"}

    def test_interface_nao_oferece_mais_capacidade_minima(self, logado, acervo):
        """O pacote V2 proíbe capacidade mínima/máxima como interface principal."""
        conteudo = logado.get(reverse("space_list")).content.decode()
        assert 'name="min_capacity"' not in conteudo
        assert 'name="max_capacity"' not in conteudo
        assert "Quantas pessoas?" in conteudo

    def test_pessoas_convive_com_o_tipo(self, logado, acervo):
        """Os filtros se somam."""
        resposta = logado.get(reverse("space_list"), {"people": "8", "type": "sala-de-reuniao"})
        assert nomes(resposta) == {"Sala Média"}


@pytest.mark.django_db
class TestSeletorDeData:
    """The date control, which drives the availability badge."""

    def test_default_e_hoje(self, logado, acervo):
        """Quem não escolhe data está perguntando por hoje."""
        resposta = logado.get(reverse("space_list"))
        assert resposta.context["selected_date"] == timezone.localdate()
        assert resposta.context["data_e_hoje"] is True

    def test_aceita_outra_data(self, logado, acervo):
        """A data escolhida vale para o cálculo de disponibilidade."""
        amanha = timezone.localdate() + datetime.timedelta(days=1)
        resposta = logado.get(reverse("space_list"), {"date": amanha.isoformat()})
        assert resposta.context["selected_date"] == amanha
        assert resposta.context["data_e_hoje"] is False

    def test_limita_ao_horizonte_da_politica(self, logado, acervo):
        """Não se oferece um dia que a regra recusaria."""
        politica = BookingPolicy.carregar()
        limite = timezone.localdate() + datetime.timedelta(days=politica.horizon_days)
        conteudo = logado.get(reverse("space_list")).content.decode()
        assert f'max="{limite.isoformat()}"' in conteudo
        assert f'min="{timezone.localdate().isoformat()}"' in conteudo

    def test_rotulo_diz_a_que_dia_se_refere(self, logado, acervo):
        """O rótulo sozinho seria ambíguo depois de o usuário trocar a data.

        O que se verifica é o **sufixo**, não a palavra do status: qual status o
        dia de hoje tem depende da hora em que o teste roda, e prender a
        asserção a "Disponível" fazia a suíte passar de manhã e falhar à tarde.
        """
        hoje = logado.get(reverse("space_list")).content.decode()
        assert any(f"{rotulo} hoje" in hoje for rotulo in ROTULOS.values())

        amanha = timezone.localdate() + datetime.timedelta(days=1)
        outro = logado.get(reverse("space_list"), {"date": amanha.isoformat()}).content.decode()
        assert f"em {amanha.strftime('%d/%m')}" in outro

    def test_data_sobrevive_a_troca_de_aba(self, logado, acervo):
        """Trocar de aba não pode devolver o usuário para hoje."""
        amanha = timezone.localdate() + datetime.timedelta(days=1)
        resposta = logado.get(
            reverse("space_list"), {"date": amanha.isoformat(), "type": "auditorio"}
        )
        assert f"date={amanha.isoformat()}" in resposta.context["query_sem_tipo"]


@pytest.mark.django_db
class TestSelecaoDeEspaco:
    """Selecting a space, which is server state on the querystring."""

    def test_sem_selecao_nao_ha_resumo(self, logado, acervo):
        """Uma barra vazia o tempo todo seria ruído."""
        resposta = logado.get(reverse("space_list"))
        assert resposta.context["espaco_selecionado"] is None
        assert "Escolher horário" not in resposta.content.decode()

    def test_seleciona_pelo_parametro(self, logado, acervo):
        """A escolha viaja na URL: recarregar e compartilhar preservam."""
        media = acervo["media"]
        resposta = logado.get(reverse("space_list"), {"space": str(media.pk)})
        assert resposta.context["espaco_selecionado"] == media
        conteudo = resposta.content.decode()
        assert "Escolher horário" in conteudo
        assert 'aria-selected="true"' in conteudo

    def test_selecao_invalida_e_ignorada(self, logado, acervo):
        """Um id inventado não pode gerar erro nem resumo fantasma."""
        for invalido in ["abc", "999999", ""]:
            resposta = logado.get(reverse("space_list"), {"space": invalido})
            assert resposta.status_code == 200
            assert resposta.context["espaco_selecionado"] is None

    def test_selecao_cai_quando_o_filtro_a_exclui(self, logado, acervo):
        """Resumo apontando para cartão ausente é a tela contradizendo a si mesma."""
        pequena = acervo["pequena"]
        resposta = logado.get(reverse("space_list"), {"space": str(pequena.pk), "people": "50"})
        assert pequena.name not in nomes(resposta)
        assert resposta.context["espaco_selecionado"] is None

    def test_continuar_leva_ao_passo_2_com_a_data(self, logado, acervo):
        """A data escolhida no passo 1 não pode ser pedida de novo no passo 2."""
        media = acervo["media"]
        amanha = timezone.localdate() + datetime.timedelta(days=1)
        resposta = logado.get(
            reverse("space_list"),
            {"space": str(media.pk), "date": amanha.isoformat(), "people": "8"},
        )
        conteudo = resposta.content.decode()
        assert f"/spaces/{media.pk}/?date={amanha.isoformat()}" in conteudo
        assert "people=8" in conteudo

    def test_trocar_remove_apenas_a_selecao(self, logado, acervo):
        """O botão "Trocar" não pode desfazer os filtros junto."""
        media = acervo["media"]
        resposta = logado.get(reverse("space_list"), {"space": str(media.pk), "people": "8"})
        query = resposta.context["querystring_sem_espaco"]
        assert "people=8" in query
        assert "space=" not in query

    def test_resumo_traz_a_situacao_do_espaco(self, logado, acervo):
        """O resumo repete a disponibilidade para quem já rolou a tela."""
        media = acervo["media"]
        resposta = logado.get(reverse("space_list"), {"space": str(media.pk)})
        assert resposta.context["espaco_selecionado"].resumo_disponibilidade is not None

    def test_fragmento_htmx_traz_cartoes_e_resumo(self, logado, acervo):
        """Os dois ficam longe um do outro: sem troca fora de banda, um desatualiza."""
        media = acervo["media"]
        resposta = logado.get(
            reverse("space_list"), {"space": str(media.pk)}, HTTP_HX_REQUEST="true"
        )
        conteudo = resposta.content.decode()
        assert "spaces/_space_list_fragment.html" in [t.name for t in resposta.templates]
        assert 'hx-swap-oob="true"' in conteudo
        assert "Escolher horário" in conteudo
        assert "<html" not in conteudo


@pytest.mark.django_db
class TestBuscaComIa:
    """The AI search, which must survive the redesign and hand over what it inferred."""

    def test_continua_disponivel(self, logado, acervo):
        """Exigência explícita do pacote: a busca com IA é preservada."""
        conteudo = logado.get(reverse("space_list")).content.decode()
        assert 'name="ai_query"' in conteudo
        assert "Buscar com IA" in conteudo

    def test_capacidade_inferida_volta_para_o_campo(self, logado, acervo, monkeypatch):
        """A pessoa vê o que a IA entendeu e corrige clicando, não reescrevendo."""
        monkeypatch.setattr(
            "spaces.views.extract_room_search_filters",
            lambda _consulta, _contexto=None: {
                "min_capacity": 8,
                "max_capacity": None,
                "attributes": [],
                "location": "",
                "summary": "sala para 8 pessoas",
                "date": None,
                "start_time": None,
                "duration_minutes": None,
                "avisos": [],
            },
        )
        resposta = logado.get(reverse("space_list"), {"ai_query": "sala para 8 pessoas"})
        assert resposta.context["people"] == 8
        assert nomes(resposta) == {"Sala Média", "Auditório Central"}

    def test_equipamentos_inferidos_voltam_marcados(self, logado, acervo, monkeypatch):
        """Idem para os equipamentos: a interpretação fica visível e ajustável."""
        Attribute.objects.create(name="Projetor")
        monkeypatch.setattr(
            "spaces.views.extract_room_search_filters",
            lambda _consulta, _contexto=None: {
                "min_capacity": None,
                "max_capacity": None,
                "attributes": ["Projetor"],
                "location": "",
                "summary": "sala com projetor",
                "date": None,
                "start_time": None,
                "duration_minutes": None,
                "avisos": [],
            },
        )
        resposta = logado.get(reverse("space_list"), {"ai_query": "sala com projetor"})
        assert resposta.context["selected_attributes"] == ["Projetor"]

    def test_o_que_a_pessoa_digitou_vence_a_inferencia(self, logado, acervo, monkeypatch):
        """Se ela informou o número, a IA não sobrescreve."""
        monkeypatch.setattr(
            "spaces.views.extract_room_search_filters",
            lambda _consulta, _contexto=None: {
                "min_capacity": 8,
                "max_capacity": None,
                "attributes": [],
                "location": "",
                "summary": "sala para 8 pessoas",
                "date": None,
                "start_time": None,
                "duration_minutes": None,
                "avisos": [],
            },
        )
        resposta = logado.get(
            reverse("space_list"), {"ai_query": "sala para 8 pessoas", "people": "150"}
        )
        assert resposta.context["people"] == 150

    def test_formulario_de_filtros_nao_carrega_a_consulta_da_ia(self, logado, acervo):
        """Levá-la junto faria o botão "Buscar" não filtrar nada."""
        conteudo = logado.get(
            reverse("space_list"), {"ai_query": "qualquer coisa"}
        ).content.decode()
        assert conteudo.count('name="ai_query"') == 1


@pytest.mark.django_db
class TestHorarioPedido:
    """The time window, which comes from the AI or from a link."""

    def _ocupa(self, espaco, hora_inicial, horas=1):
        """Book a space for a stretch of today.

        Args:
            espaco: O espaço a ocupar.
            hora_inicial: Hora local de início.
            horas: Duração em horas.
        """
        dono = User.objects.create_user(
            username=f"dono{espaco.pk}{hora_inicial}", password="senha-de-teste-123"
        )
        hoje = timezone.localdate()
        inicio = timezone.make_aware(
            datetime.datetime.combine(hoje, datetime.time(hora_inicial, 0))
        )
        Reservation.objects.create(
            space=espaco,
            user=dono,
            start_time=inicio,
            end_time=inicio + datetime.timedelta(hours=horas),
            status=ReservationStatus.CONFIRMED,
        )

    def test_sem_horario_o_resumo_e_do_dia(self, logado, acervo):
        """O comportamento anterior continua sendo o padrão.

        "Resumo do dia" é o oposto de "resumo do horário": o que precisa valer é
        que o status **não** seja um dos de horário. Exigir ``livre`` prendia o
        teste ao relógio — depois das 16h o dia tem poucos horários restantes e
        o status legítimo passa a ser ``poucos``.
        """
        resposta = logado.get(reverse("space_list"))
        assert resposta.context["horario_pedido"] is None
        resumo = resposta.context["availability_summary"][acervo["media"].pk]
        assert resumo["status"] not in STATUS_DE_HORARIO

    def test_com_horario_o_resumo_responde_ao_horario(self, logado, acervo):
        """Um dia com janela livre às 8h não responde a quem perguntou por 15h."""
        media = acervo["media"]
        self._ocupa(media, 15)
        resposta = logado.get(reverse("space_list"), {"start": "15:00"})
        resumo = resposta.context["availability_summary"]
        assert resumo[media.pk]["status"] == "ocupado_no_horario"
        assert resumo[acervo["pequena"].pk]["status"] == "livre_no_horario"

    def test_rotulo_de_horario_nao_emenda_o_dia(self, logado, acervo):
        """Emendar o dia depois do rótulo de horário daria uma frase sem sentido."""
        conteudo = logado.get(reverse("space_list"), {"start": "15:00"}).content.decode()
        assert "Disponível no horário" in conteudo
        assert "Disponível no horário hoje" not in conteudo

    def test_duracao_estende_o_intervalo_verificado(self, logado, acervo):
        """Pedir duas horas às 14h precisa olhar até as 16h."""
        media = acervo["media"]
        self._ocupa(media, 15)
        livre_curto = logado.get(reverse("space_list"), {"start": "14:00", "duration": "30"})
        ocupado_longo = logado.get(reverse("space_list"), {"start": "14:00", "duration": "120"})
        assert livre_curto.context["availability_summary"][media.pk]["status"] == (
            "livre_no_horario"
        )
        assert ocupado_longo.context["availability_summary"][media.pk]["status"] == (
            "ocupado_no_horario"
        )

    def test_horario_fora_do_expediente_e_ignorado(self, logado, acervo):
        """Filtrar por 22h seria filtrar por um horário que não existe."""
        resposta = logado.get(reverse("space_list"), {"start": "22:00"})
        assert resposta.context["horario_pedido"] is None

    def test_horario_malformado_e_ignorado(self, logado, acervo):
        """A tela não pode cair por causa de um parâmetro digitado errado."""
        resposta = logado.get(reverse("space_list"), {"start": "manhã"})
        assert resposta.status_code == 200
        assert resposta.context["horario_pedido"] is None

    def test_duracao_fora_da_politica_e_ignorada(self, logado, acervo):
        """A regra de duração vale também para o filtro."""
        resposta = logado.get(reverse("space_list"), {"start": "14:00", "duration": "9999"})
        assert resposta.context["horario_pedido"] == datetime.time(14, 0)
        assert resposta.context["duracao_pedida"] is None

    def test_chip_permite_remover_o_horario(self, logado, acervo):
        """Sem campo próprio, a pessoa precisa de um jeito de desfazer."""
        resposta = logado.get(reverse("space_list"), {"start": "14:00", "people": "8"})
        conteudo = resposta.content.decode()
        assert "Filtrando por horário" in conteudo
        assert "Remover filtro de horário" in conteudo
        assert "people=8" in resposta.context["querystring_sem_horario"]
        assert "start=" not in resposta.context["querystring_sem_horario"]

    def test_horario_sobrevive_a_um_filtro(self, logado, acervo):
        """Apertar "Buscar" não pode descartar o horário pedido."""
        conteudo = logado.get(reverse("space_list"), {"start": "14:00"}).content.decode()
        assert 'name="start" value="14:00"' in conteudo


@pytest.mark.django_db
class TestBuscaComIaTemporal:
    """The AI handing over date and time to step 1."""

    def _resposta_da_ia(self, **campos):
        """Build the filter payload the service returns.

        Args:
            **campos: Campos a sobrescrever.

        Returns:
            dict: Payload no formato de ``extract_room_search_filters``.
        """
        base = {
            "min_capacity": None,
            "max_capacity": None,
            "attributes": [],
            "location": "",
            "summary": "entendido",
            "date": None,
            "start_time": None,
            "duration_minutes": None,
            "avisos": [],
        }
        base.update(campos)
        return base

    def test_data_inferida_muda_a_tela(self, logado, acervo, monkeypatch):
        """Quem escreveu "amanhã" acabou de dizer qual data quer."""
        amanha = timezone.localdate() + datetime.timedelta(days=1)
        monkeypatch.setattr(
            "spaces.views.extract_room_search_filters",
            lambda _c, _ctx=None: self._resposta_da_ia(date=amanha),
        )
        resposta = logado.get(reverse("space_list"), {"ai_query": "sala amanhã"})
        assert resposta.context["selected_date"] == amanha

    def test_data_inferida_vence_o_campo_escondido(self, logado, acervo, monkeypatch):
        """O formulário leva a data da tela; a frase da pessoa é mais recente."""
        depois = timezone.localdate() + datetime.timedelta(days=3)
        monkeypatch.setattr(
            "spaces.views.extract_room_search_filters",
            lambda _c, _ctx=None: self._resposta_da_ia(date=depois),
        )
        resposta = logado.get(
            reverse("space_list"),
            {"ai_query": "daqui a três dias", "date": timezone.localdate().isoformat()},
        )
        assert resposta.context["selected_date"] == depois

    def test_horario_inferido_muda_o_rotulo(self, logado, acervo, monkeypatch):
        """O cartão passa a responder ao horário pedido."""
        monkeypatch.setattr(
            "spaces.views.extract_room_search_filters",
            lambda _c, _ctx=None: self._resposta_da_ia(start_time=datetime.time(15, 0)),
        )
        resposta = logado.get(reverse("space_list"), {"ai_query": "sala às 15h"})
        assert resposta.context["horario_pedido"] == datetime.time(15, 0)
        assert "Disponível no horário" in resposta.content.decode()

    def test_avisos_aparecem_na_tela(self, logado, acervo, monkeypatch):
        """O que a regra recusou é dito em voz alta, não descartado em silêncio."""
        monkeypatch.setattr(
            "spaces.views.extract_room_search_filters",
            lambda _c, _ctx=None: self._resposta_da_ia(
                avisos=["A data pedida já passou; mostrando hoje."]
            ),
        )
        resposta = logado.get(reverse("space_list"), {"ai_query": "sala ontem"})
        assert "A data pedida já passou" in resposta.content.decode()

    def test_recebe_o_contexto_temporal(self, logado, acervo, monkeypatch):
        """Sem contexto, o serviço nem pergunta por data ao modelo."""
        recebidos = {}

        def espiao(consulta, contexto=None):
            recebidos["contexto"] = contexto
            return self._resposta_da_ia()

        monkeypatch.setattr("spaces.views.extract_room_search_filters", espiao)
        logado.get(reverse("space_list"), {"ai_query": "sala"})
        assert recebidos["contexto"]["hoje_date"] == timezone.localdate()
        assert recebidos["contexto"]["abertura"] == "08:00"


@pytest.mark.django_db
class TestCartao:
    """The card anatomy the V2 reference asks for."""

    def test_mostra_capacidade_em_linguagem_humana(self, logado, acervo):
        """O cartão diz "Até 10 pessoas" no lugar de "10 lugares"."""
        conteudo = logado.get(reverse("space_list")).content.decode()
        assert "Até 10 pessoas" in conteudo
        assert "lugares" not in conteudo

    def test_mostra_o_tipo(self, logado, acervo):
        """O tipo dá contexto sem precisar abrir o detalhe."""
        assert "Sala de Reunião" in logado.get(reverse("space_list")).content.decode()

    def test_mostra_o_proximo_horario_quando_existe(self, logado, acervo):
        """A referência V2 pede o próximo horário no cartão.

        A data é a do próximo dia **aberto**, e não a de amanhã, porque o
        "quando existe" do nome precisa ser verdade em dois eixos: pedindo hoje,
        o resultado depende da hora em que a suíte roda — depois do fechamento
        não existe próximo horário nenhum —; e pedindo amanhã, duas vezes por
        semana cai num dia em que o prédio não abre. Os dois casos têm teste
        próprio logo abaixo.
        """
        dia = proximo_dia_aberto(timezone.localdate() + datetime.timedelta(days=1))
        conteudo = logado.get(reverse("space_list"), {"date": dia.isoformat()}).content.decode()
        assert "Próximo horário" in conteudo

    def test_dia_fechado_diz_que_esta_fechado(self, logado, acervo):
        """Prédio fechado não é prédio lotado.

        Sem estado próprio, o domingo caía em "Sem horários" — que descreve uma
        agenda cheia e manda a pessoa procurar outro espaço no mesmo domingo,
        onde também não vai achar nada.
        """
        politica = BookingPolicy.carregar()
        # Este teste **é** sobre dia da semana, então declara os dias que
        # assume em vez de herdá-los da fixture que abre a semana inteira.
        politica.opens_saturday = False
        politica.opens_sunday = False
        politica.save(update_fields=["opens_saturday", "opens_sunday"])
        hoje = timezone.localdate()
        fechado = next(
            hoje + datetime.timedelta(days=adiante)
            for adiante in range(1, 15)
            if not politica.abre_em(hoje + datetime.timedelta(days=adiante))
        )
        conteudo = logado.get(reverse("space_list"), {"date": fechado.isoformat()}).content.decode()
        assert "Fechado" in conteudo
        assert "Sem horários" not in conteudo

    def test_dia_encerrado_nao_promete_proximo_horario(self, acervo):
        """Depois do fechamento não há o que oferecer, e o resumo não inventa.

        Este é o estado em que a tela fica todo fim de tarde, e até aqui nenhum
        teste o exercitava — a suíte só era executada em horário comercial. O
        instante entra por ``agora``, que ``resumo_em_lote`` aceita justamente
        para que a resposta não dependa da hora em que o teste roda.
        """
        media = acervo["media"]
        hoje = timezone.localdate()
        politica = BookingPolicy.carregar()

        antes_de_abrir = timezone.make_aware(
            datetime.datetime.combine(hoje, politica.opening_time)
        ) - datetime.timedelta(hours=1)
        depois_de_fechar = timezone.make_aware(
            datetime.datetime.combine(hoje, politica.closing_time)
        ) + datetime.timedelta(minutes=1)

        de_manha = resumo_em_lote([media], hoje, agora=antes_de_abrir)[media.pk]
        assert de_manha["proxima_janela"] is not None
        assert de_manha["slots_livres"] > 0

        a_noite = resumo_em_lote([media], hoje, agora=depois_de_fechar)[media.pk]
        assert a_noite["proxima_janela"] is None
        assert a_noite["slots_livres"] == 0
        assert a_noite["status"] == STATUS_ENCERRADO

    def test_situacao_nao_deriva_de_is_active(self, logado, acervo, django_user_model):
        """Um espaço ativo pode estar lotado; são eixos independentes."""
        media = acervo["media"]
        dono = django_user_model.objects.create_user(
            username="outro", password="senha-de-teste-123"
        )
        politica = BookingPolicy.carregar()
        hoje = timezone.localdate()
        Reservation.objects.create(
            space=media,
            user=dono,
            start_time=timezone.make_aware(datetime.datetime.combine(hoje, politica.opening_time)),
            end_time=timezone.make_aware(datetime.datetime.combine(hoje, politica.closing_time)),
            status=ReservationStatus.CONFIRMED,
        )
        resposta = logado.get(reverse("space_list"))
        assert media.name in nomes(resposta)
        assert resposta.context["availability_summary"][media.pk]["status"] != "livre"

    def test_lista_e_um_listbox_acessivel(self, logado, acervo):
        """Quem não vê a borda precisa saber o que está selecionado."""
        media = acervo["media"]
        conteudo = logado.get(reverse("space_list"), {"space": str(media.pk)}).content.decode()
        assert 'role="listbox"' in conteudo
        assert 'role="option"' in conteudo
        assert 'aria-selected="true"' in conteudo
        assert 'aria-selected="false"' in conteudo


@pytest.mark.django_db
class TestFiltrosAvancados:
    """The collapsed advanced filters."""

    def test_ficam_recolhidos_por_padrao(self, logado, acervo):
        """São a exceção, não o caminho comum."""
        conteudo = logado.get(reverse("space_list")).content.decode()
        assert "Mais filtros" in conteudo
        assert conteudo.count("<details") >= 1

    def test_abrem_quando_ha_filtro_ativo(self, logado, acervo):
        """Filtro aplicado e invisível seria um resultado inexplicável."""
        resposta = logado.get(reverse("space_list"), {"location": "Térreo"})
        assert resposta.context["filtros_avancados_ativos"] == 1
        assert "Auditório Central" in resposta.content.decode()

    def test_contam_localizacao_e_equipamentos(self, logado, acervo):
        """O contador diz quantos filtros estão escondidos."""
        Attribute.objects.create(name="TV")
        media = acervo["media"]
        SpaceAttribute.objects.create(space=media, attribute=Attribute.objects.get(name="TV"))
        resposta = logado.get(reverse("space_list"), {"location": "2º", "attributes": "TV"})
        assert resposta.context["filtros_avancados_ativos"] == 2
        assert nomes(resposta) == {"Sala Média"}


@pytest.mark.django_db
class TestBarraDeSelecao:
    """The step 1 selection bar, which must stay pinned while the page scrolls."""

    def test_a_barra_e_o_proprio_elemento_pregado(self, logado, acervo):
        """O ``sticky`` precisa estar no elemento de id, não num filho.

        Antes o id ficava num ``<div>`` que envolvia o elemento ``sticky``.
        Como o invólucro tinha exatamente a altura do filho, o
        ``position: sticky`` não tinha margem para deslocar e a barra nunca
        colava — um defeito que nenhum teste via, porque o HTML estava lá.
        """
        media = acervo["media"]
        conteudo = logado.get(reverse("space_list"), {"space": str(media.pk)}).content.decode()
        elemento = conteudo.split('id="resumo-selecao"')[1].split(">")[0]
        assert "sticky" in elemento
        assert "bottom-0" in elemento

    def test_o_id_aparece_uma_vez_so(self, logado, acervo):
        """Dois ids iguais fazem o HTMX trocar o elemento errado."""
        conteudo = logado.get(
            reverse("space_list"), {"space": str(acervo["media"].pk)}
        ).content.decode()
        assert conteudo.count('id="resumo-selecao"') == 1

    def test_a_resposta_htmx_traz_o_mesmo_elemento(self, logado, acervo):
        """Se as classes divergirem, a barra para de colar depois do primeiro clique."""
        media = acervo["media"]
        resposta = logado.get(
            reverse("space_list"),
            {"space": str(media.pk)},
            headers={"HX-Request": "true"},
        )
        fragmento = resposta.content.decode()
        elemento = fragmento.split('id="resumo-selecao"')[1].split(">")[0]
        assert "hx-swap-oob" in elemento
        assert "sticky" in elemento
        assert "bottom-0" in elemento

    def test_sem_selecao_a_barra_fica_vazia_mas_existe(self, logado, acervo):
        """O alvo do swap precisa existir antes do primeiro clique."""
        conteudo = logado.get(reverse("space_list")).content.decode()
        assert 'id="resumo-selecao"' in conteudo
        assert "Escolher horário" not in conteudo
