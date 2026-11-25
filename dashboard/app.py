"""Dashboard Streamlit do projeto: violência letal e feminicídio sob a ótica interseccional de gênero × raça/cor (ODS 5 e 18), a partir das views do schema dw."""

import streamlit as st

import db
import filtros
import graficos
import kpis
import territorio

st.set_page_config(
    page_title="Feminicídio e Violência Interseccional",
    page_icon="📊",
    layout="wide",
)


def falhar(erro: Exception) -> None:
    if isinstance(erro, db.ConfiguracaoAusente):
        st.error(
            f"Credenciais do banco não encontradas ({erro}). Preencha o `.env` na raiz do projeto "
            "ou os Secrets do Streamlit (modelo em `dashboard/secrets.toml.example`)."
        )
    else:
        st.error(
            "Não foi possível consultar o banco. No plano gratuito do Aiven o serviço é desligado após "
            "um período sem uso: confira no console se ele está **Running** e recarregue a página."
        )
        with st.expander("Detalhes técnicos"):
            st.code(str(erro))
    st.stop()


st.title("Violência letal e feminicídio no Brasil")
st.caption(
    "Gênero × raça/cor · Sinesp (MJSP), SIM (Ministério da Saúde) e Censo 2022 (IBGE) · "
    "ODS 5 (Igualdade de Gênero) e ODS 18 (Igualdade Étnico-Racial)"
)

try:
    opcoes = filtros.carregar_opcoes()
except Exception as erro:
    falhar(erro)

f = filtros.barra_lateral(opcoes)
st.markdown(f"**Recorte:** {f.resumo(opcoes)}")

MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]
if f.sim_parcial:
    st.warning(
        f"O SIM de {f.ano} é preliminar e cobre só janeiro a {MESES[f.meses_sim]}. As taxas do SIM são "
        f"anualizadas (× 12 ÷ {f.meses_sim}), mas o último mês ainda está incompleto: a comparação com o "
        "ano anterior tende a subestimar o ano corrente.",
        icon="⚠️",
    )

where_sim, params_sim = f.where()
try:
    sim = db.consultar(
        f"SELECT COALESCE(SUM(obitos), 0) AS obitos, COALESCE(SUM(populacao), 0) AS populacao "
        f"FROM vw_taxa_sim_uf WHERE {where_sim}", tuple(params_sim)).iloc[0]
except Exception as erro:
    falhar(erro)

if sim["populacao"] == 0 and sim["obitos"] == 0:
    st.info(
        "Nenhum dado para essa combinação de filtros. Amplie o recorte (por exemplo, remova uma "
        "faixa etária ou um grupo racial) ou use **Limpar filtros** na barra lateral.",
        icon="🔍",
    )
    st.stop()

try:
    interseccionais, policiais = kpis.calcular(f, opcoes.anos)
except Exception as erro:
    falhar(erro)


CSS_CARTOES = """
<style>
[data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] div { white-space: normal !important; }
[data-testid="stMetricValue"] { font-size: clamp(1.15rem, 2.2vw, 2.1rem); }
[data-testid="stMetricValue"] div { overflow: visible !important; text-overflow: clip !important; }
</style>
"""
st.markdown(CSS_CARTOES, unsafe_allow_html=True)


def cartoes(lista: list[kpis.Kpi], larguras: list[float] | None = None) -> None:
    for coluna, k in zip(st.columns(larguras or len(lista)), lista):
        with coluna.container(border=True):
            st.metric(k.titulo, k.valor, delta=k.delta, delta_color=k.delta_cor, help=k.ajuda)
            st.caption(k.legenda)
            if k.alerta:
                st.caption(f":orange[⚠️ {k.alerta}]")


st.subheader("Gênero × raça/cor · óbitos por agressão (SIM)")
cartoes(interseccionais, [1, 1, 1.25, 1])

st.subheader("Feminicídio · registros policiais (Sinesp)")
cartoes(policiais)
if f.sexo != "todos" or f.grupos or f.faixas:
    st.caption("O Sinesp não traz raça/cor nem idade: estes indicadores seguem só os filtros de ano e território.")

st.subheader("Comparativo interseccional · óbitos por agressão (SIM)")
try:
    graficos.render(f)
except Exception as erro:
    falhar(erro)

st.subheader("Território")
try:
    territorio.render(f, opcoes)
except Exception as erro:
    falhar(erro)

with st.sidebar:
    st.divider()
    st.caption(
        "Painel do projeto prático de **Big Data & Analytics** (UCSal). Dados do PostgreSQL no Aiven "
        "(schema `dw`), carregado pelo ETL do repositório."
    )
