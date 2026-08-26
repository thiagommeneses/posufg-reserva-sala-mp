#!/usr/bin/env python3
"""Valida e renderiza um story map em YAML (fase 2 da skill spec-driven-ux).

Uso:
    python storymap.py validar mapa.yaml
    python storymap.py md mapa.yaml -o mapa.md
    python storymap.py html mapa.yaml -o mapa.html

Requer PyYAML (pip install pyyaml).

O validador procura os defeitos que passam despercebidos na leitura:
IDs duplicados ou fora de padrão, história sem fatia ou sem resultado,
referência a fatia/resultado/hipótese inexistente, passo sem história,
fatia vazia e ausência (ou excesso) de esqueleto ambulante.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML não encontrado. Instale com: pip install pyyaml")

PADROES = {
    "resultado": re.compile(r"^OUT-\d{2,}$"),
    "fatia": re.compile(r"^FAT-\d{2,}$"),
    "atividade": re.compile(r"^ACT-\d{2,}$"),
    "passo": re.compile(r"^STP-\d{2,}\.\d{2,}$"),
    "historia": re.compile(r"^US-\d{3,}$"),
    "hipotese": re.compile(r"^H-\d{2,}$"),
}

ESTADOS = {"descoberta", "pronta", "em-entrega", "medindo", "descartada"}


def carregar(caminho: Path) -> dict:
    with caminho.open(encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    if not isinstance(dados, dict):
        raise SystemExit("O arquivo não contém um mapa válido (esperado um objeto YAML).")
    return dados


def iter_historias(mapa: dict):
    """Percorre o mapa devolvendo (atividade, passo, historia)."""
    for atividade in mapa.get("atividades") or []:
        for passo in atividade.get("passos") or []:
            for historia in passo.get("historias") or []:
                yield atividade, passo, historia


def validar(mapa: dict) -> tuple[list[str], list[str]]:
    erros: list[str] = []
    avisos: list[str] = []

    resultados = {r.get("id") for r in mapa.get("resultados") or []}
    fatias = {f.get("id"): f for f in mapa.get("fatias") or []}
    hipoteses = {h.get("id") for h in mapa.get("hipoteses") or []}

    if not resultados:
        erros.append("Nenhum resultado (OUT-xx) declarado: sem resultado não há como priorizar.")
    if not fatias:
        erros.append("Nenhuma fatia declarada: o mapa não está fatiado.")

    vistos: dict[str, str] = {}

    def registrar(id_: str | None, tipo: str, onde: str) -> None:
        if not id_:
            erros.append(f"{onde}: item sem 'id'.")
            return
        if id_ in vistos:
            erros.append(f"ID duplicado: {id_} (usado em {vistos[id_]} e em {onde}).")
        else:
            vistos[id_] = onde
        padrao = PADROES.get(tipo)
        if padrao and not padrao.match(id_):
            avisos.append(f"{id_}: fora do padrão esperado para {tipo} ({padrao.pattern}).")

    for resultado in mapa.get("resultados") or []:
        registrar(resultado.get("id"), "resultado", "resultados")
        if not resultado.get("metrica"):
            avisos.append(f"{resultado.get('id')}: sem métrica — não será possível dizer se aconteceu.")

    for hipotese in mapa.get("hipoteses") or []:
        registrar(hipotese.get("id"), "hipotese", "hipoteses")

    usadas_por_fatia: dict[str, list[str]] = {fid: [] for fid in fatias}
    esqueletos: list[str] = []

    for fid, fatia in fatias.items():
        registrar(fid, "fatia", "fatias")
        ref = fatia.get("resultado")
        if not ref:
            erros.append(f"{fid}: fatia sem resultado associado.")
        elif ref not in resultados:
            erros.append(f"{fid}: referencia resultado inexistente ({ref}).")
        if fatia.get("esqueleto_ambulante"):
            esqueletos.append(fid)
        if not fatia.get("objetivo_aprendizado"):
            avisos.append(f"{fid}: sem objetivo de aprendizado declarado.")

    if len(esqueletos) == 0:
        avisos.append("Nenhuma fatia marcada como esqueleto ambulante (esqueleto_ambulante: true).")
    elif len(esqueletos) > 1:
        avisos.append(f"Mais de uma fatia marcada como esqueleto ambulante: {', '.join(esqueletos)}.")

    for atividade in mapa.get("atividades") or []:
        aid = atividade.get("id")
        registrar(aid, "atividade", "atividades")
        passos = atividade.get("passos") or []
        if not passos:
            erros.append(f"{aid}: atividade sem passos.")
        for passo in passos:
            pid = passo.get("id")
            registrar(pid, "passo", f"atividade {aid}")
            historias = passo.get("historias") or []
            if not historias:
                avisos.append(f"{pid}: passo sem histórias (órfão no mapa).")
            for historia in historias:
                hid = historia.get("id")
                registrar(hid, "historia", f"passo {pid}")
                fatia_ref = historia.get("fatia")
                if not fatia_ref:
                    erros.append(f"{hid}: história sem fatia.")
                elif fatia_ref not in fatias:
                    erros.append(f"{hid}: referencia fatia inexistente ({fatia_ref}).")
                else:
                    usadas_por_fatia[fatia_ref].append(hid)
                res_ref = historia.get("resultado")
                if not res_ref:
                    erros.append(f"{hid}: história sem resultado (OUT) associado.")
                elif res_ref not in resultados:
                    erros.append(f"{hid}: referencia resultado inexistente ({res_ref}).")
                estado = historia.get("estado")
                if estado and estado not in ESTADOS:
                    avisos.append(f"{hid}: estado '{estado}' fora de {sorted(ESTADOS)}.")
                if not historia.get("para"):
                    avisos.append(f"{hid}: sem o 'para' (benefício) — verifique se a história tem propósito claro.")
                for h_ref in historia.get("hipoteses") or []:
                    if h_ref not in hipoteses:
                        avisos.append(f"{hid}: referencia hipótese inexistente ({h_ref}).")

    for fid, historias in usadas_por_fatia.items():
        if not historias:
            erros.append(f"{fid}: fatia sem nenhuma história.")

    return erros, avisos


def render_md(mapa: dict) -> str:
    linhas: list[str] = []
    ad = linhas.append
    ad(f"# Story Map — {mapa.get('produto', '[produto]')}")
    ad("")
    ad(f"Versão {mapa.get('versao', '-')} · atualizado em {mapa.get('atualizado_em', '-')}")
    ad("")

    ad("## Resultados")
    ad("")
    ad("| ID | Resultado | Métrica |")
    ad("|---|---|---|")
    for r in mapa.get("resultados") or []:
        ad(f"| {r.get('id', '')} | {r.get('descricao', '')} | {r.get('metrica', '')} |")
    ad("")

    atividades = mapa.get("atividades") or []
    ad("## Espinha dorsal")
    ad("")
    ad("| " + " | ".join(f"{a.get('id')} {a.get('nome', '')}" for a in atividades) + " |")
    ad("|" + "---|" * max(len(atividades), 1))
    altura = max((len(a.get("passos") or []) for a in atividades), default=0)
    for i in range(altura):
        celulas = []
        for a in atividades:
            passos = a.get("passos") or []
            celulas.append(f"{passos[i].get('id')} {passos[i].get('nome', '')}" if i < len(passos) else "")
        ad("| " + " | ".join(celulas) + " |")
    ad("")

    ad("## Fatias")
    ad("")
    for f in mapa.get("fatias") or []:
        marca = " *(esqueleto ambulante)*" if f.get("esqueleto_ambulante") else ""
        ad(f"### {f.get('id')} — {f.get('nome', '')}{marca}")
        ad("")
        ad(f"- Resultado: {f.get('resultado', '-')}")
        if f.get("objetivo_aprendizado"):
            ad(f"- Aprendizado buscado: {f['objetivo_aprendizado']}")
        ad("")
        ad("| Atividade | Passo | História | Estado |")
        ad("|---|---|---|---|")
        for atividade, passo, historia in iter_historias(mapa):
            if historia.get("fatia") == f.get("id"):
                ad(
                    f"| {atividade.get('id')} | {passo.get('id')} | "
                    f"{historia.get('id')} {historia.get('titulo', '')} | {historia.get('estado', '-')} |"
                )
        ad("")

    hipoteses = mapa.get("hipoteses") or []
    if hipoteses:
        ad("## Hipóteses abertas")
        ad("")
        ad("| ID | Hipótese | Risco | Experimento |")
        ad("|---|---|---|---|")
        for h in hipoteses:
            ad(f"| {h.get('id')} | {h.get('descricao', '')} | {h.get('risco', '-')} | {h.get('experimento', '-')} |")
        ad("")

    fora = mapa.get("fora_de_escopo") or []
    if fora:
        ad("## Deliberadamente fora de escopo")
        ad("")
        for item in fora:
            ad(f"- {item}")
        ad("")

    return "\n".join(linhas)


def render_html(mapa: dict) -> str:
    e = html.escape
    fatias = mapa.get("fatias") or []
    atividades = mapa.get("atividades") or []

    colunas = []
    for atividade in atividades:
        passos_html = []
        for passo in atividade.get("passos") or []:
            historias_por_fatia = {
                f.get("id"): [h for h in (passo.get("historias") or []) if h.get("fatia") == f.get("id")]
                for f in fatias
            }
            linhas_fatia = []
            for f in fatias:
                itens = historias_por_fatia.get(f.get("id")) or []
                cartoes = "".join(
                    f'<div class="hist"><b>{e(str(h.get("id")))}</b> {e(str(h.get("titulo", "")))}'
                    f'<span class="est">{e(str(h.get("estado", "")))}</span></div>'
                    for h in itens
                )
                linhas_fatia.append(f'<div class="faixa" data-fatia="{e(str(f.get("id")))}">{cartoes}</div>')
            passos_html.append(
                f'<div class="passo"><div class="passo-nome">{e(str(passo.get("id")))} '
                f'{e(str(passo.get("nome", "")))}</div>{"".join(linhas_fatia)}</div>'
            )
        colunas.append(
            f'<div class="coluna"><div class="atividade">{e(str(atividade.get("id")))} '
            f'{e(str(atividade.get("nome", "")))}</div>{"".join(passos_html)}</div>'
        )

    legenda = "".join(
        f'<li><b>{e(str(f.get("id")))}</b> {e(str(f.get("nome", "")))}'
        f'{" — esqueleto ambulante" if f.get("esqueleto_ambulante") else ""}</li>'
        for f in fatias
    )

    return f"""<!doctype html>
