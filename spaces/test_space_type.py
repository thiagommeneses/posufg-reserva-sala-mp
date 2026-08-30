"""Tests for space types.

O risco desta fase não é a tabela — é a aba mentir. Uma aba "Auditório" que
lista uma sala de reunião, ou um ícone que não renderiza nada, chega ao usuário
sem erro nenhum no log. Por isso os testes aqui cobrem, além do CRUD: o
catálogo de ícones batendo com o partial que os desenha, a heurística de
backfill recusando-se a chutar, e as abas preservando o resto da busca.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from spaces.management.commands.sugerir_tipos_de_espaco import sugerir_slug
from spaces.models import Space, SpaceType
from spaces.validators import (
    CODIGO_ICONE,
    ICONES_DISPONIVEIS,
    validar_nome_de_icone,
)

User = get_user_model()

CAMINHO_DO_PARTIAL = "templates/partials/_icon.html"


@pytest.fixture
def admin_client_logado(client, db):
    """Return a client logged in as a staff user.

    Args:
        client: Cliente de teste do Django.
        db: Fixture do pytest-django que habilita o banco.

    Returns:
        Client: Cliente autenticado como staff.
    """
    User.objects.create_user(username="staff", password="senha-de-teste-123", is_staff=True)
    client.login(username="staff", password="senha-de-teste-123")
    return client


class TestCatalogoDeIcones:
    """The allow-list must match the partial that draws the icons."""

    def test_todo_icone_da_lista_existe_no_partial(self, settings):
        """Um nome aceito que o partial não desenha renderiza vazio na tela."""
        caminho = settings.BASE_DIR / CAMINHO_DO_PARTIAL
        conteudo = caminho.read_text(encoding="utf-8")
        desenhados = set(re.findall(r'name == "([a-z0-9-]+)"', conteudo))
        faltando = ICONES_DISPONIVEIS - desenhados
        assert not faltando, f"Nomes aceitos que o partial não desenha: {sorted(faltando)}"

    def test_todo_icone_do_partial_esta_na_lista(self, settings):
        """Um ícone existente fora da lista fica indisponível para o administrador."""
        caminho = settings.BASE_DIR / CAMINHO_DO_PARTIAL
        conteudo = caminho.read_text(encoding="utf-8")
        desenhados = set(re.findall(r'name == "([a-z0-9-]+)"', conteudo))
        sobrando = desenhados - ICONES_DISPONIVEIS
        assert not sobrando, f"Ícones do partial fora da lista aceita: {sorted(sobrando)}"

    def test_valida_nome_conhecido(self):
        """Um nome do catálogo passa."""
        validar_nome_de_icone("calendar")

    def test_recusa_nome_desconhecido(self):
        """Um nome fora do catálogo é recusado com código próprio."""
        with pytest.raises(ValidationError) as exc:
            validar_nome_de_icone("foguete")
        assert exc.value.code == CODIGO_ICONE

    def test_aceita_vazio(self):
        """Tipo sem ícone é legítimo — o campo é opcional."""
        validar_nome_de_icone("")


@pytest.mark.django_db
class TestModelo:
    """The model itself, including what the migration seeded."""

    def test_catalogo_inicial_existe(self):
        """A data migration precisa deixar o catálogo pronto num banco novo."""
        slugs = set(SpaceType.objects.values_list("slug", flat=True))
        assert {"sala-de-reuniao", "auditorio", "espaco-compartilhado"} <= slugs

    def test_catalogo_inicial_usa_apenas_icones_validos(self):
        """Os ícones do seed precisam existir de verdade."""
        for tipo in SpaceType.objects.all():
            assert tipo.icon_name in ICONES_DISPONIVEIS

    def test_ordenacao_por_sort_order(self):
        """As abas seguem sort_order, não a ordem de criação."""
        SpaceType.objects.create(name="Zebra", slug="zebra", sort_order=1)
        assert SpaceType.objects.first().name == "Zebra"

    def test_str_retorna_o_nome(self):
        """O nome é o que aparece em selects e logs."""
        assert str(SpaceType.objects.get(slug="auditorio")) == "Auditório"

    def test_excluir_o_tipo_nao_exclui_o_espaco(self):
        """SET_NULL: apagar uma categoria não pode apagar as salas dela."""
        tipo = SpaceType.objects.get(slug="auditorio")
        espaco = Space.objects.create(
            name="Auditório Central", capacity=100, location="Térreo", space_type=tipo
        )
        tipo.delete()
        espaco.refresh_from_db()
        assert espaco.pk is not None
        assert espaco.space_type is None

    def test_espaco_pode_ficar_sem_tipo(self):
        """O acervo atual não tem tipo; o campo precisa aceitar isso."""
        espaco = Space.objects.create(name="Sala Focus", capacity=4, location="2º andar")
        assert espaco.space_type is None


class TestHeuristicaDeSugestao:
    """The backfill heuristic must refuse to guess."""

    @pytest.mark.parametrize(
        ("nome", "esperado"),
        [
            ("Sala de Reunião Alfa", "sala-de-reuniao"),
            ("SALA DE REUNIAO BETA", "sala-de-reuniao"),
            ("Auditório Principal", "auditorio"),
            ("Sala de Treinamento 1", "sala-de-treinamento"),
            ("Sala de Capacitação", "sala-de-treinamento"),
            ("Espaço Compartilhado Norte", "espaco-compartilhado"),
            ("Coworking Térreo", "espaco-compartilhado"),
            ("Sala Executiva do PGJ", "sala-executiva"),
        ],
    )
    def test_classifica_nomes_evidentes(self, nome, esperado):
        """Nome que diz o que é pode ser classificado sem risco."""
        assert sugerir_slug(nome) == esperado

    @pytest.mark.parametrize("nome", ["Sala Focus", "Espaço 7", "Ala Verde", "Anexo II"])
    def test_nao_chuta_nomes_ambiguos(self, nome):
        """Sem evidência no nome, a decisão fica com o administrador."""
        assert sugerir_slug(nome) is None

    def test_auditorio_vence_reuniao_quando_ambos_aparecem(self):
        """A ordem das regras importa: a mais específica primeiro."""
        assert sugerir_slug("Auditório para reunião ampliada") == "auditorio"


@pytest.mark.django_db
class TestComandoDeSugestao:
    """The command proposes by default and only writes with --aplicar."""

    def _espacos(self):
        """Create one classifiable space and one ambiguous one."""
        Space.objects.create(name="Sala de Reunião Alfa", capacity=8, location="1º andar")
        Space.objects.create(name="Sala Focus", capacity=4, location="2º andar")

    def test_dry_run_nao_grava(self, capsys):
        """Sem --aplicar nada muda no banco, por mais óbvia que seja a sugestão."""
        self._espacos()
        call_command("sugerir_tipos_de_espaco")
        assert Space.objects.filter(space_type__isnull=True).count() == 2
        assert "Nada foi gravado" in capsys.readouterr().out

    def test_dry_run_mostra_a_proposta(self, capsys):
        """A proposta precisa ser legível antes de virar escrita."""
        self._espacos()
        call_command("sugerir_tipos_de_espaco")
        saida = capsys.readouterr().out
        assert "Sala de Reunião Alfa" in saida
        assert "Sala de Reunião" in saida
        assert "Sala Focus" in saida

    def test_aplicar_grava_apenas_o_que_foi_proposto(self, capsys):
        """O ambíguo continua sem tipo mesmo depois de --aplicar."""
        self._espacos()
        call_command("sugerir_tipos_de_espaco", "--aplicar")
        alfa = Space.objects.get(name="Sala de Reunião Alfa")
        focus = Space.objects.get(name="Sala Focus")
        assert alfa.space_type.slug == "sala-de-reuniao"
        assert focus.space_type is None

    def test_nao_reclassifica_quem_ja_tem_tipo(self):
        """Uma classificação feita por humano não pode ser sobrescrita."""
        outro = SpaceType.objects.get(slug="outro")
        espaco = Space.objects.create(
            name="Sala de Reunião Alfa", capacity=8, location="1º andar", space_type=outro
        )
        call_command("sugerir_tipos_de_espaco", "--aplicar")
        espaco.refresh_from_db()
        assert espaco.space_type == outro

    def test_avisa_quando_nao_ha_o_que_fazer(self, capsys):
        """Sem espaços pendentes o comando diz isso e sai."""
        call_command("sugerir_tipos_de_espaco")
        assert "Todos os espaços já têm tipo." in capsys.readouterr().out


@pytest.mark.django_db
class TestAbasNaListaDeEspacos:
    """The tabs on the booking flow, step 1."""

    @pytest.fixture(autouse=True)
    def _dados(self, client):
        """Create one space of each of two types plus one untyped space."""
        self.reuniao = SpaceType.objects.get(slug="sala-de-reuniao")
        self.auditorio = SpaceType.objects.get(slug="auditorio")
        self.sala = Space.objects.create(
            name="Sala Alfa", capacity=8, location="1º andar", space_type=self.reuniao
        )
        self.aud = Space.objects.create(
            name="Auditório Central", capacity=200, location="Térreo", space_type=self.auditorio
        )
        self.sem_tipo = Space.objects.create(name="Sala Focus", capacity=4, location="2º andar")
        User.objects.create_user(username="user", password="senha-de-teste-123")
        client.login(username="user", password="senha-de-teste-123")
        self.client = client

    def test_sem_filtro_lista_tudo(self):
        """A aba "Todos" não esconde espaço nenhum, inclusive os sem tipo."""
        resposta = self.client.get(reverse("space_list"))
        nomes = {espaco.name for espaco in resposta.context["spaces"]}
        assert nomes == {"Sala Alfa", "Auditório Central", "Sala Focus"}

    def test_filtra_por_tipo(self):
        """?type= restringe a lista à categoria escolhida."""
        resposta = self.client.get(reverse("space_list"), {"type": "auditorio"})
        nomes = {espaco.name for espaco in resposta.context["spaces"]}
        assert nomes == {"Auditório Central"}

    def test_tipo_inexistente_lista_vazia(self):
        """Um slug inventado não pode cair silenciosamente na lista completa."""
        resposta = self.client.get(reverse("space_list"), {"type": "nao-existe"})
        assert list(resposta.context["spaces"]) == []

    def test_marca_a_aba_ativa(self):
        """A aba corrente precisa ser anunciada, não só pintada."""
        resposta = self.client.get(reverse("space_list"), {"type": "auditorio"})
        assert resposta.context["selected_type"] == "auditorio"
        assert 'aria-current="page"' in resposta.content.decode()

    def test_abas_preservam_os_demais_parametros(self):
        """Trocar de aba não pode apagar filtros que o usuário já preencheu."""
        resposta = self.client.get(
            reverse("space_list"), {"type": "auditorio", "min_capacity": "10"}
        )
        query = resposta.context["query_sem_tipo"]
        assert "min_capacity=10" in query
        assert "type=" not in query
        assert query.endswith("&")

    def test_query_sem_tipo_vazia_nao_deixa_e_comercial_solto(self):
        """Sem outros parâmetros a URL da aba fica limpa."""
        resposta = self.client.get(reverse("space_list"))
        assert resposta.context["query_sem_tipo"] == ""

    def test_abas_so_mostram_tipos_ativos(self):
        """Um tipo desativado sai das abas sem virar link morto."""
        self.auditorio.is_active = False
        self.auditorio.save()
        resposta = self.client.get(reverse("space_list"))
        slugs = {tipo.slug for tipo in resposta.context["space_types"]}
        assert "auditorio" not in slugs
        assert "sala-de-reuniao" in slugs

    def test_tipo_aparece_no_card(self):
        """O rótulo dá contexto ao card sem precisar abrir o detalhe."""
        resposta = self.client.get(reverse("space_list"), {"type": "auditorio"})
        assert "Auditório" in resposta.content.decode()

    def test_filtro_de_tipo_convive_com_capacidade(self):
        """Os dois filtros se somam, não se substituem."""
        Space.objects.create(
            name="Auditório Pequeno", capacity=30, location="Térreo", space_type=self.auditorio
        )
        resposta = self.client.get(
            reverse("space_list"), {"type": "auditorio", "min_capacity": "100"}
        )
        nomes = {espaco.name for espaco in resposta.context["spaces"]}
        assert nomes == {"Auditório Central"}


@pytest.mark.django_db
class TestAdminDeTipos:
    """The admin CRUD for types."""

    def test_lista_exige_staff(self, client):
        """Usuário comum não administra o catálogo."""
        User.objects.create_user(username="comum", password="senha-de-teste-123")
        client.login(username="comum", password="senha-de-teste-123")
        resposta = client.get(reverse("admin_dashboard:space_type_list"))
        assert resposta.status_code == 403

    def test_lista_mostra_a_contagem_de_espacos(self, admin_client_logado):
        """Saber quantos espaços usam o tipo evita exclusão às cegas."""
        tipo = SpaceType.objects.get(slug="auditorio")
        Space.objects.create(
            name="Auditório Central", capacity=200, location="Térreo", space_type=tipo
        )
        resposta = admin_client_logado.get(reverse("admin_dashboard:space_type_list"))
        listados = {t.slug: t.total_espacos for t in resposta.context["space_types"]}
        assert listados["auditorio"] == 1
        assert listados["sala-de-reuniao"] == 0

    def test_cria_tipo_com_slug_automatico(self, admin_client_logado):
        """Deixar o slug em branco não pode dar erro de formulário."""
        resposta = admin_client_logado.post(
            reverse("admin_dashboard:space_type_create"),
            {"name": "Sala de Videoconferência", "slug": "", "icon_name": "users", "sort_order": 5},
        )
        assert resposta.status_code == 302
        assert SpaceType.objects.filter(slug="sala-de-videoconferencia").exists()

    def test_recusa_icone_fora_do_catalogo(self, admin_client_logado):
        """O formulário precisa barrar o que a tela não sabe desenhar."""
        resposta = admin_client_logado.post(
            reverse("admin_dashboard:space_type_create"),
            {"name": "Sala Foguete", "slug": "", "icon_name": "foguete", "sort_order": 5},
        )
        assert resposta.status_code == 200
        assert "icon_name" in resposta.context["form"].errors
        assert not SpaceType.objects.filter(name="Sala Foguete").exists()

    def test_edita_tipo(self, admin_client_logado):
        """Renomear e reordenar é operação de administrador, não de migration."""
        tipo = SpaceType.objects.get(slug="outro")
        resposta = admin_client_logado.post(
            reverse("admin_dashboard:space_type_update", args=[tipo.pk]),
            {"name": "Outros espaços", "slug": tipo.slug, "icon_name": "grid", "sort_order": 99},
        )
        assert resposta.status_code == 302
        tipo.refresh_from_db()
        assert tipo.name == "Outros espaços"
        assert tipo.sort_order == 99

    def test_desativar_tipo_nao_apaga_a_classificacao(self, admin_client_logado):
        """Desativar tira das abas; não pode desclassificar os espaços."""
        tipo = SpaceType.objects.get(slug="auditorio")
        espaco = Space.objects.create(
            name="Auditório Central", capacity=200, location="Térreo", space_type=tipo
        )
        admin_client_logado.post(
            reverse("admin_dashboard:space_type_update", args=[tipo.pk]),
            {"name": tipo.name, "slug": tipo.slug, "icon_name": tipo.icon_name, "sort_order": 20},
        )
        espaco.refresh_from_db()
        assert espaco.space_type == tipo

    def test_formulario_de_espaco_aceita_tipo(self, admin_client_logado):
        """O tipo precisa ser editável junto com o resto do espaço."""
        tipo = SpaceType.objects.get(slug="sala-de-reuniao")
        resposta = admin_client_logado.post(
            reverse("admin_dashboard:space_create"),
            {
                "name": "Sala Beta",
                "capacity": 6,
                "location": "3º andar",
                "space_type": tipo.pk,
                "is_active": "on",
            },
        )
        assert resposta.status_code == 302
        assert Space.objects.get(name="Sala Beta").space_type == tipo

    def test_lista_de_espacos_mostra_o_tipo(self, admin_client_logado):
        """A coluna evita abrir cada espaço para saber a categoria."""
        tipo = SpaceType.objects.get(slug="auditorio")
        Space.objects.create(
            name="Auditório Central", capacity=200, location="Térreo", space_type=tipo
        )
        resposta = admin_client_logado.get(reverse("admin_dashboard:space_list"))
        conteudo = resposta.content.decode()
        assert "Tipo" in conteudo
        assert "Auditório" in conteudo


@pytest.mark.django_db
class TestApi:
    """The REST contract for the new field."""

    @pytest.fixture
    def api(self):
        """Return an authenticated API client."""
        cliente = APIClient()
        cliente.force_authenticate(
            user=User.objects.create_user(username="api", password="senha-de-teste-123")
        )
        return cliente

    def test_serializa_slug_e_nome(self, api):
        """O consumidor precisa do slug para filtrar e do nome para exibir."""
        tipo = SpaceType.objects.get(slug="auditorio")
        espaco = Space.objects.create(
            name="Auditório Central", capacity=200, location="Térreo", space_type=tipo
        )
        dados = api.get(f"/api/v1/spaces/{espaco.pk}/").json()
        assert dados["space_type"] == "auditorio"
        assert dados["space_type_name"] == "Auditório"

    def test_espaco_sem_tipo_serializa_nulo(self, api):
        """Sem tipo o campo é nulo — não pode explodir nem sumir do payload."""
        espaco = Space.objects.create(name="Sala Focus", capacity=4, location="2º andar")
        dados = api.get(f"/api/v1/spaces/{espaco.pk}/").json()
        assert dados["space_type"] is None
        assert dados["space_type_name"] is None

    def test_criar_espaco_pela_api_continua_funcionando(self, db):
        """Os campos novos são de leitura: não podem quebrar o POST existente."""
        cliente = APIClient()
        cliente.force_authenticate(
            user=User.objects.create_user(
                username="adm", password="senha-de-teste-123", is_staff=True
            )
        )
        resposta = cliente.post(
            "/api/v1/spaces/",
            {"name": "Sala Nova", "capacity": 10, "location": "4º andar"},
        )
        assert resposta.status_code == 201
        assert resposta.json()["space_type_name"] is None

    def test_filtra_por_tipo(self, api):
        """?space_type= usa o slug, igual às abas da interface."""
        tipo = SpaceType.objects.get(slug="auditorio")
        Space.objects.create(
            name="Auditório Central", capacity=200, location="Térreo", space_type=tipo
        )
        Space.objects.create(name="Sala Focus", capacity=4, location="2º andar")
        dados = api.get("/api/v1/spaces/", {"space_type": "auditorio"}).json()
        resultados = dados["results"] if isinstance(dados, dict) else dados
        assert [item["name"] for item in resultados] == ["Auditório Central"]
