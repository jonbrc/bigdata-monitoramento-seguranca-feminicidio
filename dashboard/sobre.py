"""Aba "Sobre os dados" do dashboard: fontes, cobertura lida do banco, definição dos indicadores, regras de proteção de dados e limitações."""

import pandas as pd
import streamlit as st

import db
from filtros import Opcoes
from kpis import MINIMO_ESTAVEL, numero
from territorio import SUPRESSAO

REPOSITORIO = "https://github.com/jonbrc/bigdata-monitoramento-seguranca-feminicidio"
MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]

FONTES = pd.DataFrame([
    ("Sinesp VDE", "Ministério da Justiça e Segurança Pública", "Vítimas de feminicídio, tentativa de feminicídio, "
     "homicídio doloso, tentativa de homicídio, lesão corporal seguida de morte e latrocínio, por sexo",
     "Município da ocorrência × mês"),
    ("SIM", "Ministério da Saúde (DATASUS)", "Declarações de óbito com causa básica de agressão (CID-10 X85–Y09), "
     "com sexo, raça/cor, idade, local do óbito e meio da agressão", "Município de residência × mês"),
    ("Censo 2022", "IBGE (API de agregados, tabela 9606)", "População residente por sexo, idade e cor/raça",
     "Município"),
], columns=["Fonte", "Órgão", "O que usamos", "Unidade"])

INDICADORES = pd.DataFrame([
    ("Óbitos por 100 mil hab.", "óbitos por agressão ÷ população do mesmo recorte × 100 mil (× 12 ÷ meses, se o ano "
     "é parcial)", "SIM + Censo", "ODS 5 e 18"),
    ("Risco em relação à branca", "taxa do grupo ÷ taxa do grupo branco do mesmo sexo (1,91 = 91% mais risco)",
     "SIM + Censo", "ODS 18"),
    ("Gap interseccional", "risco de pessoas negras em relação às brancas, mostrado para mulheres e para homens",
     "SIM + Censo", "ODS 5 e 18"),
    ("% no domicílio", "óbitos ocorridos em casa ÷ total de óbitos do recorte", "SIM", "ODS 5"),
    ("Feminicídios por 100 mil mulheres", "vítimas de feminicídio ÷ população feminina × 100 mil", "Sinesp + Censo",
     "ODS 5"),
    ("Tipificadas como feminicídio", "feminicídios ÷ mortes violentas de mulheres registradas pela polícia",
     "Sinesp", "ODS 5"),
    ("Letalidade do feminicídio", "feminicídios ÷ (feminicídios + tentativas), sem as UFs que não registram "
     "tentativas", "Sinesp", "ODS 5"),
], columns=["Indicador", "Cálculo", "Fonte", "ODS"])


def _tabela(df: pd.DataFrame) -> str:
    linhas = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    linhas += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(linhas)


@st.cache_data(ttl=db.CACHE_SEGUNDOS, show_spinner=False)
def _cobertura() -> pd.DataFrame:
    return db.consultar("""
        WITH sim AS (SELECT ano, SUM(obitos) AS obitos, SUM(obitos) FILTER (WHERE sexo = 'feminino') AS obitos_fem
                     FROM vw_sim GROUP BY 1),
             sin AS (SELECT ano, SUM(vitimas_total) AS vitimas,
                            SUM(vitimas_fem) FILTER (WHERE evento = 'feminicidio') AS feminicidios
                     FROM vw_sinesp GROUP BY 1),
             t AS (SELECT ano, COUNT(*) FILTER (WHERE sim_periodo_coberto) AS meses_sim FROM dim_tempo GROUP BY 1)
        SELECT t.ano, t.meses_sim, sim.obitos, sim.obitos_fem, sin.vitimas, sin.feminicidios
        FROM t LEFT JOIN sim USING (ano) LEFT JOIN sin USING (ano) ORDER BY t.ano""")


def render(opcoes: Opcoes) -> None:
    st.markdown(
        "Este painel cruza o registro **policial** (Sinesp), o registro de **saúde** (SIM) e o **Censo 2022** para "
        "medir a violência letal sob a ótica interseccional de gênero × raça/cor, em apoio ao **ODS 5** (meta 5.2: "
        "eliminar a violência contra mulheres e meninas) e ao **ODS 18** (igualdade étnico-racial, ODS nacional). "
        f"Código, ETL e regras de negócio completas (RN01–RN22) estão no [repositório do projeto]({REPOSITORIO})."
    )

    st.markdown("#### Fontes")
    st.markdown(_tabela(FONTES))

    st.markdown("#### Cobertura no banco")
    try:
        cob = _cobertura()
    except Exception:
        st.caption("Não foi possível ler a cobertura agora.")
    else:
        linhas = [{
            "Ano": str(int(r["ano"])),
            "Meses do SIM": "janeiro a dezembro" if r["meses_sim"] == 12
            else f"janeiro a {MESES[int(r['meses_sim'])]} (preliminar)",
            "Óbitos por agressão (SIM)": numero(r["obitos"]),
            "… de mulheres": numero(r["obitos_fem"]),
            "Vítimas no recorte do Sinesp": numero(r["vitimas"]),
            "Feminicídios (Sinesp)": numero(r["feminicidios"]),
        } for _, r in cob.iterrows()]
        st.markdown(_tabela(pd.DataFrame(linhas)))

    st.markdown("#### Indicadores")
    st.markdown(_tabela(INDICADORES))
    st.caption("Raça/cor: Negra = preta + parda (padrão do IBGE). Raça/cor e idade ignoradas aparecem nas contagens, "
               "mas ficam fora das taxas e das razões, por não terem população correspondente.")

    st.markdown("#### Proteção de dados e estimativas instáveis")
    st.markdown(
        f"- **Células pequenas (RN22):** no nível de município, contagens de 1 ou {SUPRESSAO - 1} casos aparecem "
        f"como \"≤ {SUPRESSAO - 1}\" e taxas só são calculadas a partir de {MINIMO_ESTAVEL} casos. A regra é "
        "aplicada na consulta SQL, então esses valores nunca chegam ao navegador.\n"
        f"- **Estimativas instáveis (RN21):** valores baseados em menos de {MINIMO_ESTAVEL} casos aparecem "
        "hachurados, vazados ou com asterisco, e os cartões mostram um aviso.\n"
        "- **Sem dados pessoais:** as bases são públicas e agregadas; o painel acessa o banco com um usuário "
        "somente leitura."
    )

    st.markdown("#### Limitações")
    anos_parciais = [a for a, m in opcoes.anos.items() if m < 12]
    parcial = (f"O SIM de {', '.join(map(str, anos_parciais))} é preliminar e o último mês está incompleto; as taxas "
               "são anualizadas. " if anos_parciais else "")
    st.markdown(
        f"- {parcial}O Sinesp de cada ano cobre os 12 meses.\n"
        "- O SIM localiza o óbito pelo município de **residência**; o Sinesp, pelo município da **ocorrência**.\n"
        "- O Sinesp não traz raça/cor nem idade: os indicadores policiais seguem só os filtros de ano e território.\n"
        "- O denominador é o Censo 2022 para os dois anos (não há estimativa oficial por raça/cor para 2024–2025).\n"
        "- Feminicídio depende da tipificação policial, que varia entre UFs e pode ser revista depois do registro.\n"
        "- Estupro e estupro de vulnerável ficam de fora: o Sinesp só os divulga agregados por UF."
    )
