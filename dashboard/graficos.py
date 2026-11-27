"""Gráfico principal do dashboard: comparativo interseccional com seletor de métrica (contagem, taxa, risco racial, % do total) e de eixo (raça/cor, sexo, faixa etária), com marcação de estimativas instáveis e tabela de apoio."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db
from filtros import Filtros
from kpis import MINIMO_ESTAVEL, numero
from layout import cartao

CORES_GRUPO = {"Branca": "#2a78d6", "Negra": "#eb6834", "Indígena": "#1baf7a",
               "Amarela": "#eda100", "Ignorada": "#9b9a95"}
CORES_SEXO = {"Mulheres": "#6250d6", "Homens": "#008300"}
ORDEM_GRUPO = list(CORES_GRUPO)
SEXO_ROTULO = {"feminino": "Mulheres", "masculino": "Homens"}

METRICAS = {
    "taxa": "Taxa",
    "razao": "Risco vs. branca",
    "contagem": "Óbitos",
    "pct": "%",
}
EIXOS = {"grupo": "Raça/cor", "sexo": "Sexo", "faixa": "Idade"}


def _dados(f: Filtros) -> pd.DataFrame:
    where, params = f.where(ignorar=("grupo",))
    df = db.consultar(
        "SELECT sexo, grupo_racial, faixa_etaria, faixa_ordem, SUM(obitos) AS obitos, "
        "SUM(populacao) AS populacao, MAX(meses_cobertos) AS meses "
        f"FROM vw_taxa_sim_uf WHERE {where} "
        "GROUP BY sexo, grupo_racial, faixa_etaria, faixa_ordem",
        tuple(params),
    )
    df["sexo"] = df["sexo"].map(SEXO_ROTULO)
    return df.astype({"obitos": "int64", "populacao": "int64", "meses": "int64", "faixa_ordem": "int64"})


def _faixas_rotulos() -> dict[str, str]:
    d = db.consultar("SELECT codigo, descricao FROM dim_faixa_etaria ORDER BY ordem")
    return dict(zip(d["codigo"], d["descricao"]))


def preparar(df: pd.DataFrame, f: Filtros, eixo: str, metrica: str) -> tuple[pd.DataFrame, str, str]:
    dims = {"grupo": ("grupo_racial", "sexo"), "sexo": ("sexo", "grupo_racial"),
            "faixa": ("faixa_etaria", "grupo_racial")}
    x, serie = dims[eixo]
    meses = int(df["meses"].max()) if len(df) else 12
    t = df.groupby([x, serie], as_index=False)[["obitos", "populacao"]].sum()
    t["taxa"] = t["obitos"] * 100000 / t["populacao"].where(t["populacao"] > 0) * 12 / meses

    chave_ref = serie if eixo == "grupo" else x
    ref = t[t["grupo_racial"] == "Branca"].set_index(chave_ref)[["taxa", "obitos"]]
    t["taxa_branca"] = t[chave_ref].map(ref["taxa"])
    t["obitos_branca"] = t[chave_ref].map(ref["obitos"])
    t["razao"] = t["taxa"] / t["taxa_branca"].where(t["taxa_branca"] > 0)

    if f.grupos:
        t = t[t["grupo_racial"].isin(f.grupos)]
    if metrica in ("taxa", "razao"):
        t = t[(t["grupo_racial"] != "Ignorada") & (t[x] != "idade_ignorada") & t["taxa"].notna()]
    if metrica == "razao":
        t = t[t["taxa_branca"].notna()]
    t["pct"] = 100 * t["obitos"] / t.groupby(serie)["obitos"].transform("sum")
    t["contagem"] = t["obitos"]
    t["valor"] = t[metrica]
    t["instavel"] = t["obitos"] < MINIMO_ESTAVEL
    if metrica == "razao":
        t["instavel"] |= t["obitos_branca"] < MINIMO_ESTAVEL
    return t, x, serie


def _ordem(valores, eixo_col: str, faixas: dict[str, str]) -> list:
    if eixo_col == "grupo_racial":
        return [g for g in ORDEM_GRUPO if g in set(valores)]
    if eixo_col == "sexo":
        return [s for s in CORES_SEXO if s in set(valores)]
    return [c for c in faixas if c in set(valores)]


def _rotulo_y(metrica: str, f: Filtros) -> str:
    anual = " (anualizada)" if f.sim_parcial else ""
    return {
        "taxa": f"Óbitos por 100 mil hab.{anual}",
        "razao": "Risco em relação ao grupo branco (×)",
        "contagem": "Óbitos por agressão",
        "pct": "% dos óbitos de cada série",
    }[metrica]


def _formato(metrica: str, v: float) -> str:
    if pd.isna(v):
        return "—"
    return {"taxa": numero(v, 2), "razao": numero(v, 2) + "×", "contagem": numero(v),
            "pct": numero(v, 1) + "%"}[metrica]


def figura(t: pd.DataFrame, x: str, serie: str, metrica: str, f: Filtros, faixas: dict[str, str]) -> go.Figure:
    ordem_x = _ordem(t[x], x, faixas)
    ordem_s = _ordem(t[serie], serie, faixas)
    cores = CORES_GRUPO if serie == "grupo_racial" else CORES_SEXO
    rotulo_x = (lambda v: faixas.get(v, v)) if x == "faixa_etaria" else (lambda v: v)
    fig = go.Figure()
    for s in ordem_s:
        d = t[t[serie] == s].set_index(x).reindex(ordem_x)
        d = d[d["valor"].notna()]
        if d.empty:
            continue
        fig.add_bar(
            name=s,
            x=[rotulo_x(v) for v in d.index],
            y=d["valor"],
            marker=dict(color=cores.get(s, "#9b9a95"), cornerradius=4,
                        pattern=dict(shape=["/" if i else "" for i in d["instavel"]], fillmode="overlay",
                                     fgcolor="rgba(255,255,255,0.9)", size=6, solidity=0.4)),
            text=["" if metrica == "razao" and s == "Branca" else _formato(metrica, v) for v in d["valor"]],
            textposition="outside", cliponaxis=False,
            customdata=list(zip(
                [numero(v) for v in d["obitos"]],
                [numero(v) for v in d["populacao"]],
                [_formato("taxa", v) for v in d["taxa"]],
                ["<br><i>Menos de 10 óbitos: estimativa instável</i>" if i else "" for i in d["instavel"]],
                [_formato(metrica, v) for v in d["valor"]],
            )),
            hovertemplate=(f"<b>{s}</b> · %{{x}}<br>{_rotulo_y(metrica, f)}: %{{customdata[4]}}"
                           "<br>Óbitos: %{customdata[0]} · população: %{customdata[1]}"
                           "<br>Taxa por 100 mil: %{customdata[2]}%{customdata[3]}<extra></extra>"),
        )
    if metrica == "razao":
        fig.add_hline(y=1, line_dash="dash", line_width=1, line_color="#8a8984")
    fig.update_layout(
        barmode="group", bargap=0.25, bargroupgap=0.06, separators=",.",
        height=430, margin=dict(t=40, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        showlegend=len(fig.data) > 1,
        yaxis=dict(title=_rotulo_y(metrica, f), rangemode="tozero", gridcolor="rgba(128,128,128,0.18)",
                   zeroline=False),
        xaxis=dict(title=None),
        hoverlabel=dict(align="left"),
    )
    return fig


def tabela(t: pd.DataFrame, x: str, serie: str, faixas: dict[str, str]) -> pd.DataFrame:
    nomes = {"grupo_racial": "Raça/cor", "sexo": "Sexo", "faixa_etaria": "Faixa etária"}
    out = t[[x, serie, "obitos", "populacao", "taxa", "razao", "pct", "instavel"]].copy()
    if "faixa_etaria" in (x, serie):
        out["faixa_etaria"] = out["faixa_etaria"].map(lambda v: faixas.get(v, v))
    return out.rename(columns={
        x: nomes[x], serie: nomes[serie], "obitos": "Óbitos", "populacao": "População",
        "taxa": "Taxa por 100 mil", "razao": "Risco vs. branca", "pct": "% da série",
        "instavel": "Estimativa instável",
    })


NOTA = ("Óbitos por agressão (SIM) com a população do mesmo grupo no denominador. Risco vs. branca = taxa do "
        "grupo ÷ taxa do grupo branco com o mesmo sexo ou faixa (linha tracejada = 1). Barras hachuradas: menos "
        f"de {MINIMO_ESTAVEL} óbitos, estimativa instável (RN21). Raça/cor e idade ignoradas ficam fora das taxas.")


def render(f: Filtros, altura: int = 400) -> None:
    with cartao("interseccional", "Comparativo interseccional · óbitos por agressão", NOTA):
        c1, c2 = st.columns([2.6, 1], vertical_alignment="center")
        metrica = c1.segmented_control("Métrica", list(METRICAS), format_func=METRICAS.get, key="g_metrica",
                                       default="taxa", label_visibility="collapsed") or "taxa"
        eixo = c2.selectbox("Comparar por", list(EIXOS), format_func=EIXOS.get,
                            key="g_eixo", label_visibility="collapsed")

        faixas = _faixas_rotulos()
        t, x, serie = preparar(_dados(f), f, eixo, metrica)
        if t.empty or t["valor"].isna().all():
            motivo = (" O risco é calculado em relação ao grupo branco, que não tem óbitos neste recorte."
                      if metrica == "razao" else "")
            st.info(f"Sem dados para esta métrica no recorte selecionado.{motivo}", icon="🔍")
            return

        fig = figura(t, x, serie, metrica, f, faixas)
        fig.update_layout(height=altura, margin=dict(t=30, b=0, l=0, r=0))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "locale": "pt-BR"})

        with st.expander("Dados"):
            tab = tabela(t, x, serie, faixas)
            st.dataframe(
                tab, hide_index=True, width="stretch",
                column_config={
                    "Óbitos": st.column_config.NumberColumn(format="localized"),
                    "População": st.column_config.NumberColumn(format="localized"),
                    "Taxa por 100 mil": st.column_config.NumberColumn(format="%.2f"),
                    "Risco vs. branca": st.column_config.NumberColumn(format="%.2f×"),
                    "% da série": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )
            st.download_button("Baixar CSV", tab.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                               file_name=f"comparativo_{eixo}_{metrica}_{f.ano}.csv", mime="text/csv")
