"""Tests for the extended equipment attributes.

O risco desta fase é a tela esconder um filtro que o usuário marcou, ou destacar
equipamento por invenção em vez de por evidência. Os testes cobrem os dois: a
degradação quando não há destaque nenhum, a seção que se abre sozinha quando há
seleção escondida, e o comando que propõe destaques a partir do acervo real.
"""

import importlib
import re

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from spaces.management.commands.sugerir_atributos_em_destaque import _utilidade
from spaces.models import Attribute, Space, SpaceAttribute
from spaces.validators import ICONES_DISPONIVEIS

User = get_user_model()

#: O nome do módulo começa com dígito, então não dá para importar com ``from``.
MIGRATION_0007 = importlib.import_module("spaces.migrations.0007_atributos_icones")

NOMES_PADRAO = [
    "Ar-condicionado",
    "Projetor",
    "Quadro branco",
    "TV",
    "Videoconferência",
    "Webcam",
    "Wi-Fi",
]


@pytest.fixture
def logado(client, db):
    """Return a client logged in as a regular user."""
    User.objects.create_user(username="user", password="senha-de-teste-123")
    client.login(username="user", password="senha-de-teste-123")
    return client


@pytest.fixture
def staff(client, db):
    """Return a client logged in as staff."""
    User.objects.create_user(username="staff", password="senha-de-teste-123", is_staff=True)
    client.login(username="staff", password="senha-de-teste-123")
    return client


@pytest.fixture
def catalogo(db):
    """Create the seven standard attributes and return them by name."""
    return {nome: Attribute.objects.create(name=nome) for nome in NOMES_PADRAO}


def com_atributos(espaco, atributos):
    """Link a space to several attributes.

    Args:
        espaco: O espaço.
        atributos: Os atributos a vincular.
    """
    for atributo in atributos:
        SpaceAttribute.objects.create(space=espaco, attribute=atributo)


@pytest.mark.django_db
class TestModelo:
    """The new fields on Attribute."""

    def test_campos_novos_tem_padrao_neutro(self):
        """Um atributo criado sem nada não altera a tela em nada."""
        atributo = Attribute.objects.create(name="Lousa digital")
        assert atributo.is_featured is False
        assert atributo.sort_order == 0
        assert atributo.icon_name == ""
        assert atributo.category == ""

    def test_ordenacao_por_sort_order_depois_nome(self):
        """Sort_order manda; empate resolve alfabeticamente."""
        Attribute.objects.create(name="Zebra", sort_order=1)
        Attribute.objects.create(name="Alfa", sort_order=5)
        Attribute.objects.create(name="Beta", sort_order=5)
        assert [a.name for a in Attribute.objects.all()] == ["Zebra", "Alfa", "Beta"]

    def test_recusa_icone_fora_do_catalogo(self):
        """A mesma lista de ícones vale para tipo de espaço e equipamento."""
        atributo = Attribute(name="Teleporte", icon_name="foguete")
        with pytest.raises(Exception, match="Ícone desconhecido"):
            atributo.full_clean()

    def test_migration_so_usa_icones_que_existem(self):
        """Um ícone inválido na migration apareceria como espaço em branco na tela."""
        assert set(MIGRATION_0007.ICONES) == set(NOMES_PADRAO)
        for icone in MIGRATION_0007.ICONES.values():
            assert icone in ICONES_DISPONIVEIS

    def test_migration_nao_sobrescreve_escolha_humana(self):
        """Um ícone já definido por alguém não pode ser trocado pela migration."""
        Attribute.objects.create(name="Wi-Fi", icon_name="grid")
        MIGRATION_0007.aplicar_icones(apps, None)
        assert Attribute.objects.get(name="Wi-Fi").icon_name == "grid"

    def test_migration_preenche_quem_esta_sem_icone(self):
        """O caso normal: o atributo chega sem ícone e ganha o seu."""
        Attribute.objects.create(name="Wi-Fi")
        MIGRATION_0007.aplicar_icones(apps, None)
        assert Attribute.objects.get(name="Wi-Fi").icon_name == "wifi"

    def test_migration_reverte_apenas_o_que_definiu(self):
        """A reversão não pode apagar o ícone que um humano escolheu."""
        Attribute.objects.create(name="Wi-Fi", icon_name="wifi")
        Attribute.objects.create(name="TV", icon_name="grid")
        MIGRATION_0007.remover_icones(apps, None)
        assert Attribute.objects.get(name="Wi-Fi").icon_name == ""
        assert Attribute.objects.get(name="TV").icon_name == "grid"


