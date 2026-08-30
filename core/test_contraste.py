"""Guarda de contraste: mede a cor que o usuário realmente vê.

Todo teste desta suíte renderiza HTML e afirma sobre o HTML. Nenhum deles sabe
se o texto é legível — e legibilidade não é opinião, é uma razão entre duas
luminâncias que a WCAG 2.1 fixa em **4,5:1** para texto normal e 3:1 para texto
grande. Um `text-base-content/50` passa em qualquer teste de template e reprova
em 3,22:1 na tela.

Por que precisa de navegador. As opacidades do DaisyUI chegam ao CSS como
``color-mix(in oklab, var(--color-base-content) 50%, transparent)``. Resolver
isso à mão significaria reimplementar oklab, herança de cor e empilhamento de
fundos translúcidos — três coisas que o navegador já faz e que erraríamos. Aqui
o próprio Chromium pinta a cor num ``<canvas>`` de 1×1 sobre o fundo real e
devolve o RGB final. Foi assim que o ``.label-text`` do DaisyUI apareceu
reprovando em 4,33 — um defeito em *todos* os formulários da aplicação, que
nenhuma leitura de template acharia.

Marcado como ``visual`` e fora do ``make test`` padrão: roda com
``pytest -m visual``. Teste caro que roda sempre é teste que alguém desliga.

O servidor é o ``live_server`` do pytest-django — um servidor HTTP de verdade,
com o ``ALLOWED_HOSTS`` já ajustado. Escrever um à mão custou duas tentativas e
um ``DisallowedHost`` antes de eu lembrar que ele existe.
"""

import os

import pytest
from django.contrib.auth import get_user_model

from core.models import HelpArticle

pytestmark = pytest.mark.visual

User = get_user_model()

#: Limites da WCAG 2.1 AA.
AA_TEXTO_NORMAL = 4.5
AA_TEXTO_GRANDE = 3.0

#: Telas varridas. Não é a aplicação inteira: é uma de cada família de layout,
#: porque o defeito de contraste mora na classe utilitária, não na tela — se
#: `.text-muted` estiver certo aqui, está certo em toda tela que o usa.
TELAS = (
    ("Início", "/inicio/"),
    ("Ajuda", "/ajuda/"),
    ("Nova reserva", "/spaces/"),
    ("Minhas reservas", "/reservations/"),
    ("Calendário", "/calendario/"),
    ("Visão geral (admin)", "/admin-dashboard/"),
    ("Relatórios (admin)", "/admin-dashboard/relatorios/"),
    ("Blocos de ajuda (admin)", "/admin-dashboard/ajuda/"),
    ("Novo bloco (admin)", "/admin-dashboard/ajuda/new/"),
    ("Política (admin)", "/admin-dashboard/policy/"),
    ("Catálogo (admin)", "/admin-dashboard/services/"),
    ("Novo serviço (admin)", "/admin-dashboard/services/new/"),
)

#: Exceção declarada, uma só. O ícone de prédio que ocupa o lugar de uma foto
#: ausente é gráfico decorativo: leva ``aria-hidden`` e tem um texto
#: equivalente em ``sr-only`` ao lado. A WCAG não exige contraste de gráfico
#: decorativo — e um placeholder discreto é justamente o que se quer ali.
#: Qualquer outra exceção precisa aparecer nesta lista, com o motivo escrito.
ISENTOS = (
    "Espaço sem foto cadastrada",
)

#: Mede a cor final de cada nó que carrega texto próprio.
#:
#: ``willReadFrequently`` evita que o Chromium promova o canvas para a GPU, de
#: onde a leitura de pixel volta lenta. O fundo é procurado subindo a árvore até
#: achar um elemento com cor opaca, porque o pai imediato quase sempre é
#: transparente e comparar contra "transparente" não significa nada.
MEDIR = """
() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true});
  const pintar = (cor, base) => {
    cx.clearRect(0, 0, 1, 1);
    cx.fillStyle = base; cx.fillRect(0, 0, 1, 1);
    cx.fillStyle = cor;  cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2]];
  };
  const fundoDe = (e) => {
    let n = e, bg = 'rgb(255,255,255)';
    while (n) {
      const b = getComputedStyle(n).backgroundColor;
      if (b && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(b)) { bg = b; break; }
      n = n.parentElement;
    }
    return pintar(bg, 'rgb(255,255,255)');
  };
  const achados = [];
  for (const e of document.querySelectorAll('body *')) {
    const proprio = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!proprio) continue;
    const st = getComputedStyle(e);
    if (st.visibility === 'hidden' || st.display === 'none' || st.opacity === '0') continue;
    // `sr-only` é lido por leitor de tela, nunca pintado: contraste não se aplica.
    if (e.closest('.sr-only')) continue;
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const bg = fundoDe(e);
    achados.push({
      fg: pintar(st.color, `rgb(${bg.join(',')})`),
      bg: bg,
      px: parseFloat(st.fontSize),
      peso: parseInt(st.fontWeight) || 400,
      texto: e.textContent.trim().slice(0, 60),
      classe: (e.className || '').toString().slice(0, 70),
    });
  }
  return achados;
}
"""


