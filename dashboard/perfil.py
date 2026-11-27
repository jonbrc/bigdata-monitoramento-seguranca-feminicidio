"""Perfil da violência no dashboard (SIM): local do óbito e meio da agressão por sexo, mapa de calor das taxas por faixa etária × raça/cor e evolução mensal das taxas."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db
from filtros import Filtros
from graficos import CORES_GRUPO, CORES_SEXO, ORDEM_GRUPO, SEXO_ROTULO
from kpis import MINIMO_ESTAVEL, numero
from layout import cartao
from territorio import ESCALA, SUPRESSAO

DIMENSOES = {
    "local": ("local_obito", "dim_local_obito", "Local do óbito"),
    "meio": ("meio_agressao", "dim_meio_agressao", "Meio da agressão"),
}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
GRUPOS_EVOLUCAO = ["Branca", "Negra", "Indígena"]
SERIES = {"grupo": "Raça/cor", "sexo": "Sexo"}


def _casos(n) -> str:
    if pd.isna(n):
        return "—"
    return f"≤ {SUPRESSAO - 1}" if 0 < n < SUPRESSAO else numero(n)


def _distribuicao(f: Filtros, dimensao: str) -> pd.DataFrame:
    coluna, tabela, _ = DIMENSOES[dimensao]
    where, params = f.where()
    df = db.consultar(f"""
        SELECT v.sexo, d.codigo, d.descricao, d.ordem, v.obitos
        FROM (SELECT sexo, {coluna} AS codigo, SUM(obitos) AS obitos
              FROM vw_sim WHERE {where} GROUP BY 1, 2) v
        JOIN {tabela} d USING (codigo)
        ORDER BY d.ordem""", tuple(params))
    df["sexo"] = df["sexo"].map(SEXO_ROTULO)
    df["obitos"] = df["obitos"].astype("int64")
    df["pct"] = 100 * df["obitos"] / df.groupby("sexo")["obitos"].transform("sum")
    return df


def _figura_distribuicao(df: pd.DataFrame, titulo_eixo: str) -> go.Figure:
    categorias = list(dict.fromkeys(df.sort_values("ordem")["descricao"]))
    fig = go.Figure()
    for sexo in [s for s in CORES_SEXO if s in set(df["sexo"])]:
        d = df[df["sexo"] == sexo].set_index("descricao").reindex(categorias)
        total = int(df.loc[df["sexo"] == sexo, "obitos"].sum())
        fig.add_bar(
            name=sexo, y=categorias, x=d["pct"].fillna(0), orientation="h",
            marker=dict(color=CORES_SEXO[sexo], cornerradius=4),
            text=[numero(v, 1) + "%" if not pd.isna(v) else "" for v in d["pct"]],
            textposition="outside", cliponaxis=False,
            customdata=list(zip([_casos(v) for v in d["obitos"]], [numero(total)] * len(d))),
            hovertemplate=f"<b>{sexo}</b> · %{{y}}<br>%{{x:.1f}}% dos óbitos"
                          "<br>Óbitos: %{customdata[0]} de %{customdata[1]}<extra></extra>",
        )
    fig.update_layout(
        barmode="group", bargap=0.28, bargroupgap=0.06, separators=",.",
        height=max(300, 46 * len(categorias) + 80), margin=dict(t=30, b=10, l=10, r=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        showlegend=len(fig.data) > 1,
        xaxis=dict(title=f"% dos óbitos de cada sexo · {titulo_eixo.lower()}", rangemode="tozero",
                   gridcolor="rgba(128,128,128,0.18)", ticksuffix="%"),
        yaxis=dict(title=None, autorange="reversed", automargin=True),
        hoverlabel=dict(align="left"), dragmode=False,
    )
    return fig


def _bloco_distribuicao(f: Filtros, dimensao: str, altura: int) -> None:
    titulo = DIMENSOES[dimensao][2]
    nota = (f"% dos óbitos por agressão de cada sexo no recorte (SIM). Com menos de {MINIMO_ESTAVEL} óbitos num "
            "sexo, os percentuais são instáveis.")
    with cartao(f"perfil_{dimensao}", f"{titulo} por sexo", nota):
        df = _distribuicao(f, dimensao)
        if df.empty:
            st.info("Sem óbitos no recorte selecionado.", icon="🔍")
            return
        fig = _figura_distribuicao(df, titulo)
        fig.update_layout(height=altura, margin=dict(t=30, b=0, l=0, r=40))
        st.plotly_chart(fig, width="stretch", key=f"perfil_{dimensao}", config={"displayModeBar": False})


def _calor(f: Filtros) -> pd.DataFrame:
    where, params = f.where(ignorar=("grupo", "faixa"))
    df = db.consultar(f"""
        SELECT v.grupo_racial, v.faixa_etaria, d.descricao AS faixa, v.faixa_ordem,
               SUM(v.obitos) AS obitos, SUM(v.populacao) AS populacao, MAX(v.meses_cobertos) AS meses
        FROM vw_taxa_sim_uf v JOIN dim_faixa_etaria d ON d.codigo = v.faixa_etaria
        WHERE {where} AND v.grupo_racial <> 'Ignorada' AND v.faixa_etaria <> 'idade_ignorada'
        GROUP BY 1, 2, 3, 4""", tuple(params))
    df = df.astype({"obitos": "int64", "populacao": "int64", "meses": "int64", "faixa_ordem": "int64"})
    if f.grupos:
        df = df[df["grupo_racial"].isin(f.grupos)]
    if f.faixas:
        df = df[df["faixa_etaria"].isin(f.faixas)]
    df["taxa"] = df["obitos"] * 100000 / df["populacao"].where(df["populacao"] > 0) * 12 / df["meses"]
    return df


def _figura_calor(df: pd.DataFrame, f: Filtros) -> go.Figure:
    linhas = [g for g in ORDEM_GRUPO if g in set(df["grupo_racial"])]
    colunas = list(dict.fromkeys(df.sort_values("faixa_ordem")["faixa"]))
    taxa = df.pivot_table(index="grupo_racial", columns="faixa", values="taxa").reindex(index=linhas, columns=colunas)
    obitos = df.pivot_table(index="grupo_racial", columns="faixa", values="obitos").reindex(index=linhas, columns=colunas)
    texto = [[("—" if pd.isna(t) else numero(t, 2) + ("*" if o < MINIMO_ESTAVEL else ""))
              for t, o in zip(taxa.loc[g], obitos.loc[g])] for g in linhas]
    casos = [[_casos(o) for o in obitos.loc[g]] for g in linhas]
    fig = go.Figure(go.Heatmap(
        z=taxa.values, x=colunas, y=linhas, text=texto, texttemplate="%{text}", textfont=dict(size=13),
        customdata=casos, colorscale=ESCALA, zmin=0, xgap=2, ygap=2, hoverongaps=False,
        colorbar=dict(title=dict(text="por 100 mil", side="right"), thickness=10, tickformat=",.0f"),
        hovertemplate="<b>%{y}</b> · %{x}<br>Taxa por 100 mil: %{text}<br>Óbitos: %{customdata}<extra></extra>",
    ))
    fig.update_layout(
        height=max(260, 62 * len(linhas) + 90), margin=dict(t=10, b=10, l=10, r=10), separators=",.",
        xaxis=dict(title=None, side="top"), yaxis=dict(title=None, autorange="reversed"), dragmode=False,
    )
    return fig


def _bloco_calor(f: Filtros) -> None:
    anual = " (anualizada)" if f.sim_parcial else ""
    nota = ("Óbitos por agressão por 100 mil hab., com a população do mesmo grupo e faixa no denominador. Segue o "
            f"filtro Sexo da barra lateral. * menos de {MINIMO_ESTAVEL} óbitos: estimativa instável (RN21). Raça/cor "
            "e idade ignoradas ficam fora, por não terem população correspondente.")
    with cartao("perfil_calor", f"Taxa por 100 mil{anual} · faixa etária × raça/cor", nota):
        df = _calor(f)
        if df.empty or df["taxa"].isna().all():
            st.info("Sem população ou óbitos para montar o mapa de calor neste recorte.", icon="🔍")
            return
        st.plotly_chart(_figura_calor(df, f), width="stretch", key="perfil_calor", config={"displayModeBar": False})


def _evolucao(f: Filtros, serie: str) -> pd.DataFrame:
    col = "grupo_racial" if serie == "grupo" else "sexo"
    w_obi, p_obi = f.where(ignorar=("ano",))
    w_pop, p_pop = f.where(ignorar=("ano",))
    df = db.consultar(f"""
        WITH t AS (SELECT ano, mes, id_tempo FROM dim_tempo WHERE sim_periodo_coberto),
             o AS (SELECT id_tempo, {col} AS serie, SUM(obitos) AS obitos
                   FROM vw_sim WHERE {w_obi} GROUP BY 1, 2),
             p AS (SELECT {col} AS serie, SUM(populacao) AS populacao
                   FROM vw_populacao WHERE {w_pop} GROUP BY 1)
        SELECT t.ano, t.mes, p.serie, p.populacao, COALESCE(o.obitos, 0) AS obitos
        FROM t CROSS JOIN p LEFT JOIN o ON o.id_tempo = t.id_tempo AND o.serie = p.serie
        ORDER BY t.ano, t.mes""", tuple(p_obi + p_pop))
    df = df.astype({"ano": "int64", "mes": "int64", "populacao": "int64", "obitos": "int64"})
    if serie == "grupo":
        escolhidos = f.grupos or GRUPOS_EVOLUCAO
        df = df[df["serie"].isin([g for g in escolhidos if g != "Ignorada"])]
    else:
        df["serie"] = df["serie"].map(SEXO_ROTULO)
    df["taxa"] = df["obitos"] * 100000 * 12 / df["populacao"].where(df["populacao"] > 0)
    df["rotulo"] = [f"{MESES[m - 1]}/{str(a)[2:]}" for a, m in zip(df["ano"], df["mes"])]
    return df


def _figura_evolucao(df: pd.DataFrame, serie: str, f: Filtros) -> go.Figure:
    cores = CORES_GRUPO if serie == "grupo" else CORES_SEXO
    ordem = [s for s in cores if s in set(df["serie"])]
    meses = list(dict.fromkeys(df["rotulo"]))
    fig = go.Figure()
    do_ano = [r for r, a in zip(df["rotulo"], df["ano"]) if a == f.ano]
    if do_ano and len(set(df["ano"])) > 1:
        fig.add_vrect(x0=meses.index(do_ano[0]) - 0.5, x1=meses.index(do_ano[-1]) + 0.5,
                      fillcolor="rgba(128,128,128,0.08)", line_width=0, layer="below")
    meses_por_ano = df.groupby("ano")["mes"].nunique()
    incompletos = {f"{MESES[df.loc[df['ano'] == a, 'mes'].max() - 1]}/{str(a)[2:]}"
                   for a, n in meses_por_ano.items() if n < 12}
    for s in ordem:
        d = df[df["serie"] == s]
        fechado = d[~d["rotulo"].isin(incompletos)]
        instavel = fechado["obitos"] < MINIMO_ESTAVEL
        fig.add_scatter(
            name=s, x=fechado["rotulo"], y=fechado["taxa"], mode="lines+markers", legendgroup=s,
            line=dict(color=cores[s], width=2),
            marker=dict(size=8, color=[("white" if i else cores[s]) for i in instavel],
                        line=dict(color=cores[s], width=2)),
            customdata=list(zip([_casos(v) for v in fechado["obitos"]], [numero(v, 2) for v in fechado["taxa"]])),
            hovertemplate=f"<b>{s}</b><br>Taxa anualizada: %{{customdata[1]}} por 100 mil"
                          "<br>Óbitos no mês: %{customdata[0]}<extra></extra>",
        )
        for rotulo in incompletos & set(d["rotulo"]):
            k = meses.index(rotulo)
            trecho = d[d["rotulo"].isin(meses[max(k - 1, 0):k + 1])]
            ultimo = d[d["rotulo"] == rotulo]
            fig.add_scatter(x=trecho["rotulo"], y=trecho["taxa"], mode="lines", legendgroup=s, showlegend=False,
                            line=dict(color=cores[s], width=2, dash="dot"), hoverinfo="skip")
            fig.add_scatter(
                x=ultimo["rotulo"], y=ultimo["taxa"], mode="markers", legendgroup=s, showlegend=False,
                marker=dict(size=8, color="white", line=dict(color=cores[s], width=2)),
                customdata=list(zip([_casos(v) for v in ultimo["obitos"]], [numero(v, 2) for v in ultimo["taxa"]])),
                hovertemplate=f"<b>{s}</b> · mês incompleto<br>Taxa anualizada: %{{customdata[1]}} por 100 mil"
                              "<br>Óbitos no mês: %{customdata[0]}<extra></extra>",
            )
    fig.update_layout(
        height=380, margin=dict(t=30, b=10, l=10, r=10), separators=",.", hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        xaxis=dict(title=None, categoryorder="array", categoryarray=meses, showgrid=False),
        yaxis=dict(title="Óbitos por 100 mil hab. (taxa mensal anualizada)", rangemode="tozero",
                   gridcolor="rgba(128,128,128,0.18)", zeroline=False),
        dragmode=False,
    )
    return fig


NOTA_EVOLUCAO = ("Taxa do mês × 12, comparável às taxas anuais; a faixa cinza marca o ano selecionado e os demais "
                 f"filtros valem para toda a série. Pontos vazados: menos de {MINIMO_ESTAVEL} óbitos no mês. Linha "
                 "pontilhada: último mês de um ano preliminar do SIM, ainda incompleto. Amarela fica de fora por "
                 "padrão (poucos casos); selecione-a em Raça/cor para incluí-la.")


def bloco_evolucao(f: Filtros, altura: int = 400) -> None:
    with cartao("evolucao", "Evolução mensal · óbitos por agressão por 100 mil", NOTA_EVOLUCAO):
        serie = st.segmented_control("Séries", list(SERIES), format_func=SERIES.get, key="p_serie",
                                     default="grupo", label_visibility="collapsed") or "grupo"
        df = _evolucao(f, serie)
        if df.empty or df["taxa"].isna().all():
            st.info("Sem população ou óbitos para a evolução mensal neste recorte.", icon="🔍")
            return
        fig = _figura_evolucao(df, serie, f)
        fig.update_layout(height=altura, margin=dict(t=30, b=0, l=0, r=0),
                          yaxis_title="Taxa mensal anualizada")
        meses = list(dict.fromkeys(df["rotulo"]))
        fig.update_xaxes(tickangle=0, tickmode="array", tickvals=meses[::3])
        st.plotly_chart(fig, width="stretch", key="perfil_evolucao", config={"displayModeBar": False})
        with st.expander("Dados"):
            tab = df.assign(obitos=[_casos(v) for v in df["obitos"]])[
                ["rotulo", "serie", "obitos", "populacao", "taxa"]].rename(columns={
                "rotulo": "Mês", "serie": SERIES[serie], "obitos": "Óbitos", "populacao": "População",
                "taxa": "Taxa anualizada"})
            st.dataframe(tab, hide_index=True, width="stretch",
                         column_config={"Taxa anualizada": st.column_config.NumberColumn(format="%.2f")})
            st.download_button("Baixar CSV", tab.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                               file_name=f"evolucao_mensal_{serie}.csv", mime="text/csv", key="csv_evolucao")


def render(f: Filtros) -> None:
    c1, c2 = st.columns(2)
    with c1:
        _bloco_distribuicao(f, "local", 420)
    with c2:
        _bloco_distribuicao(f, "meio", 420)
    _bloco_calor(f)
