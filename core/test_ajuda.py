"""Tests for the help screen — its derived half, its written half, and its CRUD.

O que se protege aqui não é "a tela abre". É a única promessa que uma tela de
ajuda faz: **o que ela diz é verdade agora**.

Por isso o teste central é uma varredura de políticas. Ele muda o horário, os
dias, a duração e a tolerância, e exige que o texto acompanhe. Se alguém um dia
substituir a derivação por uma frase escrita à mão — que é a tentação óbvia,
porque escrever é mais rápido do que derivar — esta varredura falha na hora, e
não seis meses depois, quando um servidor tiver ido até o prédio num sábado
porque a Ajuda dizia que abria.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.ajuda import _minutos_por_extenso, perguntas_frequentes
from core.models import HelpArticle
from reservations.models import BookingPolicy
from reservations.steps import FLUXO_EM_USO

User = get_user_model()


@pytest.fixture
def policy(db):
    """Return the live policy, opening Monday to Friday, 08:00–18:00."""
    politica = BookingPolicy.carregar()
    politica.opening_time = datetime.time(8, 0)
    politica.closing_time = datetime.time(18, 0)
    politica.opens_monday = True
    politica.opens_tuesday = True
    politica.opens_wednesday = True
    politica.opens_thursday = True
    politica.opens_friday = True
    politica.opens_saturday = False
    politica.opens_sunday = False
    politica.save()
    return politica


@pytest.fixture
def servidor(db):
    """Return an ordinary user."""
    return User.objects.create_user(username="servidor", password="senha-de-teste-123")


@pytest.fixture
def gestor(db):
    """Return a staff member."""
    return User.objects.create_user(
        username="gestor", password="senha-de-teste-123", is_staff=True
    )


@pytest.fixture
def logado(client, servidor):
    """Return a client logged in as an ordinary user."""
    client.force_login(servidor)
    return client


def texto_de(item):
    """Flatten one answer into a single searchable string."""
    return " ".join(item["respostas"])


def texto_todo(perguntas):
    """Flatten every answer into a single searchable string."""
    return " ".join(texto_de(item) for item in perguntas)


def resposta(perguntas, identificador):
    """Return the answer with the given id."""
    return next(item for item in perguntas if item["id"] == identificador)


class TestMinutosPorExtenso:
    """A duração precisa sair como as pessoas dizem, não como o banco guarda."""

    @pytest.mark.parametrize(
        ("minutos", "esperado"),
        [
            (30, "30 minutos"),
            (45, "45 minutos"),
            (60, "1 hora"),
            (120, "2 horas"),
            (240, "4 horas"),
            (90, "1h30"),
            (150, "2h30"),
        ],
    )
    def test_escreve_a_duracao(self, minutos, esperado):
        """A duração sai como as pessoas dizem, não como o banco guarda."""
        assert _minutos_por_extenso(minutos) == esperado


class TestDerivacaoAcompanhaAPolitica:
    """A varredura: mudou a regra, mudou o texto."""

    def test_o_horario_vem_da_politica(self, policy):
        """Mudou o horário na política, mudou a resposta."""
        policy.opening_time = datetime.time(7, 30)
        policy.closing_time = datetime.time(19, 0)
        policy.save()

        texto = texto_de(resposta(perguntas_frequentes(), "quando-reservar"))
        assert "07:30" in texto
        assert "19:00" in texto
        assert "08:00" not in texto

    def test_os_dias_vem_da_politica(self, policy):
        """Abrir o sábado muda a frase, sem tocar em texto nenhum."""
        texto = texto_de(resposta(perguntas_frequentes(), "quando-reservar"))
        assert "de segunda-feira a sexta-feira" in texto

        policy.opens_saturday = True
        policy.save()
        texto = texto_de(resposta(perguntas_frequentes(), "quando-reservar"))
        assert "de segunda-feira a sábado" in texto

    def test_dias_com_buraco_saem_listados(self, policy):
        """Dias não corridos saem enumerados, não como intervalo."""
        policy.opens_tuesday = False
        policy.opens_thursday = False
        policy.save()

        texto = texto_de(resposta(perguntas_frequentes(), "quando-reservar"))
        assert "segunda-feira, quarta-feira e sexta-feira" in texto

    def test_um_dia_so(self, policy):
        """Com um dia só, a frase não vira um intervalo de um elemento."""
        for campo in BookingPolicy.CAMPOS_DE_DIA:
            setattr(policy, campo, campo == "opens_wednesday")
        policy.save()

        texto = texto_de(resposta(perguntas_frequentes(), "quando-reservar"))
        assert "apenas quarta-feira" in texto

    def test_o_incremento_vem_da_politica(self, policy):
        """O passo dos horários é o configurado, não um número fixo."""
        policy.slot_minutes = 15
        policy.save()

        texto = texto_de(resposta(perguntas_frequentes(), "quando-reservar"))
        assert "de 15 em 15 minutos" in texto

    def test_a_duracao_vem_da_politica(self, policy):
        """Mínimo e máximo saem da política, já escritos por extenso."""
        policy.min_duration_minutes = 60
        policy.max_duration_minutes = 180
        policy.save()

        texto = texto_de(resposta(perguntas_frequentes(), "quanto-tempo"))
        assert "no mínimo 1 hora" in texto
        assert "no máximo 3 horas" in texto

    def test_o_horizonte_vem_da_politica(self, policy):
        """A antecedência máxima é a configurada."""
        policy.horizon_days = 45
        policy.save()

        texto = texto_de(resposta(perguntas_frequentes(), "como-reservar"))
        assert "45 dias" in texto

    def test_a_janela_de_check_in_e_a_real(self, policy):
        """A janela citada é a constante que o serviço aplica."""
        from reservations.services import CHECK_IN_WINDOW_MINUTES

        texto = texto_de(resposta(perguntas_frequentes(), "check-in"))
        assert f"{CHECK_IN_WINDOW_MINUTES} minutos antes" in texto

    def test_as_etapas_sao_as_do_fluxo_em_uso(self, policy):
        """A Ajuda ensina exatamente as etapas da constante."""
        texto = texto_de(resposta(perguntas_frequentes(), "como-reservar"))
        assert f"{len(FLUXO_EM_USO)} etapas" in texto
        for etapa in FLUXO_EM_USO:
            assert etapa.rotulo in texto


class TestHonestidadeDoNoShow:
    """A resposta muda de sentido conforme a regra esteja ligada ou não."""

    def test_com_a_regra_desligada_diz_que_nada_e_liberado(self, policy):
        """Com a regra desligada, a resposta não ameaça com o que não acontece."""
        policy.release_no_shows = False
        policy.save()

        texto = texto_de(resposta(perguntas_frequentes(), "sem-check-in"))
        assert "nada é liberado automaticamente" in texto
        assert "continua ocupando" in texto

    def test_com_a_regra_ligada_diz_o_prazo_real(self, policy):
        """Com a regra ligada, a resposta dá o prazo — e ele é o configurado."""
        policy.release_no_shows = True
        policy.no_show_threshold_minutes = 20
        policy.save()

        texto = texto_de(resposta(perguntas_frequentes(), "sem-check-in"))
        assert "20 minutos" in texto
        assert "não comparecida" in texto
        assert "nada é liberado automaticamente" not in texto

    def test_a_tolerancia_acompanha_a_politica(self, policy):
        """Mudou a tolerância, mudou o prazo citado."""
        policy.release_no_shows = True
        policy.no_show_threshold_minutes = 60
        policy.save()

        texto = texto_de(resposta(perguntas_frequentes(), "sem-check-in"))
        assert "1 hora" in texto


class TestServicos:
    """Serviços prometidos precisam existir no catálogo."""

    def test_sem_catalogo_nao_promete_nada(self, policy):
        """Com tudo desativado, a resposta diz que não há serviço — e só isso.

        A migration ``0002_catalogo_inicial`` semeia um catálogo real, então o
        caso "vazio" não é o estado de fábrica: é o estado em que um
        administrador desativou tudo. É justamente aí que a resposta genérica
        ("peça pela sua reserva") viraria promessa falsa.
        """
        from services.models import ServiceType

        ServiceType.objects.update(is_active=False)

        texto = texto_de(resposta(perguntas_frequentes(), "servicos"))
        assert "Nenhum serviço está disponível" in texto

    def test_lista_os_servicos_ativos(self, policy):
        """Os serviços ativos são citados pelo nome."""
        from services.models import ServiceType

        ServiceType.objects.update(is_active=False)
        ServiceType.objects.create(name="Café de teste", slug="cafe-de-teste", sort_order=1)
        ServiceType.objects.create(name="Projetor de teste", slug="projetor-de-teste", sort_order=2)

        texto = texto_de(resposta(perguntas_frequentes(), "servicos"))
        assert "Café de teste" in texto
        assert "Projetor de teste" in texto

    def test_servico_inativo_fica_de_fora(self, policy):
        """Serviço desativado não é prometido."""
        from services.models import ServiceType

        ServiceType.objects.update(is_active=False)
        ServiceType.objects.create(name="Café de teste", slug="cafe-de-teste")
        ServiceType.objects.create(
            name="Serviço desativado", slug="servico-desativado", is_active=False
        )

        texto = texto_de(resposta(perguntas_frequentes(), "servicos"))
        assert "Café de teste" in texto
        assert "Serviço desativado" not in texto

    def test_a_antecedencia_maxima_aparece(self, policy):
        """O maior prazo do catálogo é o citado."""
        from services.models import ServiceType

        ServiceType.objects.update(is_active=False)
        ServiceType.objects.create(
            name="Café de teste", slug="cafe-de-teste", min_lead_time_hours=4
        )
        ServiceType.objects.create(
            name="Coquetel de teste", slug="coquetel-de-teste", min_lead_time_hours=48
        )

        texto = texto_de(resposta(perguntas_frequentes(), "servicos"))
        assert "48 horas" in texto


class TestNadaInventado:
    """Nenhuma resposta pode citar um contato ou número que não existe."""

    def test_nao_ha_telefone_nem_email(self, policy):
        """Nenhum contato inventado atravessa para a tela."""
        import re

        texto = texto_todo(perguntas_frequentes())
        assert not re.search(r"\(\d{2}\)", texto), "telefone inventado na Ajuda"
        assert "@" not in texto, "e-mail inventado na Ajuda"
        assert "ramal" not in texto.lower()


class TestBlocosInstitucionais:
    """A metade escrita por gente."""

    def test_o_slug_sai_do_titulo(self, db):
        """O slug — que vira âncora — é derivado, não digitado."""
        bloco = HelpArticle.objects.create(title="Uso de auditórios", body="Texto.")
        assert bloco.slug == "uso-de-auditorios"

    def test_titulos_iguais_nao_colidem(self, db):
        """Dois blocos com o mesmo título ainda têm âncoras distintas."""
        primeiro = HelpArticle.objects.create(title="Acessibilidade", body="A.")
        segundo = HelpArticle.objects.create(title="Acessibilidade", body="B.")
        assert primeiro.slug != segundo.slug

    def test_paragrafos_saem_das_linhas_em_branco(self, db):
        """Linha em branco separa parágrafo; espaço sozinho não vira um."""
        bloco = HelpArticle.objects.create(
            title="Auditórios",
            body="Primeiro parágrafo.\n\n  \n\nSegundo parágrafo.\n",
        )
        assert bloco.paragrafos() == ["Primeiro parágrafo.", "Segundo parágrafo."]

    def test_publicados_respeita_a_ordem_e_a_situacao(self, db):
        """A consulta pública devolve só o publicado, na ordem de exibição."""
        HelpArticle.objects.create(title="Zebra", body="z", sort_order=1)
        HelpArticle.objects.create(title="Alfa", body="a", sort_order=2)
        HelpArticle.objects.create(title="Oculto", body="o", sort_order=0, is_published=False)

        titulos = [bloco.title for bloco in HelpArticle.objects.publicados()]
        assert titulos == ["Zebra", "Alfa"]


class TestTela:
    """A tela do usuário."""

    def test_anonimo_nao_entra(self, client, policy):
        """A Ajuda é da casa: sem sessão, não entra."""
        resposta_http = client.get(reverse("ajuda"))
        assert resposta_http.status_code in (302, 403)

    def test_usuario_entra(self, logado, policy):
        """Servidor autenticado abre a tela."""
        assert logado.get(reverse("ajuda")).status_code == 200

    def test_mostra_as_perguntas_derivadas(self, logado, policy):
        """Toda pergunta derivada chega à tela."""
        html = logado.get(reverse("ajuda")).content.decode()
        for item in perguntas_frequentes():
            assert item["pergunta"] in html

    def test_mostra_os_blocos_publicados(self, logado, policy):
        """Título e texto do bloco publicado aparecem."""
        HelpArticle.objects.create(title="Uso de auditórios", body="Reserve com antecedência.")
        html = logado.get(reverse("ajuda")).content.decode()
        assert "Uso de auditórios" in html
        assert "Reserve com antecedência." in html

    def test_nao_mostra_bloco_despublicado(self, logado, policy):
        """Rascunho fica fora da tela do usuário."""
        HelpArticle.objects.create(
            title="Rascunho interno", body="Não publicar.", is_published=False
        )
        html = logado.get(reverse("ajuda")).content.decode()
        assert "Rascunho interno" not in html

    def test_o_texto_do_bloco_nao_vira_marcacao(self, logado, policy):
        """Bloco editável é texto puro. Sempre."""
        HelpArticle.objects.create(
            title="Teste",
            body="<script>alert('x')</script>",
        )
        html = logado.get(reverse("ajuda")).content.decode()
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_encaminha_para_consultar_normas(self, logado, policy):
        """O rodapé leva a um destino real, não a um contato inventado."""
        html = logado.get(reverse("ajuda")).content.decode()
        assert reverse("document_assistant") in html
        assert "Consultar Normas" in html

    def test_o_indice_aponta_para_ancoras_que_existem(self, logado, policy):
        """Índice que leva a lugar nenhum é link morto dentro da própria página."""
        import re

        HelpArticle.objects.create(title="Uso de auditórios", body="Texto.")
        html = logado.get(reverse("ajuda")).content.decode()
        indice = re.search(r'aria-label="Índice da ajuda".*?</nav>', html, re.S)
        assert indice
        ancoras = re.findall(r'href="#([^"]+)"', indice.group(0))
        assert ancoras
        for ancora in ancoras:
            assert f'id="{ancora}"' in html, f"#{ancora} não existe na página"

    def test_a_tela_funciona_sem_nenhum_bloco(self, logado, policy):
        """Sem conteúdo institucional a Ajuda ainda responde — e não mostra seção vazia."""
        html = logado.get(reverse("ajuda")).content.decode()
        assert html.count("Orientações da administração") == 0
        assert "Como faço o check-in?" in html


class TestCrudAdministrativo:
    """Quem edita os blocos."""

    def test_usuario_comum_nao_entra(self, logado, policy):
        """Escrever a ajuda institucional é da administração."""
        assert logado.get(reverse("admin_dashboard:help_article_list")).status_code == 403

    def test_gestor_entra(self, client, gestor, policy):
        """Staff abre a lista de blocos."""
        client.force_login(gestor)
        assert client.get(reverse("admin_dashboard:help_article_list")).status_code == 200

    def test_gestor_cria_um_bloco(self, client, gestor, policy):
        """O formulário grava o bloco."""
        client.force_login(gestor)
        client.post(
            reverse("admin_dashboard:help_article_create"),
            {
                "title": "Uso de auditórios",
                "body": "Reserve com antecedência.",
                "sort_order": 0,
                "is_published": "on",
            },
        )
        assert HelpArticle.objects.filter(title="Uso de auditórios").exists()

    def test_texto_em_branco_e_recusado(self, client, gestor, policy):
        """Título sem texto não publica um bloco vazio."""
        client.force_login(gestor)
        resposta_http = client.post(
            reverse("admin_dashboard:help_article_create"),
            {"title": "Vazio", "body": "   \n\n  ", "sort_order": 0},
        )
        assert resposta_http.status_code == 200
        assert not HelpArticle.objects.filter(title="Vazio").exists()

    def test_gestor_edita(self, client, gestor, policy):
        """A edição altera o bloco existente, sem criar outro."""
        bloco = HelpArticle.objects.create(title="Antes", body="Texto.")
        client.force_login(gestor)
        client.post(
            reverse("admin_dashboard:help_article_update", args=[bloco.pk]),
            {"title": "Depois", "body": "Texto novo.", "sort_order": 0, "is_published": "on"},
        )
        bloco.refresh_from_db()
        assert bloco.title == "Depois"

    def test_remover_exige_post(self, client, gestor, policy):
        """GET não apaga: link que apaga ao ser visitado apaga sozinho."""
        bloco = HelpArticle.objects.create(title="Some", body="Texto.")
        client.force_login(gestor)
        assert client.get(reverse("admin_dashboard:help_article_delete", args=[bloco.pk]))
        assert HelpArticle.objects.filter(pk=bloco.pk).exists()

    def test_gestor_remove(self, client, gestor, policy):
        """O POST remove o bloco."""
        bloco = HelpArticle.objects.create(title="Some", body="Texto.")
        client.force_login(gestor)
        client.post(reverse("admin_dashboard:help_article_delete", args=[bloco.pk]))
        assert not HelpArticle.objects.filter(pk=bloco.pk).exists()

    def test_a_lista_mostra_publicados_e_rascunhos(self, client, gestor, policy):
        """A lista da administração mostra os dois estados."""
        HelpArticle.objects.create(title="Publicado", body="p")
        HelpArticle.objects.create(title="Rascunho", body="r", is_published=False)
        client.force_login(gestor)
        html = client.get(reverse("admin_dashboard:help_article_list")).content.decode()
        assert "Publicado" in html
        assert "Rascunho" in html


class TestAAjudaConcordaComOStepper:
    """A Ajuda e a tela de reserva precisam contar a mesma história.

    Este teste existe por causa de um defeito real, e a forma dele é a lição.

    A Fase 23 já tinha um teste de etapas: ele comparava a Ajuda com a constante
    ``FLUXO_EM_USO``. Passava sempre — porque a Ajuda **lê** essa constante.
    Comparar uma coisa com a fonte de onde ela veio não prova nada; prova só que
    a leitura funciona.

    Enquanto isso, todas as views do fluxo passavam ``FLUXO_V2`` explicitamente,
    e ``FLUXO_EM_USO`` apontava para a lista antiga, de três etapas. O stepper
    mostrava quatro; a Ajuda ensinava três. Nenhum teste reclamou, e quem
    encontrou foi uma captura de tela.

    A correção do teste é comparar **as duas telas renderizadas**, sem passar
    pela constante. É mais caro e mais feio — precisa extrair texto de HTML —
    e é a única versão que teria falhado.
    """

    def _rotulos_do_stepper(self, html):
        """Extract the step labels from a rendered stepper, in order."""
        import re

        nav = re.search(r'aria-label="Etapas da reserva".*?</nav>', html, re.S)
        assert nav, "a tela não tem stepper"

        # O `sr-only` sai primeiro, e do HTML inteiro: ele mora *dentro* do
        # `step-label` e diz "Etapa 2 de 4, atual:". Tentar recortá-lo depois
        # não funciona — o `</span>` dele fecha a captura do rótulo antes da
        # hora, e o teste passa a comparar o texto de acessibilidade.
        limpo = re.sub(r'<span class="sr-only">.*?</span>', "", nav.group(0), flags=re.S)

        rotulos = []
        for bloco in re.findall(r'<span class="step-label">(.*?)</span>', limpo, re.S):
            texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", bloco)).strip()
            if texto:
                rotulos.append(texto)
        return rotulos

    def test_a_ajuda_lista_as_mesmas_etapas_que_a_tela_de_reserva(self, logado, policy):
        """As duas telas, comparadas uma com a outra — não com a constante."""
        html_reserva = logado.get(reverse("space_list")).content.decode()
        rotulos = self._rotulos_do_stepper(html_reserva)
        assert rotulos, "não consegui ler os rótulos do stepper"

        texto = texto_de(resposta(perguntas_frequentes(), "como-reservar"))
        assert f"{len(rotulos)} etapas" in texto, (
            f"o stepper mostra {len(rotulos)} etapas e a Ajuda diz outra coisa: {texto!r}"
        )
        for rotulo in rotulos:
            assert rotulo in texto, f"a etapa {rotulo!r} está na tela de reserva e não na Ajuda"

    def test_todas_as_telas_do_fluxo_usam_o_mesmo_numero_de_etapas(self, logado, policy):
        """Um stepper de 4 numa tela e de 3 em outra confunde mais do que ajuda."""
        html = logado.get(reverse("space_list")).content.decode()
        esperado = len(self._rotulos_do_stepper(html))
        assert esperado == len(FLUXO_EM_USO), (
            "a tela renderiza um número de etapas diferente da constante — "
            "alguma view está passando um fluxo próprio"
        )
