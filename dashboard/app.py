"""Dashboard Streamlit do projeto: violência letal e feminicídio sob a ótica interseccional de gênero × raça/cor (ODS 5 e 18), a partir das views do schema dw."""

import streamlit as st

import db

st.set_page_config(
    page_title="Feminicídio e Violência Interseccional",
    page_icon="📊",
    layout="wide",
)


def formatar(n) -> str:
    return f"{int(n):,}".replace(",", ".")


st.title("Violência letal e feminicídio no Brasil")
st.caption(
    "Gênero × raça/cor · Sinesp (MJSP), SIM (Ministério da Saúde) e Censo 2022 (IBGE) · "
    "ODS 5 (Igualdade de Gênero) e ODS 18 (Igualdade Étnico-Racial)"
)

try:
    resumo = db.consultar("""
        SELECT (SELECT SUM(vitimas_total) FROM fato_ocorrencia_sinesp) AS vitimas_sinesp,
               (SELECT SUM(obitos)        FROM fato_obito_sim)         AS obitos_sim,
               (SELECT SUM(populacao)     FROM fato_populacao)         AS populacao,
               (SELECT COUNT(DISTINCT codigo_ibge) FROM dim_municipio) AS municipios,
               (SELECT STRING_AGG(DISTINCT ano::text, ', ' ORDER BY ano::text) FROM dim_tempo) AS anos
    """)
except db.ConfiguracaoAusente as erro:
    st.error(
        f"Credenciais do banco não encontradas ({erro}). Preencha o `.env` na raiz do projeto "
        "ou os Secrets do Streamlit (modelo em `dashboard/secrets.toml.example`)."
    )
    st.stop()
except Exception as erro:
    st.error(
        "Não foi possível consultar o banco. No plano gratuito do Aiven o serviço é desligado após "
        "um período sem uso: confira no console se ele está **Running** e recarregue a página."
    )
    with st.expander("Detalhes técnicos"):
        st.code(str(erro))
    st.stop()

r = resumo.iloc[0]
st.subheader("Base de dados carregada")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Vítimas registradas (Sinesp)", formatar(r["vitimas_sinesp"]))
c2.metric("Óbitos por agressão (SIM)", formatar(r["obitos_sim"]))
c3.metric("População (Censo 2022)", formatar(r["populacao"]))
c4.metric("Municípios", formatar(r["municipios"]))
st.caption(f"Anos disponíveis: {r['anos']}. Os filtros e indicadores são adicionados nas próximas etapas.")

with st.sidebar:
    st.header("Sobre")
    st.markdown(
        "Painel do projeto prático de **Big Data & Analytics** (UCSal).\n\n"
        "Os dados vêm do PostgreSQL no Aiven (schema `dw`), carregado pelo ETL do repositório."
    )
