"""Identidade visual do dashboard no estilo de painel de BI: estilos globais, cabeçalho com o recorte, cartões de gráfico com título e nota em tooltip, e blocos de KPI."""

import html
from contextlib import contextmanager

import streamlit as st

CSS = """
<style>
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #eaeaea; }
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp input, .kpi, .topo,
.stApp span:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded) {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; }
.block-container { padding-top: 3rem; padding-bottom: 2rem; max-width: 1500px; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { border-right: 1px solid #d0d0d0; }

.topo { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap;
        background: #12355b; color: #ffffff; padding: 0.7rem 1rem; margin-bottom: 0.5rem;
        border-bottom: 3px solid #e8a33d; }
.topo h1 { font-size: 1.25rem; font-weight: 600; margin: 0; padding: 0; color: #ffffff; line-height: 1.25; }
.topo .sub { font-size: 0.78rem; color: #c9d6e6; margin-top: 0.1rem; }
.recorte { font-size: 0.8rem; color: #e6edf5; text-align: right; }
.recorte b { color: #ffffff; font-weight: 600; }
.recorte .alerta { display: block; color: #f5c66b; font-weight: 600; cursor: help; margin-top: 0.15rem; }

.stTabs [role="tablist"] { gap: 0; border-bottom: 1px solid #c8c8c8 !important; box-shadow: none !important; }
.stTabs [role="tab"] { background: #f3f2f1; border: 1px solid #c8c8c8; border-bottom: none; border-radius: 0;
                       padding: 0.35rem 1rem !important; height: auto; margin-right: -1px; }
.stTabs [role="tab"] p { color: #605e5c; }
.stTabs [role="tab"][aria-selected="true"] { background: #ffffff; box-shadow: inset 0 3px 0 #12355b; }
.stTabs [role="tab"][aria-selected="true"] p { color: #252423 !important; font-weight: 600; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

div[class*="st-key-card_"] { background: #ffffff; border: 1px solid #d6d6d6 !important; border-radius: 2px;
                             box-shadow: none; padding: 0.6rem 0.8rem 0.4rem 0.8rem; }
div[class*="st-key-card_"] [data-testid="stMarkdownContainer"] p { margin-bottom: 0.1rem; }
.card-titulo { font-size: 0.9rem; font-weight: 600; color: #252423; }

.kpi { background: #ffffff; border: 1px solid #d6d6d6; border-radius: 2px; padding: 0.55rem 0.7rem 0.5rem;
       height: 100%; text-align: center; cursor: help; margin-bottom: 0.5rem; }
.kpi-v { font-size: 1.9rem; font-weight: 600; color: #252423; line-height: 1.1; white-space: nowrap; }
.kpi-t { font-size: 0.8rem; color: #605e5c; line-height: 1.25; margin-top: 0.2rem; }
.kpi-rodape { display: flex; gap: 0.5rem; justify-content: center; align-items: center; margin-top: 0.2rem;
              min-height: 1.05rem; font-size: 0.74rem; }
.kpi-d { font-weight: 600; white-space: nowrap; }
.kpi-d.ruim { color: #a4262c; } .kpi-d.bom { color: #107c10; } .kpi-d.neutro { color: #605e5c; }
.kpi-alerta { color: #a35a00; font-weight: 600; white-space: nowrap; }
.kpi-s { font-size: 0.68rem; color: #8a8886; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
         margin-top: 0.15rem; }
.kpi-fonte { font-weight: 600; color: var(--cor); }
</style>
"""

COR_SIM = "#4b3fb8"
COR_SINESP = "#a36a00"


def aplicar_estilo() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def cabecalho(titulo: str, subtitulo: str, chips: list[str], alerta: tuple[str, str] | None = None) -> None:
    recorte = " | ".join(html.escape(c) for c in chips)
    aviso = ""
    if alerta:
        rotulo, detalhe = alerta
        aviso = f'<span class="alerta" title="{html.escape(detalhe)}">⚠ {html.escape(rotulo)}</span>'
    st.markdown(
        f'<div class="topo"><div><h1>{html.escape(titulo)}</h1><div class="sub">{html.escape(subtitulo)}</div></div>'
        f'<div class="recorte"><b>Recorte:</b> {recorte}{aviso}</div></div>',
        unsafe_allow_html=True,
    )


@contextmanager
def cartao(chave: str, titulo: str | None = None, nota: str | None = None):
    with st.container(border=True, key=f"card_{chave}"):
        if titulo:
            st.markdown(f'<span class="card-titulo">{html.escape(titulo)}</span>', unsafe_allow_html=True,
                        help=nota)
        yield


def _classe_delta(delta: str, modo: str) -> str:
    if modo == "off" or not delta:
        return "neutro"
    subiu = delta.lstrip().startswith("+")
    caiu = delta.lstrip().startswith(("-", "−"))
    if not (subiu or caiu):
        return "neutro"
    piorou = subiu if modo == "inverse" else caiu
    return "ruim" if piorou else "bom"


def kpi(k, fonte: str) -> None:
    cor = COR_SIM if fonte == "SIM" else COR_SINESP
    dica = f"{k.legenda}\n\n{k.ajuda}" + (f"\n\n⚠ {k.alerta}" if k.alerta else "")
    delta = (f'<span class="kpi-d {_classe_delta(k.delta, k.delta_cor)}">{html.escape(k.delta)}</span>'
             if k.delta else "")
    alerta = '<span class="kpi-alerta">⚠ instável</span>' if k.alerta else ""
    nome_fonte = "SIM" if fonte == "SIM" else "Sinesp"
    st.markdown(
        f'<div class="kpi" style="--cor:{cor}" title="{html.escape(dica).replace(chr(10), "&#10;")}">'
        f'<div class="kpi-v">{html.escape(k.valor)}</div>'
        f'<div class="kpi-t">{html.escape(k.titulo)}</div>'
        f'<div class="kpi-rodape">{delta}{alerta}</div>'
        f'<div class="kpi-s"><span class="kpi-fonte">{nome_fonte}</span> · {html.escape(k.legenda)}</div></div>',
        unsafe_allow_html=True,
    )


def linha_kpis(lista, fonte: str, larguras: list[float] | None = None) -> None:
    for coluna, k in zip(st.columns(larguras or len(lista), gap="small"), lista):
        with coluna:
            kpi(k, fonte)
