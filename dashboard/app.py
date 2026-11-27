"""Dashboard Streamlit do projeto: violência letal e feminicídio sob a ótica interseccional de gênero × raça/cor (ODS 5 e 18), a partir das views do schema dw."""

import streamlit as st

import db
import filtros
import graficos
import kpis
import layout
import perfil
import policia_saude
import sobre
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


layout.aplicar_estilo()

try:
    opcoes = filtros.carregar_opcoes()
except Exception as erro:
    falhar(erro)

f = filtros.barra_lateral(opcoes)

MESES = ["", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
alerta = None
if f.sim_parcial:
    alerta = (f"SIM {f.ano} preliminar · jan–{MESES[f.meses_sim]}",
              f"O SIM de {f.ano} cobre só janeiro a {MESES[f.meses_sim]}. As taxas do SIM são anualizadas "
              f"(× 12 ÷ {f.meses_sim}), mas o último mês ainda está incompleto: a comparação com o ano anterior "
              "tende a subestimar o ano corrente.")
layout.cabecalho(
    "Violência letal e feminicídio no Brasil",
    "Gênero × raça/cor · Sinesp, SIM e Censo 2022 · ODS 5 e ODS 18",
    f.resumo(opcoes).split(" · "),
    alerta,
)

abas = st.tabs(["Visão geral", "Perfil da violência", "Território", "Polícia × saúde", "Sobre os dados"])
with abas[4]:
    sobre.render(opcoes)

where_sim, params_sim = f.where()
try:
    sim = db.consultar(
        f"SELECT COALESCE(SUM(obitos), 0) AS obitos, COALESCE(SUM(populacao), 0) AS populacao "
        f"FROM vw_taxa_sim_uf WHERE {where_sim}", tuple(params_sim)).iloc[0]
except Exception as erro:
    falhar(erro)

if sim["populacao"] == 0 and sim["obitos"] == 0:
    for aba in abas[:4]:
        aba.info(
            "Nenhum dado para essa combinação de filtros. Amplie o recorte ou use **Limpar filtros** na barra lateral.",
            icon="🔍",
        )
    st.stop()

try:
    interseccionais, policiais = kpis.calcular(f, opcoes.anos)
except Exception as erro:
    falhar(erro)


def visao_geral() -> None:
    layout.linha_kpis(interseccionais, "SIM", [1, 1, 1.3, 1])
    st.write("")
    layout.linha_kpis(policiais, "SINESP")
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        graficos.render(f, altura=380)
    with c2:
        perfil.bloco_evolucao(f, altura=380)


abas_dados = [
    (abas[0], visao_geral),
    (abas[1], lambda: perfil.render(f)),
    (abas[2], lambda: territorio.render(f, opcoes)),
    (abas[3], lambda: policia_saude.render(f, opcoes)),
]
for aba, desenhar in abas_dados:
    with aba:
        try:
            desenhar()
        except Exception as erro:
            falhar(erro)

with st.sidebar:
    st.divider()
    st.caption(
        "Painel do projeto prático de **Big Data & Analytics** (UCSal). Dados do PostgreSQL no Aiven "
        "(schema `dw`), carregado pelo ETL do repositório."
    )