def _luminancia(rgb):
    """Return the relative luminance of an sRGB triplet, per WCAG 2.1."""

    def canal(valor):
        valor = valor / 255
        return valor / 12.92 if valor <= 0.03928 else ((valor + 0.055) / 1.055) ** 2.4

    return 0.2126 * canal(rgb[0]) + 0.7152 * canal(rgb[1]) + 0.0722 * canal(rgb[2])


def razao_de_contraste(frente, fundo):
    """Return the WCAG contrast ratio between two opaque sRGB colours.

    Args:
        frente: A cor do texto, já resolvida sobre o fundo.
        fundo: A cor do fundo.

    Returns:
        float: A razão, de 1,0 (invisível) a 21,0 (preto no branco).
    """
    claro, escuro = sorted((_luminancia(frente), _luminancia(fundo)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def limite_para(px, peso):
    """Return the AA threshold for a given font size and weight.

    A WCAG chama de "grande" o texto a partir de 18pt (24px), ou 14pt (18,66px)
    em negrito. Texto grande passa com 3:1; o resto precisa de 4,5:1.
    """
    grande = px >= 24 or (px >= 18.66 and peso >= 700)
    return AA_TEXTO_GRANDE if grande else AA_TEXTO_NORMAL


def _executavel_do_navegador():
    """Return an explicit Chromium path when the environment provides one.

    A imagem da aplicação e a máquina de quem desenvolve nem sempre têm a mesma
    revisão de navegador que o Playwright espera baixar. ``CHROMIUM_EXECUTAVEL``
    aponta para um Chromium já instalado; sem ela, o Playwright usa o dele.
    """
    return os.environ.get("CHROMIUM_EXECUTAVEL") or None


@pytest.fixture
def cenario(db):
    """Seed enough data for every swept screen to render something."""
    gestor = User.objects.create_user(
        username="contraste", password="senha-de-teste-123", is_staff=True
    )
    HelpArticle.objects.create(
        title="Uso de auditórios",
        body="Primeiro parágrafo do bloco.\n\nSegundo parágrafo do bloco.",
    )
    return gestor


@pytest.mark.django_db(transaction=True)
def test_todo_texto_visivel_passa_no_aa(cenario, live_server):
    """Nenhum texto pintado pode ficar abaixo do mínimo da WCAG 2.1 AA.

    Falha listando tela, razão medida, tamanho e a classe culpada — porque
    "contraste insuficiente" sem o seletor manda a próxima pessoa procurar
    agulha em palheiro.
    """
    playwright = pytest.importorskip("playwright.sync_api")

    reprovas = []
    with playwright.sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=_executavel_do_navegador())
        pagina = navegador.new_context(viewport={"width": 1440, "height": 900}).new_page()

        pagina.goto(f"{live_server.url}/accounts/login/")
        pagina.fill('input[name="username"]', cenario.username)
        pagina.fill('input[name="password"]', "senha-de-teste-123")
        pagina.click('button[type="submit"], input[type="submit"]')
        pagina.wait_for_load_state("networkidle")

        for nome, caminho in TELAS:
            pagina.goto(f"{live_server.url}{caminho}")
            pagina.wait_for_load_state("networkidle")
            for achado in pagina.evaluate(MEDIR):
                if any(isento in achado["texto"] for isento in ISENTOS):
                    continue
                razao = razao_de_contraste(achado["fg"], achado["bg"])
                minimo = limite_para(achado["px"], achado["peso"])
                if razao < minimo:
                    reprovas.append(
                        f"{nome}: {razao:.2f}:1 (mínimo {minimo}) "
                        f"em {achado['px']:.0f}px — {achado['texto']!r} "
                        f"[{achado['classe']}]"
                    )
        navegador.close()

    assert not reprovas, "texto abaixo do contraste mínimo:\n  " + "\n  ".join(reprovas)


@pytest.mark.parametrize(
    ("frente", "fundo", "esperado"),
    [
        ((0, 0, 0), (255, 255, 255), 21.0),
        ((255, 255, 255), (255, 255, 255), 1.0),
        ((119, 119, 119), (255, 255, 255), 4.48),
    ],
)
def test_a_propria_conta_esta_certa(frente, fundo, esperado):
    """A régua também precisa ser conferida.

    Sem isto, um erro na fórmula transformaria a guarda inteira num teste que
    sempre passa — a pior espécie de teste, porque parece proteção.
    """
    assert round(razao_de_contraste(frente, fundo), 2) == esperado


@pytest.mark.parametrize(
    ("px", "peso", "esperado"),
    [
        (14, 400, AA_TEXTO_NORMAL),
        (16, 700, AA_TEXTO_NORMAL),
        (24, 400, AA_TEXTO_GRANDE),
        (19, 700, AA_TEXTO_GRANDE),
        (19, 400, AA_TEXTO_NORMAL),
    ],
)
def test_o_limite_segue_a_definicao_de_texto_grande(px, peso, esperado):
    """18,66px só vale como grande se for negrito; 24px vale sempre."""
    assert limite_para(px, peso) == esperado