@pytest.mark.django_db
class TestUtilidade:
    """The heuristic behind the suggestion command."""

    def test_equipamento_que_todos_tem_nao_filtra(self):
        """Se todo espaço tem, marcar o filtro não muda a lista."""
        assert _utilidade(10, 10) == 0

    def test_equipamento_que_ninguem_tem_nao_filtra(self):
        """Idem no outro extremo."""
        assert _utilidade(0, 10) == 0

    def test_metade_e_o_ponto_de_maior_utilidade(self):
        """Um equipamento que divide o acervo ao meio é o que mais informa."""
        assert _utilidade(5, 10) == 1

    def test_sem_espacos_nao_divide_por_zero(self):
        """Base vazia não pode explodir."""
        assert _utilidade(0, 0) == 0


@pytest.mark.django_db
class TestComandoDeDestaque:
    """The command proposes from real data and only writes with --aplicar."""

    @pytest.fixture
    def acervo(self, catalogo):
        """Create four spaces so the attributes differ in usefulness."""
        espacos = [
            Space.objects.create(name=f"Sala {i}", capacity=6, location="1º andar")
            for i in range(4)
        ]
        # TV em metade dos espaços: o mais útil como filtro.
        com_atributos(espacos[0], [catalogo["TV"], catalogo["Wi-Fi"]])
        com_atributos(espacos[1], [catalogo["TV"], catalogo["Wi-Fi"]])
        com_atributos(espacos[2], [catalogo["Wi-Fi"]])
        # Wi-Fi em todos: não separa nada.
        com_atributos(espacos[3], [catalogo["Wi-Fi"]])
        return espacos

    def test_dry_run_nao_grava(self, acervo, capsys):
        """Sem --aplicar o banco não muda."""
        call_command("sugerir_atributos_em_destaque")
        assert not Attribute.objects.filter(is_featured=True).exists()
        assert "Nada foi gravado" in capsys.readouterr().out

    def test_ranking_poe_o_mais_discriminante_primeiro(self, acervo, capsys):
        """TV, em metade dos espaços, precisa vir antes do Wi-Fi, que está em todos."""
        call_command("sugerir_atributos_em_destaque")
        saida = capsys.readouterr().out
        assert saida.index("TV") < saida.index("Wi-Fi")

    def test_aplicar_marca_destaque_e_ordem(self, acervo):
        """A gravação define destaque e ordem de exibição."""
        call_command("sugerir_atributos_em_destaque", "--aplicar", "--quantidade", "1")
        tv = Attribute.objects.get(name="TV")
        assert tv.is_featured is True
        assert tv.sort_order == 10
        assert Attribute.objects.filter(is_featured=True).count() == 1

    def test_aplicar_desmarca_quem_saiu(self, acervo):
        """Rodar de novo não pode acumular destaques antigos."""
        Attribute.objects.filter(name="Quadro branco").update(is_featured=True)
        call_command("sugerir_atributos_em_destaque", "--aplicar", "--quantidade", "1")
        assert Attribute.objects.get(name="Quadro branco").is_featured is False

    def test_nao_destaca_equipamento_que_nao_separa_nada(self, catalogo):
        """Sem nenhum vínculo, nada tem utilidade — e nada é destacado."""
        Space.objects.create(name="Sala Única", capacity=4, location="1º andar")
        call_command("sugerir_atributos_em_destaque", "--aplicar")
        assert not Attribute.objects.filter(is_featured=True).exists()

    def test_avisa_quando_nao_ha_equipamento(self, db, capsys):
        """Base sem equipamento nenhum não pode dar erro."""
        call_command("sugerir_atributos_em_destaque")
        assert "Nenhum equipamento cadastrado." in capsys.readouterr().out