<html lang="pt-BR"><meta charset="utf-8">
<title>Story Map — {e(str(mapa.get('produto', '')))}</title>
<style>
 body{{font:14px/1.45 system-ui,sans-serif;margin:24px;color:#1a1a1a}}
 h1{{font-size:20px;margin:0 0 4px}} .meta{{color:#666;margin-bottom:20px}}
 .mapa{{display:flex;gap:12px;align-items:flex-start;overflow-x:auto;padding-bottom:12px}}
 .coluna{{min-width:230px;flex:1}}
 .atividade{{background:#2f3e46;color:#fff;padding:8px 10px;border-radius:6px;font-weight:600}}
 .passo{{margin-top:8px;border:1px solid #dcdcdc;border-radius:6px;overflow:hidden}}
 .passo-nome{{background:#f2f2f2;padding:6px 8px;font-weight:600;font-size:13px}}
 .faixa{{border-top:1px dashed #d0d0d0;padding:6px;min-height:14px}}
 .hist{{background:#fffbe6;border:1px solid #e8dca0;border-radius:4px;padding:6px;margin:4px 0;font-size:13px}}
 .est{{display:block;color:#777;font-size:11px;text-transform:uppercase;letter-spacing:.04em}}
 ul{{padding-left:18px}}
</style>
<h1>Story Map — {e(str(mapa.get('produto', '')))}</h1>
<div class="meta">Versão {e(str(mapa.get('versao', '-')))} · atualizado em {e(str(mapa.get('atualizado_em', '-')))}</div>
<div class="mapa">{''.join(colunas)}</div>
<h2>Fatias (de cima para baixo dentro de cada passo)</h2>
<ul>{legenda}</ul>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida e renderiza story maps em YAML.")
    parser.add_argument("comando", choices=["validar", "md", "html"])
    parser.add_argument("arquivo", type=Path)
    parser.add_argument("-o", "--saida", type=Path, help="arquivo de saída (padrão: stdout)")
    args = parser.parse_args()

    mapa = carregar(args.arquivo)

    if args.comando == "validar":
        erros, avisos = validar(mapa)
        for erro in erros:
            print(f"ERRO   {erro}")
        for aviso in avisos:
            print(f"AVISO  {aviso}")
        if not erros and not avisos:
            print("OK — mapa válido, sem avisos.")
        else:
            print(f"\n{len(erros)} erro(s), {len(avisos)} aviso(s).")
        return 1 if erros else 0

    conteudo = render_md(mapa) if args.comando == "md" else render_html(mapa)
    if args.saida:
        args.saida.write_text(conteudo, encoding="utf-8")
        print(f"Gerado: {args.saida}")
    else:
        print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
