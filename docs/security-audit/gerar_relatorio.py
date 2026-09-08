#!/usr/bin/env python3
"""Gera o PDF do relatório de auditoria de segurança de reserva-sala-mp.

Uso:
    # num ambiente virtual isolado com reportlab + matplotlib instalados
    python gerar_relatorio.py

Regenera sempre `relatorio-auditoria-seguranca.pdf` neste mesmo diretório a
partir dos dados estruturados em `dados_auditoria.py`. Não instala nada
globalmente — depende de um venv já preparado pelo operador
(`pip install reportlab matplotlib`).
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.frames import Frame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dados_auditoria as D  # noqa: E402

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relatorio-auditoria-seguranca.pdf")

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------

COR = {
    "critica": colors.HexColor("#B91C1C"),
    "alta": colors.HexColor("#EA580C"),
    "media": colors.HexColor("#D97706"),
    "baixa": colors.HexColor("#2563EB"),
    "informativa": colors.HexColor("#6B7280"),
    "ponto_forte": colors.HexColor("#059669"),
}
ROTULO_SEVERIDADE = {
    "critica": "Crítica",
    "alta": "Alta",
    "media": "Média",
    "baixa": "Baixa",
    "informativa": "Informativa",
}
INSTITUCIONAL = colors.HexColor("#0F3D2E")  # verde institucional escuro, tom MPGO
CINZA_TEXTO = colors.HexColor("#1F2937")
CINZA_CLARO = colors.HexColor("#F3F4F6")
BORDA = colors.HexColor("#D1D5DB")

TMPDIR = tempfile.mkdtemp(prefix="audit-charts-")

# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        "Titulo1",
        parent=styles["Heading1"],
        fontSize=17,
        leading=21,
        textColor=INSTITUCIONAL,
        spaceBefore=4,
        spaceAfter=10,
    )
)
styles.add(
    ParagraphStyle(
        "Titulo2",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=INSTITUCIONAL,
        spaceBefore=14,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        "Titulo3",
        parent=styles["Heading3"],
        fontSize=10.5,
        leading=13,
        textColor=CINZA_TEXTO,
        spaceBefore=8,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        "CorpoJust",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        alignment=TA_JUSTIFY,
        textColor=CINZA_TEXTO,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        "CorpoPequeno",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11.5,
        alignment=TA_LEFT,
        textColor=CINZA_TEXTO,
    )
)
styles.add(
    ParagraphStyle(
        "Codigo",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=7.3,
        leading=9.5,
        backColor=colors.HexColor("#0B1220"),
        textColor=colors.HexColor("#E5E7EB"),
        borderPadding=6,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        "CodigoIssue",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=6.6,
        leading=8.6,
        backColor=colors.HexColor("#0B1220"),
        textColor=colors.HexColor("#E5E7EB"),
        borderPadding=6,
    )
)
styles.add(
    ParagraphStyle(
        "Capa",
        parent=styles["Title"],
        fontSize=25,
        leading=30,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
)
styles.add(
    ParagraphStyle(
        "CapaSub",
        parent=styles["Normal"],
        fontSize=12.5,
        leading=17,
        textColor=colors.HexColor("#D1FAE5"),
        alignment=TA_CENTER,
    )
)


def P(text, style="CorpoJust"):
    return Paragraph(text, styles[style])


# ---------------------------------------------------------------------------
# Cabeçalho / rodapé
# ---------------------------------------------------------------------------

NOME_RELATORIO = "Relatório de Auditoria de Segurança — reserva-sala-mp"


def _header_footer(canvas, doc):
    canvas.saveState()
    largura, altura = A4

    if doc.page > 1:
        canvas.setFillColor(INSTITUCIONAL)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(2 * cm, altura - 1.3 * cm, NOME_RELATORIO)
        canvas.setStrokeColor(BORDA)
        canvas.setLineWidth(0.5)
        canvas.line(2 * cm, altura - 1.5 * cm, largura - 2 * cm, altura - 1.5 * cm)

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.line(2 * cm, 1.5 * cm, largura - 2 * cm, 1.5 * cm)
        canvas.drawString(2 * cm, 1.05 * cm, "reserva-sala-mp · Auditoria de Segurança")
        canvas.drawRightString(largura - 2 * cm, 1.05 * cm, f"Página {doc.page - 1}")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Gráficos (matplotlib -> PNG -> Image do reportlab)
# ---------------------------------------------------------------------------


def gerar_grafico_rosca(caminho):
    contagem = Counter(a["severidade"] for a in D.ACHADOS)
    ordem = ["critica", "alta", "media", "baixa", "informativa"]
    labels, valores, cores = [], [], []
    for sev in ordem:
        if contagem.get(sev):
            labels.append(f"{ROTULO_SEVERIDADE[sev]} ({contagem[sev]})")
            valores.append(contagem[sev])
            cores.append(COR[sev].hexval()[2:] if hasattr(COR[sev], "hexval") else None)

    cores_hex = {
        "critica": "#B91C1C",
        "alta": "#EA580C",
        "media": "#D97706",
        "baixa": "#2563EB",
        "informativa": "#6B7280",
    }
    cores_plot = [cores_hex[sev] for sev in ordem if contagem.get(sev)]

    fig, ax = plt.subplots(figsize=(4.4, 3.6), dpi=200)
    wedges, _texts = ax.pie(
        valores,
        colors=cores_plot,
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2},
    )
    ax.text(0, 0.08, str(sum(valores)), ha="center", va="center", fontsize=22, fontweight="bold", color="#1F2937")
    ax.text(0, -0.20, "achados", ha="center", va="center", fontsize=9, color="#6B7280")
    ax.legend(
        wedges,
        labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=9,
    )
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(caminho, transparent=True, bbox_inches="tight")
    plt.close(fig)


def gerar_grafico_categorias(caminho):
    ordem_cat = [
        "1. Isolamento por dono/organização",
        "2. Permissão no navegador vs. backend",
        "3. IDOR",
        "4. Chaves expostas",
        "5. Inputs sem tratamento (XSS)",
    ]
    contagem = Counter(a["categoria"] for a in D.ACHADOS)
    valores = [contagem.get(c, 0) for c in ordem_cat]
    rotulos_curtos = [
        "1. Isolamento",
        "2. Permissão\nno backend",
        "3. IDOR",
        "4. Chaves\nexpostas",
        "5. XSS",
    ]

    fig, ax = plt.subplots(figsize=(6.6, 3.3), dpi=200)
    barras = ax.bar(rotulos_curtos, valores, color="#0F3D2E", width=0.55, zorder=3)
    for barra, valor in zip(barras, valores):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            barra.get_height() + 0.05,
            str(valor),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color="#1F2937",
        )
    ax.set_ylim(0, max(valores + [1]) + 1)
    ax.set_yticks(range(0, max(valores + [1]) + 2))
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="both", labelsize=8.5, length=0)
    ax.yaxis.grid(True, color="#E5E7EB", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(caminho, transparent=True, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Componentes visuais
# ---------------------------------------------------------------------------


class Faixa(Flowable):
    """Uma faixa colorida de largura total, usada na capa."""

    def __init__(self, largura, altura, cor):
        super().__init__()
        self.largura = largura
        self.altura = altura
        self.cor = cor

    def draw(self):
        self.canv.setFillColor(self.cor)
        self.canv.rect(0, 0, self.largura, self.altura, fill=1, stroke=0)


def chip_severidade(sev):
    cor = COR.get(sev, COR["informativa"])
    rotulo = ROTULO_SEVERIDADE.get(sev, sev.title())
    t = Table([[rotulo]], colWidths=[2.3 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), cor),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ]
        )
    )
    return t


def linha_evidencia(rotulo, valor):
    return P(f"<b>{rotulo}:</b> {valor}", "CorpoPequeno")


# ---------------------------------------------------------------------------
# Construção do documento
# ---------------------------------------------------------------------------


def construir_capa(story):
    story.append(NextPageTemplate("normal"))

    conteudo_faixa = [
        Spacer(1, 2.6 * cm),
        P("RELATÓRIO DE AUDITORIA DE SEGURANÇA", "Capa"),
        Spacer(1, 0.5 * cm),
        P(D.PROJETO, "CapaSub"),
        Spacer(1, 2.6 * cm),
    ]
    faixa = Table([[conteudo_faixa]], colWidths=[17 * cm], rowHeights=[9.3 * cm])
    faixa.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), INSTITUCIONAL),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(faixa)
    story.append(Spacer(1, 0.8 * cm))

    dados_capa = [
        ["Data da auditoria", Paragraph(D.DATA_AUDITORIA, styles["CorpoPequeno"])],
        ["Repositório", Paragraph(D.PROJETO, styles["CorpoPequeno"])],
        ["Branch", Paragraph("redesign-v2", styles["CorpoPequeno"])],
        [
            "Escopo",
            Paragraph(
                "Código-fonte completo (backend Django/DRF, templates, JS estático, migrations), "
                "arquivos de configuração e deploy (settings.py, .env.example, Dockerfile, "
                "docker-compose*.yml, .pre-commit-config.yaml) e histórico do Git.",
                styles["CorpoPequeno"],
            ),
        ],
        [
            "Categorias avaliadas",
            Paragraph(
                "(1) Isolamento por dono/organização — equivalente a RLS neste app de organização "
                "única; (2) Permissão definida só no navegador; (3) IDOR; (4) Chaves e segredos "
                "expostos; (5) Inputs sem tratamento (XSS).",
                styles["CorpoPequeno"],
            ),
        ],
    ]
    tabela = Table(dados_capa, colWidths=[3.6 * cm, 13.4 * cm])
    tabela.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), CINZA_TEXTO),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDA),
            ]
        )
    )
    story.append(tabela)
    story.append(Spacer(1, 0.7 * cm))

    story.append(P("Nota metodológica", "Titulo3"))
    story.append(
        P(
            f"Stack detectada: <b>{D.STACK['framework']}</b> em {D.STACK['linguagem']}, ORM "
            f"{D.STACK['orm']}, autenticação {D.STACK['auth']}, frontend {D.STACK['frontend']}, "
            f"deploy via {D.STACK['deploy']}. Cada categoria genérica do roteiro de auditoria foi "
            "mapeada para o equivalente concreto desta stack antes da varredura — o detalhamento "
            "de cada mapeamento está na seção seguinte.",
            "CorpoPequeno",
        )
    )
    story.append(PageBreak())


def construir_metodologia(story):
    story.append(P("Nota metodológica — mapeamento das categorias para a stack", "Titulo2"))
    story.append(
        P(
            "Este projeto é uma aplicação Django monolítica de <b>organização única</b> (o MPGO), "
            "sem Supabase e sem separação multi-tenant — por isso as cinco categorias do roteiro "
            "padrão de auditoria foram traduzidas para o equivalente real desta stack antes da "
            "varredura, como segue.",
            "CorpoJust",
        )
    )
    for titulo, texto in D.METODOLOGIA:
        story.append(P(titulo, "Titulo3"))
        story.append(P(texto, "CorpoJust"))
    story.append(PageBreak())


def construir_resumo_executivo(story):
    story.append(P("Resumo executivo", "Titulo1"))

    contagem = Counter(a["severidade"] for a in D.ACHADOS)
    ordem = ["critica", "alta", "media", "baixa", "informativa"]
    linhas = [["Severidade", "Quantidade"]]
    for sev in ordem:
        linhas.append([ROTULO_SEVERIDADE[sev], str(contagem.get(sev, 0))])
    linhas.append(["Total de achados", str(len(D.ACHADOS))])
    linhas.append(["Pontos fortes verificados", str(len(D.PONTOS_FORTES))])

    tabela_resumo = Table(linhas, colWidths=[5 * cm, 3 * cm])
    estilo_resumo = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), INSTITUCIONAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -3), [colors.white, CINZA_CLARO]),
        ("BACKGROUND", (0, -2), (-1, -2), colors.HexColor("#E5E7EB")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D1FAE5")),
        ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    tabela_resumo.setStyle(TableStyle(estilo_resumo))

    caminho_rosca = os.path.join(TMPDIR, "rosca.png")
    gerar_grafico_rosca(caminho_rosca)
    img_rosca = Image(caminho_rosca, width=8.6 * cm, height=7 * cm)

    linha_graficos = Table(
        [[tabela_resumo, img_rosca]],
        colWidths=[8.2 * cm, 8.8 * cm],
    )
    linha_graficos.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(linha_graficos)

    story.append(Spacer(1, 0.5 * cm))
    story.append(P("Achados por categoria", "Titulo3"))
    caminho_barras = os.path.join(TMPDIR, "barras.png")
    gerar_grafico_categorias(caminho_barras)
    story.append(Image(caminho_barras, width=16 * cm, height=8 * cm))

    story.append(Spacer(1, 0.3 * cm))
    story.append(
        P(
            "Não foram identificados achados de severidade crítica ou alta. Os achados de "
            "severidade média concentram-se em <b>defaults e guardas de configuração</b> "
            "(categoria 4) e em uma questão de <b>modelagem de privilégio</b> (categoria 2); "
            "nenhum deles é uma falha de autorização em produção — todos exigem uma condição "
            "operacional adicional (ex.: um operador pular a troca de um placeholder) para serem "
            "explorados. A categoria 5 (XSS) não produziu nenhum achado.",
            "CorpoJust",
        )
    )
    story.append(PageBreak())


def construir_pontos_fortes(story):
    story.append(P("Pontos fortes — o que está protegido, com evidência", "Titulo1"))
    story.append(
        P(
            "Lista o que foi verificado no código e está corretamente implementado. Esta seção "
            "existe tanto para orientar o time (o que <i>não</i> precisa ser mexido) quanto para "
            "demonstrar a cobertura desta auditoria — cada item aponta para o arquivo e a linha "
            "onde a proteção foi confirmada.",
            "CorpoJust",
        )
    )
    linhas = []
    for titulo, texto in D.PONTOS_FORTES:
        marca = Paragraph("&#10003;", styles["CorpoJust"])
        texto_par = Paragraph(f"<b>{titulo}.</b> {texto}", styles["CorpoJust"])
        linhas.append([marca, texto_par])
    tabela = Table(linhas, colWidths=[0.7 * cm, 16.3 * cm])
    tabela.setStyle(
        TableStyle(
            [
                ("TEXTCOLOR", (0, 0), (0, -1), COR["ponto_forte"]),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, CINZA_CLARO),
            ]
        )
    )
    story.append(tabela)
    story.append(PageBreak())


def construir_pontos_fracos(story):
    story.append(P("Pontos fracos — riscos centrais", "Titulo1"))
    story.append(
        P(
            "Síntese dos riscos identificados, em ordem de severidade. O detalhamento completo — "
            "arquivo, linha, trecho de código e explicação de exploração — está na seção "
            "\"Achados detalhados\" a seguir.",
            "CorpoJust",
        )
    )
    ordem_sev = {"critica": 0, "alta": 1, "media": 2, "baixa": 3, "informativa": 4}
    achados_ordenados = sorted(D.ACHADOS, key=lambda a: ordem_sev[a["severidade"]])
    linhas = [["Sev.", "ID", "Achado", "Arquivo"]]
    for a in achados_ordenados:
        linhas.append(
            [
                chip_severidade(a["severidade"]),
                a["id"],
                Paragraph(a["titulo"], styles["CorpoPequeno"]),
                Paragraph(a["arquivo"].replace(",", ",<br/>"), styles["CorpoPequeno"]),
            ]
        )
    tabela = Table(linhas, colWidths=[2.4 * cm, 1.1 * cm, 7.5 * cm, 5.7 * cm], repeatRows=1)
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INSTITUCIONAL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDA),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(tabela)
    story.append(PageBreak())


def construir_achados_detalhados(story):
    story.append(P("Achados detalhados por categoria", "Titulo1"))

    categorias_ordem = [
        "1. Isolamento por dono/organização",
        "2. Permissão no navegador vs. backend",
        "3. IDOR",
        "4. Chaves expostas",
        "5. Inputs sem tratamento (XSS)",
    ]
    por_categoria = {c: [] for c in categorias_ordem}
    for a in D.ACHADOS:
        por_categoria.setdefault(a["categoria"], []).append(a)

    ordem_sev = {"critica": 0, "alta": 1, "media": 2, "baixa": 3, "informativa": 4}

    for categoria in categorias_ordem:
        achados = sorted(por_categoria.get(categoria, []), key=lambda a: ordem_sev[a["severidade"]])
        story.append(P(categoria, "Titulo2"))
        if not achados:
            story.append(
                P(
                    "Nenhum achado nesta categoria. Ver seção \"Pontos fortes\" para as proteções "
                    "verificadas — nenhum uso de <font face=\"Courier\">|safe</font>, "
                    "<font face=\"Courier\">mark_safe</font> ou <font face=\"Courier\">format_html</font> "
                    "sobre conteúdo de usuário/administrador/LLM foi encontrado em todo o código-fonte.",
                    "CorpoJust",
                )
            )
            continue

        for a in achados:
            bloco = []
            cabecalho = Table(
                [[chip_severidade(a["severidade"]), P(f"<b>{a['id']} — {a['titulo']}</b>", "CorpoJust")]],
                colWidths=[2.4 * cm, 13.6 * cm],
            )
            cabecalho.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            bloco.append(cabecalho)
            bloco.append(linha_evidencia("Arquivo", a["arquivo"]))
            bloco.append(Spacer(1, 2))
            bloco.append(Paragraph(a["trecho"].replace("\n", "<br/>").replace(" ", "&nbsp;"), styles["Codigo"]))
            bloco.append(linha_evidencia("Por que é explorável", a["explicacao"]))
            bloco.append(linha_evidencia("Condição de exploração", a["exploitability"]))
            for rotulo, valor in a.get("evidencia_extra", []):
                bloco.append(linha_evidencia(rotulo, valor))
            bloco.append(Spacer(1, 8))
            story.append(KeepTogether(bloco))
    story.append(PageBreak())


def construir_recomendacoes(story):
    story.append(P("Recomendações priorizadas", "Titulo1"))
    linhas = [["Prior.", "Recomendação", "Referência"]]
    for prioridade, titulo, texto in D.RECOMENDACOES:
        linhas.append(
            [
                prioridade,
                Paragraph(f"<b>{titulo}.</b> {texto}", styles["CorpoPequeno"]),
                "",
            ]
        )
    tabela = Table(linhas, colWidths=[1.6 * cm, 14.9 * cm, 0.01 * cm], repeatRows=1)
    cores_prior = {"P1": colors.HexColor("#FEE2E2"), "P2": colors.HexColor("#FEF3C7"), "P3": colors.HexColor("#DBEAFE")}
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), INSTITUCIONAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("GRID", (0, 0), (1, -1), 0.4, BORDA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
    ]
    for i, (prioridade, _t, _x) in enumerate(D.RECOMENDACOES, start=1):
        estilo.append(("BACKGROUND", (0, i), (0, i), cores_prior.get(prioridade, colors.white)))
    tabela.setStyle(TableStyle(estilo))
    story.append(tabela)
    story.append(PageBreak())


def construir_issues_github(story):
    story.append(P("Issues para o GitHub", "Titulo1"))
    story.append(
        P(
            "Texto completo em Markdown, pronto para copiar e colar na criação de cada issue. "
            "Achados triviais e relacionados foram agrupados numa única issue quando fazia sentido, "
            "para não gerar spam.",
            "CorpoJust",
        )
    )
    for i, issue in enumerate(D.GITHUB_ISSUES, start=1):
        story.append(Spacer(1, 4))
        story.append(P(f"--- ISSUE {i} ---", "Titulo3"))
        story.append(linha_evidencia("Título", issue["titulo"]))
        story.append(linha_evidencia("Labels sugeridas", issue["labels"]))
        story.append(Spacer(1, 3))
        corpo_html = (
            issue["corpo"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
            .replace(" ", "&nbsp;")
        )
        story.append(Paragraph(corpo_html, styles["CodigoIssue"]))
        story.append(P(f"--- FIM ISSUE {i} ---", "Titulo3"))
        if i < len(D.GITHUB_ISSUES):
            story.append(PageBreak())


def main():
    doc = SimpleDocTemplate(
        OUT_PATH,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=NOME_RELATORIO,
        author="Auditoria de Segurança (Claude Code)",
    )

    frame_capa = Frame(
        0,
        0,
        A4[0],
        A4[1],
        leftPadding=2 * cm,
        rightPadding=2 * cm,
        topPadding=2 * cm,
        bottomPadding=2 * cm,
        id="capa",
    )
    frame_normal = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="normal",
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="capa", frames=[frame_capa], onPage=lambda c, d: None),
            PageTemplate(id="normal", frames=[frame_normal], onPage=_header_footer),
        ]
    )

    story = []
    construir_capa(story)
    construir_metodologia(story)
    construir_resumo_executivo(story)
    construir_pontos_fortes(story)
    construir_pontos_fracos(story)
    construir_achados_detalhados(story)
    construir_recomendacoes(story)
    construir_issues_github(story)

    doc.build(story)
    print(f"PDF gerado em: {OUT_PATH}")


if __name__ == "__main__":
    main()