@pytest.mark.django_db
class TestPainelDeFiltros:
    """The filter panel on step 1."""

    def test_sem_destaque_lista_todos(self, logado, catalogo):
        """Estado inicial: a tela funciona como antes desta fase."""
        resposta = logado.get(reverse("space_list"))
        assert resposta.context["featured_attributes"] == []
        conteudo = resposta.content.decode()
        for nome in NOMES_PADRAO:
            assert nome in conteudo
        assert "Mais equipamentos" not in conteudo

    def test_com_destaque_separa_as_duas_listas(self, logado, catalogo):
        """Os destacados ficam visíveis; o resto vai para trás do resumo."""
        Attribute.objects.filter(name__in=["TV", "Wi-Fi"]).update(is_featured=True)
        resposta = logado.get(reverse("space_list"))
        destacados = [a.name for a in resposta.context["featured_attributes"]]
        outros = [a.name for a in resposta.context["other_attributes"]]
        assert sorted(destacados) == ["TV", "Wi-Fi"]
        assert "Projetor" in outros
        assert "Mais equipamentos" in resposta.content.decode()

    def test_todos_os_equipamentos_continuam_acessiveis(self, logado, catalogo):
        """Destacar não pode fazer equipamento sumir da tela."""
        Attribute.objects.filter(name="TV").update(is_featured=True)
        conteudo = logado.get(reverse("space_list")).content.decode()
        for nome in NOMES_PADRAO:
            assert nome in conteudo

    def test_secao_abre_sozinha_quando_ha_filtro_escondido(self, logado, catalogo):
        """Um filtro marcado invisível seria um resultado inexplicável."""
        Attribute.objects.filter(name="TV").update(is_featured=True)
        resposta = logado.get(reverse("space_list"), {"attributes": "Projetor"})
        assert resposta.context["has_hidden_selection"] is True
        assert re.search(r"<details[^>]*\sopen", resposta.content.decode())

    def test_secao_fica_fechada_quando_a_selecao_esta_a_vista(self, logado, catalogo):
        """Sem nada escondido, a seção começa recolhida."""
        Attribute.objects.filter(name="TV").update(is_featured=True)
        resposta = logado.get(reverse("space_list"), {"attributes": "TV"})
        assert resposta.context["has_hidden_selection"] is False

    def test_agrupa_por_categoria_quando_preenchida(self, logado, catalogo):
        """A lista longa fica navegável quando um administrador categoriza."""
        Attribute.objects.filter(name="TV").update(is_featured=True)
        Attribute.objects.filter(name__in=["Projetor", "Webcam"]).update(category="Audiovisual")
        conteudo = logado.get(reverse("space_list")).content.decode()
        assert "Audiovisual" in conteudo

    def test_filtro_continua_funcionando(self, logado, catalogo):
        """A mudança é de apresentação: filtrar precisa dar o mesmo resultado."""
        com_tv = Space.objects.create(name="Sala com TV", capacity=6, location="1º andar")
        Space.objects.create(name="Sala sem TV", capacity=6, location="2º andar")
        com_atributos(com_tv, [catalogo["TV"]])
        Attribute.objects.filter(name="TV").update(is_featured=True)
        resposta = logado.get(reverse("space_list"), {"attributes": "TV"})
        assert [e.name for e in resposta.context["spaces"]] == ["Sala com TV"]

    def test_icone_aparece_ao_lado_do_nome(self, logado, catalogo):
        """O ícone é reforço; o nome continua escrito por extenso."""
        Attribute.objects.filter(name="Wi-Fi").update(icon_name="wifi", is_featured=True)
        conteudo = logado.get(reverse("space_list")).content.decode()
        assert "Wi-Fi" in conteudo
        assert "<svg" in conteudo

    def test_equipamento_sem_icone_nao_quebra_a_linha(self, logado, catalogo):
        """Ícone é opcional e a ausência não pode deixar buraco no HTML."""
        resposta = logado.get(reverse("space_list"))
        assert resposta.status_code == 200
        assert "Quadro branco" in resposta.content.decode()


