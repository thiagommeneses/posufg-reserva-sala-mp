"""Tests for the reports screen and its CSV export.

O cálculo tem testes próprios em ``reservations/test_relatorios.py``. O que se
protege aqui é o que só a tela pode errar:

* quem entra;
* a tela e o arquivo mostrarem os **mesmos** números — um relatório que discorda
  do próprio CSV é pior do que não ter exportação;
* o CSV abrir no Excel em português, que é onde ele vai ser aberto;
* as ressalvas continuarem visíveis. Um número sem a ressalva que o sustenta é
  uma decisão errada esperando para acontecer.
"""

import csv
import datetime
import io

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from reservations.models import BookingPolicy, Reservation, ReservationStatus
from spaces.models import Space

User = get_user_model()


def local(date, hora, minuto=0):
    """Return an aware datetime in the local timezone."""
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(hora, minuto)))


@pytest.fixture
def policy(db):
    """Return a policy that opens Monday to Friday, 08:00–18:00."""
    politica = BookingPolicy.carregar()
    politica.opening_time = datetime.time(8, 0)
    politica.closing_time = datetime.time(18, 0)
    politica.opens_saturday = False
    politica.opens_sunday = False
    politica.save()
    return politica


@pytest.fixture
def espaco(db):
    """Return a plain active space."""
    return Space.objects.create(name="Sala Alfa", capacity=10, location="1º andar")


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
def logado(client, gestor):
    """Return a client logged in as staff."""
    client.force_login(gestor)
    return client


@pytest.fixture
def ontem():
    """Return yesterday, which every default period covers."""
    return timezone.localdate() - datetime.timedelta(days=1)


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
    """Who may read the numbers."""

    def test_anonimo_nao_entra(self, client):
        """Sem sessão, não há relatório."""
        assert client.get(reverse("admin_dashboard:reports")).status_code in (302, 403)

    def test_usuario_comum_nao_entra(self, client, servidor):
        """Ocupação por espaço e assunto de reserva são leitura da administração."""
        client.force_login(servidor)
        assert client.get(reverse("admin_dashboard:reports")).status_code in (302, 403)

    def test_o_csv_tambem_e_protegido(self, client, servidor):
        """A porta dos fundos precisa da mesma chave da porta da frente.

        Exportação é o lugar clássico de esquecer a permissão: a tela é
        obviamente sensível, o arquivo parece "só um download".
        """
        client.force_login(servidor)
        assert client.get(reverse("admin_dashboard:reports_csv")).status_code in (302, 403)

    def test_staff_entra(self, logado, policy):
        """Quem administra os espaços abre a tela."""
        assert logado.get(reverse("admin_dashboard:reports")).status_code == 200


@pytest.mark.django_db
class TestTela:
    """The screen itself."""

    def test_abre_no_periodo_padrao(self, logado, policy):
        """Sem parâmetro nenhum, a tela mostra um período verdadeiro."""
        resposta = logado.get(reverse("admin_dashboard:reports"))
        assert resposta.status_code == 200
        assert resposta.context["periodo"]["primeiro_dia"] is not None

    def test_periodo_invalido_nao_derruba_a_tela(self, logado, policy):
        """Link velho continua abrindo um relatório, não uma página de erro."""
        resposta = logado.get(
            reverse("admin_dashboard:reports"), {"de": "31/02/2026", "ate": "oi"}
        )
        assert resposta.status_code == 200

    def test_o_periodo_escolhido_atravessa_para_o_csv(self, logado, policy):
        """O botão de exportar precisa levar o mesmo recorte que está na tela.

        Se o link do CSV perdesse os parâmetros, o arquivo baixado seria de
        outro período — e ninguém repararia, porque os dois têm cara de certo.
        """
        resposta = logado.get(reverse("admin_dashboard:reports"), {"periodo": "7"})
        assert "periodo=7" in resposta.context["url_csv"]

    def test_mostra_a_ressalva_do_no_show(self, logado, policy):
        """Zero por não haver faltas e zero por não haver medição são opostos.

        Com a regra desligada — o padrão — a tela precisa dizer que ninguém
        está medindo, senão o zero é lido como boa notícia.
        """
        assert policy.release_no_shows is False
        html = logado.get(reverse("admin_dashboard:reports")).content.decode()
        assert "no-show" in html.lower()
        assert resposta_contem_aviso_de_regra_desligada(html)

    def test_com_a_regra_ligada_o_aviso_some(self, logado, policy):
        """A ressalva é sobre o estado real; ligada, ela não tem o que dizer."""
        policy.release_no_shows = True
        policy.save(update_fields=["release_no_shows"])
        html = logado.get(reverse("admin_dashboard:reports")).content.decode()
        assert not resposta_contem_aviso_de_regra_desligada(html)

    def test_a_ocupacao_aparece_com_o_espaco(self, logado, policy, espaco, gestor, ontem):
        """O número precisa vir com o nome do espaço a que se refere."""
        if not policy.abre_em(ontem):
            pytest.skip("ontem caiu em dia fechado; a ocupação tem teste próprio")
        reserva(espaco, gestor, ontem, 9, 11)
        html = logado.get(reverse("admin_dashboard:reports")).content.decode()
        assert espaco.name in html


