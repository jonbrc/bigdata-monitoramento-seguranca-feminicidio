"""Aba "Polícia × saúde" do dashboard: compara o registro policial (Sinesp) e o de saúde (SIM) das mortes de mulheres, mês a mês e por território, e mostra quanto das mortes violentas de mulheres foi tipificado como feminicídio."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db
from filtros import Filtros, Opcoes
from kpis import MINIMO_ESTAVEL, numero
from perfil import MESES

SERIES = {
    "obitos_sim": ("Óbitos de mulheres por agressão (SIM)", "#6250d6", "solid"),
    "mortes_violentas": ("Mortes violentas de mulheres (Sinesp)", "#eda100", "solid"),
    "feminicidios": ("Feminicídios (Sinesp)", "#e87ba4", "dash"),
}
COR_PCT = "#e87ba4"
COR_DESTAQUE_LINHA = "#8a8984"


def _mensal(f: Filtros) -> pd.DataFrame:
    w, p = f.where(perfil=False, ignorar=("ano",))
    df = db.consultar(f"""
        WITH t AS (SELECT ano, mes FROM dim_tempo WHERE sim_periodo_coberto),
             s AS (SELECT ano, mes,
                          SUM(vitimas_fem) FILTER (WHERE evento = 'feminicidio') AS feminicidios,
                          SUM(vitimas_fem) FILTER (WHERE tipo = 'consumado') AS mortes_violentas
                   FROM vw_sinesp WHERE {w} GROUP BY 1, 2),
             o AS (SELECT ano, mes, SUM(obitos) AS obitos_sim
                   FROM vw_sim WHERE sexo = 'feminino' AND {w} GROUP BY 1, 2)
        SELECT t.ano, t.mes, COALESCE(s.feminicidios, 0) AS feminicidios,
               COALESCE(s.mortes_violentas, 0) AS mortes_violentas, COALESCE(o.obitos_sim, 0) AS obitos_sim
        FROM t LEFT JOIN s USING (ano, mes) LEFT JOIN o USING (ano, mes)
        ORDER BY t.ano, t.mes""", tuple(p + p))
    df = df.astype("int64")
    df["rotulo"] = [f"{MESES[m - 1]}/{str(a)[2:]}" for a, m in zip(df["ano"], df["mes"])]
    return df


def _figura_mensal(df: pd.DataFrame, f: Filtros) -> go.Figure:
    fig = go.Figure()
    meses = df["rotulo"].tolist()
    do_ano = df.loc[df["ano"] == f.ano, "rotulo"].tolist()
    if do_ano and df["ano"].nunique() > 1:
        fig.add_vrect(x0=meses.index(do_ano[0]) - 0.5, x1=meses.index(do_ano[-1]) + 0.5,
                      fillcolor="rgba(128,128,128,0.08)", line_width=0, layer="below")
    por_ano = df.groupby("ano")["mes"].count()
    incompleto = df.index.isin([df[df["ano"] == a].index.max() for a, n in por_ano.items() if n < 12])
    for coluna, (nome, cor, traco) in SERIES.items():
        sim = coluna == "obitos_sim"
        corte = incompleto if sim else [False] * len(df)
        d = df[~pd.Series(corte, index=df.index)]
        fig.add_scatter(
            name=nome, x=d["rotulo"], y=d[coluna], mode="lines+markers", legendgroup=coluna,
            line=dict(color=cor, width=2, dash=traco), marker=dict(size=7, color=cor),
            customdata=[numero(v) for v in d[coluna]],
            hovertemplate=f"{nome}: %{{customdata}}<extra></extra>",
        )
        for i in (df.index[incompleto] if sim else []):
            pos = df.index.get_loc(i)
            trecho = df.iloc[max(pos - 1, 0):pos + 1]
            fig.add_scatter(x=trecho["rotulo"], y=trecho[coluna], mode="lines", legendgroup=coluna,
                            showlegend=False, line=dict(color=cor, width=2, dash="dot"), hoverinfo="skip")
            fig.add_scatter(
                x=[df.at[i, "rotulo"]], y=[df.at[i, coluna]], mode="markers", legendgroup=coluna, showlegend=False,
                marker=dict(size=7, color="white", line=dict(color=cor, width=2)),
                customdata=[numero(df.at[i, coluna])],
                hovertemplate=f"{nome} (mês incompleto): %{{customdata}}<extra></extra>",
            )
    fig.update_layout(
        height=380, margin=dict(t=30, b=10, l=10, r=10), separators=",.", hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        xaxis=dict(title=None, showgrid=False),
        yaxis=dict(title="Mulheres mortas no mês", rangemode="tozero", gridcolor="rgba(128,128,128,0.18)",
                   zeroline=False),
        dragmode=False,
    )
    return fig


def _territorios(f: Filtros, opcoes: Opcoes) -> tuple[pd.DataFrame, str]:
    campo = "regiao" if not (f.regioes or f.ufs) else "sigla_uf"
    w, p = f.where(perfil=False)
    df = db.consultar(f"""
        WITH c AS (SELECT {campo} AS chave, SUM(obitos_fem_agressao_sim) AS obitos_sim,
                          SUM(mortes_violentas_fem_sinesp) AS mortes_violentas_periodo
                   FROM vw_comparativo_sinesp_sim WHERE {w} GROUP BY 1),
             k AS (SELECT {campo} AS chave, SUM(feminicidios) AS feminicidios,
                          SUM(mortes_violentas_fem) AS mortes_violentas_ano
                   FROM vw_kpi_uf WHERE {w} GROUP BY 1)
        SELECT k.chave, COALESCE(c.obitos_sim, 0) AS obitos_sim,
               COALESCE(c.mortes_violentas_periodo, 0) AS mortes_violentas,
               k.feminicidios, k.mortes_violentas_ano
        FROM k LEFT JOIN c USING (chave)""", tuple(p + p))
    df[["obitos_sim", "mortes_violentas", "feminicidios", "mortes_violentas_ano"]] = df[
        ["obitos_sim", "mortes_violentas", "feminicidios", "mortes_violentas_ano"]].astype("int64")
    if campo == "sigla_uf":
        alvo = f.ufs or opcoes.ufs_de(f.regioes)
        df = df[df["chave"].isin(alvo)]
        nomes = opcoes.ufs.set_index("sigla_uf")["nome_uf"]
        df["nome"] = df["chave"] + " · " + df["chave"].map(nomes)
    else:
        df["nome"] = df["chave"]
    df["razao"] = df["obitos_sim"] / df["mortes_violentas"].where(df["mortes_violentas"] > 0)
    df["pct_feminicidio"] = 100 * df["feminicidios"] / df["mortes_violentas_ano"].where(df["mortes_violentas_ano"] > 0)
    return df, campo


def _figura_halteres(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("obitos_sim")
    fig = go.Figure()
    xs, ys = [], []
    for _, r in d.iterrows():
        xs += [r["mortes_violentas"], r["obitos_sim"], None]
        ys += [r["nome"], r["nome"], None]
    fig.add_scatter(x=xs, y=ys, mode="lines", line=dict(color="rgba(128,128,128,0.45)", width=2),
                    hoverinfo="skip", showlegend=False)
    razoes = [numero(v, 2) if not pd.isna(v) else "—" for v in d["razao"]]
    for coluna in ("mortes_violentas", "obitos_sim"):
        nome, cor, _ = SERIES[coluna]
        fig.add_scatter(
            name=nome, x=d[coluna], y=d["nome"], mode="markers",
            marker=dict(size=12, color=cor, line=dict(color="white", width=2),
                        symbol="circle" if coluna == "obitos_sim" else "diamond"),
            customdata=list(zip([numero(v) for v in d[coluna]], razoes)),
            hovertemplate=f"<b>%{{y}}</b><br>{nome}: %{{customdata[0]}}"
                          "<br>SIM ÷ Sinesp: %{customdata[1]}<extra></extra>",
        )
    fig.update_layout(
        height=max(280, 30 * len(d) + 90), margin=dict(t=30, b=10, l=10, r=20), separators=",.",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        xaxis=dict(title="Mulheres mortas no período coberto pelo SIM", rangemode="tozero",
                   gridcolor="rgba(128,128,128,0.18)"),
        yaxis=dict(title=None, automargin=True), dragmode=False,
    )
    return fig


def _figura_pct(df: pd.DataFrame, media: float | None) -> go.Figure:
    d = df[df["pct_feminicidio"].notna()].sort_values("pct_feminicidio")
    instavel = d["mortes_violentas_ano"] < MINIMO_ESTAVEL
    fig = go.Figure(go.Bar(
        x=d["pct_feminicidio"], y=d["nome"], orientation="h",
        marker=dict(color=COR_PCT, cornerradius=4,
                    pattern=dict(shape=["/" if i else "" for i in instavel], fillmode="overlay",
                                 fgcolor="rgba(255,255,255,0.9)", size=6, solidity=0.4)),
        text=[numero(v, 1) + "%" for v in d["pct_feminicidio"]], textposition="outside", cliponaxis=False,
        customdata=list(zip([numero(v) for v in d["feminicidios"]], [numero(v) for v in d["mortes_violentas_ano"]])),
        hovertemplate="<b>%{y}</b><br>%{x:.1f}% tipificadas como feminicídio"
                      "<br>Feminicídios: %{customdata[0]} de %{customdata[1]} mortes violentas<extra></extra>",
    ))
    if media is not None and len(d) > 1:
        fig.add_vline(x=media, line_dash="dash", line_width=1, line_color=COR_DESTAQUE_LINHA,
                      annotation_text=f"recorte: {numero(media, 1)}%", annotation_position="top",
                      annotation_font_size=12)
    fig.update_layout(
        height=max(280, 30 * len(d) + 90), margin=dict(t=30, b=10, l=10, r=50), separators=",.",
        xaxis=dict(title="% das mortes violentas de mulheres (Sinesp)", rangemode="tozero",
                   gridcolor="rgba(128,128,128,0.18)", ticksuffix="%"),
        yaxis=dict(title=None, automargin=True), bargap=0.3, showlegend=False, dragmode=False,
    )
    return fig


def render(f: Filtros, opcoes: Opcoes) -> None:
    st.caption("Esta aba compara as duas fontes só para mulheres e segue apenas os filtros de ano e território: "
               "o Sinesp não traz raça/cor nem idade.")

    st.markdown("**Mês a mês: registro policial × registro de saúde**")
    mensal = _mensal(f)
    st.plotly_chart(_figura_mensal(mensal, f), width="stretch", key="ps_mensal", config={"displayModeBar": False})
    st.caption("Meses cobertos pelo SIM. Linha pontilhada: último mês de um ano preliminar do SIM, ainda incompleto, "
               "por isso a queda não é real. A faixa cinza marca o ano selecionado. Mortes violentas = feminicídio, homicídio doloso, lesão corporal seguida de morte "
               "e latrocínio com vítima mulher.")
    with st.expander("Ver tabela mensal"):
        tab = mensal[["rotulo", "obitos_sim", "mortes_violentas", "feminicidios"]].rename(columns={
            "rotulo": "Mês", **{k: v[0] for k, v in SERIES.items()}})
        st.dataframe(tab, hide_index=True, width="stretch")
        st.download_button("Baixar CSV", tab.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           file_name="policia_saude_mensal.csv", mime="text/csv", key="ps_csv_mensal")

    st.divider()
    df, campo = _territorios(f, opcoes)
    if df.empty:
        st.info("Nenhum território com dados neste recorte.", icon="🔍")
        return
    nivel = "região" if campo == "regiao" else "UF"
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Polícia × saúde por {nivel} · {f.ano}**")
        st.plotly_chart(_figura_halteres(df), width="stretch", key=f"ps_halteres_{campo}",
                        config={"displayModeBar": False})
        st.caption("Os dois registros medem coisas parecidas, mas não iguais: o SIM conta pelo município de "
                   "residência e pela causa básica (agressão, CID X85–Y09); o Sinesp, pelo local da ocorrência e "
                   "pela tipificação policial. Quanto mais distantes os pontos, maior a divergência entre as fontes.")
    with c2:
        st.markdown(f"**Mortes violentas de mulheres tipificadas como feminicídio · {f.ano}**")
        total_fem, total_mv = df["feminicidios"].sum(), df["mortes_violentas_ano"].sum()
        media = 100 * total_fem / total_mv if total_mv else None
        st.plotly_chart(_figura_pct(df, media), width="stretch", key=f"ps_pct_{campo}",
                        config={"displayModeBar": False})
        notas = ["Ano completo do Sinesp, como no cartão de KPI. Percentual baixo pode indicar subnotificação ou "
                 "tipificação tardia do feminicídio, não necessariamente menos violência de gênero."]
        if (df["mortes_violentas_ano"] < MINIMO_ESTAVEL).any():
            notas.append(f"Barras hachuradas: menos de {MINIMO_ESTAVEL} mortes violentas, estimativa instável.")
        st.caption(" ".join(notas))