@pytest.mark.django_db
class TestAdminDeEquipamentos:
    """The admin CRUD for attributes."""

    def test_exige_staff(self, logado):
        """Editar o catálogo não é operação de usuário comum."""
        assert logado.get(reverse("admin_dashboard:attribute_list")).status_code == 403

    def test_lista_mostra_contagem_de_espacos(self, staff, catalogo):
        """Saber onde o equipamento é usado antes de mexer nele."""
        espaco = Space.objects.create(name="Sala Alfa", capacity=6, location="1º andar")
        com_atributos(espaco, [catalogo["TV"]])
        resposta = staff.get(reverse("admin_dashboard:attribute_list"))
        contagens = {a.name: a.total_espacos for a in resposta.context["attributes"]}
        assert contagens["TV"] == 1
        assert contagens["Webcam"] == 0

    def test_contagem_ignora_espaco_inativo(self, staff, catalogo):
        """Um espaço desativado não conta como uso corrente."""
        espaco = Space.objects.create(
            name="Sala Desativada", capacity=6, location="1º andar", is_active=False
        )
        com_atributos(espaco, [catalogo["TV"]])
        resposta = staff.get(reverse("admin_dashboard:attribute_list"))
        contagens = {a.name: a.total_espacos for a in resposta.context["attributes"]}
        assert contagens["TV"] == 0

    def test_cria_equipamento(self, staff):
        """Cadastrar equipamento novo não deve exigir o Django Admin."""
        resposta = staff.post(
            reverse("admin_dashboard:attribute_create"),
            {
                "name": "Lousa digital",
                "category": "Audiovisual",
                "icon_name": "board",
                "is_featured": "on",
                "sort_order": 5,
            },
        )
        assert resposta.status_code == 302
        atributo = Attribute.objects.get(name="Lousa digital")
        assert atributo.is_featured is True
        assert atributo.category == "Audiovisual"

    def test_recusa_icone_desconhecido(self, staff):
        """O formulário barra o que a tela não sabe desenhar."""
        resposta = staff.post(
            reverse("admin_dashboard:attribute_create"),
            {"name": "Teleporte", "category": "", "icon_name": "foguete", "sort_order": 0},
        )
        assert resposta.status_code == 200
        assert "icon_name" in resposta.context["form"].errors
        assert not Attribute.objects.filter(name="Teleporte").exists()

    def test_edita_destaque(self, staff, catalogo):
        """Marcar destaque pela tela precisa refletir na busca."""
        tv = catalogo["TV"]
        resposta = staff.post(
            reverse("admin_dashboard:attribute_update", args=[tv.pk]),
            {
                "name": "TV",
                "category": "",
                "icon_name": "tv",
                "is_featured": "on",
                "sort_order": 10,
            },
        )
        assert resposta.status_code == 302
        tv.refresh_from_db()
        assert tv.is_featured is True

    def test_destacados_aparecem_primeiro_na_lista(self, staff, catalogo):
        """Quem manda na tela do usuário aparece no topo da tela do admin."""
        Attribute.objects.filter(name="Wi-Fi").update(is_featured=True)
        resposta = staff.get(reverse("admin_dashboard:attribute_list"))
        assert list(resposta.context["attributes"])[0].name == "Wi-Fi"