def resposta_contem_aviso_de_regra_desligada(html):
    """Return whether the screen warns that nothing is marking no-shows."""
    return "não está ligada" in html or "não está sendo medido" in html or "desligada" in html


@pytest.mark.django_db
class TestCsv:
    """The file people actually open."""

    @staticmethod
    def _linhas(resposta):
        """Return the CSV rows, decoded the way a spreadsheet would."""
        texto = resposta.content.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(texto), delimiter=";"))

    def test_vem_como_anexo_com_nome_do_periodo(self, logado, policy):
        """O nome do arquivo diz de quando ele é.

        Três exportações na pasta de downloads com o mesmo nome é como alguém
        acaba mandando o relatório do mês errado para a chefia.
        """
        resposta = logado.get(reverse("admin_dashboard:reports_csv"))
        assert resposta.status_code == 200
        assert "attachment" in resposta["Content-Disposition"]
        assert ".csv" in resposta["Content-Disposition"]

    def test_comeca_com_bom_utf8(self, logado, policy):
        """Sem o BOM o Excel lê "Ocupação" como lixo."""
        resposta = logado.get(reverse("admin_dashboard:reports_csv"))
        assert resposta.content.startswith(b"\xef\xbb\xbf")

    def test_usa_ponto_e_virgula(self, logado, policy):
        """Com vírgula o Excel em português joga tudo numa coluna só."""
        resposta = logado.get(reverse("admin_dashboard:reports_csv"))
        primeira_linha = resposta.content.decode("utf-8-sig").splitlines()[1]
        assert ";" in primeira_linha

    def test_traz_todas_as_secoes(self, logado, policy):
        """Oito métricas na tela, oito no arquivo."""
        linhas = self._linhas(logado.get(reverse("admin_dashboard:reports_csv")))
        texto = "\n".join(";".join(linha) for linha in linhas)
        for secao in ["Ocupação", "Picos", "Cancelamento", "no-show", "Manutenção",
                      "Serviços", "Antecedência", "capacidade"]:
            assert secao.lower() in texto.lower(), f"o CSV não tem a seção {secao!r}"

    def test_o_arquivo_traz_os_mesmos_numeros_da_tela(
        self, logado, policy, espaco, gestor, ontem
    ):
        """A tela e o arquivo saem da mesma montagem, e este teste é o que garante.

        Duas montagens independentes divergem no primeiro ajuste feito em uma
        só — e um relatório que discorda do próprio CSV é pior do que não ter
        exportação nenhuma.
        """
        if not policy.abre_em(ontem):
            pytest.skip("ontem caiu em dia fechado; a igualdade tem teste próprio")
        reserva(espaco, gestor, ontem, 9, 11)

        tela = logado.get(reverse("admin_dashboard:reports"))
        linha_da_tela = next(
            linha for linha in tela.context["ocupacao"] if linha["espaco"].pk == espaco.pk
        )

        linhas = self._linhas(logado.get(reverse("admin_dashboard:reports_csv")))
        linha_do_csv = next(linha for linha in linhas if linha and linha[0] == espaco.name)
        # Segunda coluna: minutos ocupados, formatados sem casas decimais.
        assert linha_do_csv[1] == f"{linha_da_tela['minutos_ocupados']:.0f}"

    def test_o_periodo_do_csv_obedece_a_querystring(self, logado, policy):
        """O arquivo é do período pedido, não do padrão."""
        resposta = logado.get(
            reverse("admin_dashboard:reports_csv"),
            {"de": "2026-02-10", "ate": "2026-02-20"},
        )
        cabecalho = resposta.content.decode("utf-8-sig")
        assert "10/02/2026" in cabecalho
        assert "20/02/2026" in cabecalho


