"""Dashboard Streamlit do projeto: violência letal e feminicídio sob a ótica interseccional de gênero × raça/cor (ODS 5 e 18), a partir das views do schema dw."""

import streamlit as st

import db
import filtros

st.set_page_config(
    page_title="Feminicídio e Violência Interseccional",
    page_icon="📊",
    layout="wide",
)


def formatar(n) -> str:
    return f"{int(n or 0):,}".replace(",", ".")


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

if f.sim_parcial:
    st.warning(
        f"O SIM de {f.ano} é preliminar e cobre só {f.meses_sim} meses (janeiro a "
        f"{['', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'][f.meses_sim]}). "
        "Os números do SIM não são comparáveis diretamente com os de um ano completo; "
        "use as taxas anualizadas.",
        icon="⚠️",
    )

where_sim, params_sim = f.where()
where_sinesp, params_sinesp = f.where(perfil=False)
try:
    sim = db.consultar(
        f"SELECT COALESCE(SUM(obitos), 0) AS obitos, COALESCE(SUM(populacao), 0) AS populacao "
        f"FROM vw_taxa_sim_uf WHERE {where_sim}", tuple(params_sim)).iloc[0]
    municipios = db.consultar(
        f"SELECT COUNT(DISTINCT codigo_ibge) AS n FROM vw_sim WHERE {where_sim}", tuple(params_sim)).iloc[0]
    sinesp = db.consultar(
        f"SELECT COALESCE(SUM(feminicidios), 0) AS feminicidios, "
        f"COALESCE(SUM(mortes_violentas_fem), 0) AS mortes_violentas_fem "
        f"FROM vw_kpi_uf WHERE {where_sinesp}", tuple(params_sinesp)).iloc[0]
except Exception as erro:
    falhar(erro)

if sim["populacao"] == 0 and sim["obitos"] == 0:
    st.info(
        "Nenhum dado para essa combinação de filtros. Amplie o recorte (por exemplo, remova uma "
        "faixa etária ou um grupo racial) ou use **Limpar filtros** na barra lateral.",
        icon="🔍",
    )
    st.stop()

st.subheader("Registros de saúde (SIM)")
c1, c2, c3 = st.columns(3)
c1.metric("Óbitos por agressão", formatar(sim["obitos"]))
c2.metric("População do recorte (Censo 2022)", formatar(sim["populacao"]))
c3.metric("Municípios com óbito", formatar(municipios["n"]))

st.subheader("Registros policiais (Sinesp)")
c1, c2, _ = st.columns(3)
c1.metric("Feminicídios", formatar(sinesp["feminicidios"]))
c2.metric("Mortes violentas de mulheres", formatar(sinesp["mortes_violentas_fem"]),
          help="Feminicídio + homicídio doloso + lesão corporal seguida de morte + latrocínio (RN05).")
if f.sexo != "todos" or f.grupos or f.faixas:
    st.caption("O Sinesp não traz raça/cor nem idade: estes números seguem só os filtros de ano e território.")

st.caption("Os indicadores (taxas, razões de risco e percentuais) são adicionados nas próximas etapas.")

with st.sidebar:
    st.divider()
    st.caption(
        "Painel do projeto prático de **Big Data & Analytics** (UCSal). Dados do PostgreSQL no Aiven "
        "(schema `dw`), carregado pelo ETL do repositório."
    )