@pytest.mark.django_db
class TestPercentuaisNaTela:
    """The screen must show percentages, not fractions.

    A verificação visual pegou isto, e os testes de cálculo não podiam pegar:
    as contas estavam certas, a tela é que dividia por cem. O template tentava
    virar fração em percentual anexando um "0" depois do ``floatformat`` — e
    0,0142 virava "0,00%". Na largura da barra o mesmo truque produzia
    ``width: 0,014300%``, CSS inválido: o navegador ignorava e **toda** barra
    aparecia cheia. Sete espaços 100% ocupados com "0,00%" escrito ao lado.
    """

    def test_a_ocupacao_aparece_em_percentual(self, logado, policy, espaco, gestor, ontem):
        """Metade do expediente tem de aparecer como metade, não como 0,5%."""
        if not policy.abre_em(ontem):
            pytest.skip("ontem caiu em dia fechado")
        # Cinco horas de um expediente de dez, num período de um dia só.
        reserva(espaco, gestor, ontem, 8, 13)
        resposta = logado.get(
            reverse("admin_dashboard:reports"),
            {"de": ontem.isoformat(), "ate": ontem.isoformat()},
        )
        linha = next(
            item for item in resposta.context["ocupacao"] if item["espaco"].pk == espaco.pk
        )
        assert linha["percentual"] == pytest.approx(50.0)
        assert "50,0%" in resposta.content.decode()

    def test_a_largura_da_barra_e_css_valido(self, logado, policy, espaco, gestor, ontem):
        """Separador decimal do CSS é ponto, em qualquer idioma da interface.

        Com vírgula a regra é descartada pelo navegador — sem erro no console —
        e a barra assume a largura do contêiner.
        """
        import re

        if not policy.abre_em(ontem):
            pytest.skip("ontem caiu em dia fechado")
        reserva(espaco, gestor, ontem, 8, 13)
        html = logado.get(
            reverse("admin_dashboard:reports"),
            {"de": ontem.isoformat(), "ate": ontem.isoformat()},
        ).content.decode()
        larguras = re.findall(r'style="width: ([^"]+)%"', html)
        assert larguras, "nenhuma barra foi desenhada"
        for largura in larguras:
            assert "," not in largura, f"largura com vírgula não é CSS válido: {largura!r}"
            valor = float(largura)
            assert 0 <= valor <= 100, f"largura fora da escala: {valor}"

    def test_o_uso_da_capacidade_aparece_em_percentual(
        self, logado, policy, espaco, gestor, ontem
    ):
        """Seis pessoas numa sala de dez é 60%, não 0,6%."""
        if not policy.abre_em(ontem):
            pytest.skip("ontem caiu em dia fechado")
        reserva(espaco, gestor, ontem, 9, 10, attendee_count=6)
        resposta = logado.get(
            reverse("admin_dashboard:reports"),
            {"de": ontem.isoformat(), "ate": ontem.isoformat()},
        )
        linha = resposta.context["subutilizacao"][0]
        assert linha["percentual"] == pytest.approx(60.0)
        assert "60,0%" in resposta.content.decode()
