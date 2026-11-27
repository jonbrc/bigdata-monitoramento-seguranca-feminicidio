"""Aba "Perfil da violência" do dashboard: local do óbito e meio da agressão por sexo, mapa de calor das taxas por faixa etária × raça/cor e evolução mensal das taxas (SIM)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db
from filtros import Filtros
from graficos import CORES_GRUPO, CORES_SEXO, ORDEM_GRUPO, SEXO_ROTULO
from kpis import MINIMO_ESTAVEL, numero
from territorio import ESCALA, SUPRESSAO

DIMENSOES = {
    "local": ("local_obito", "dim_local_obito", "Local do óbito"),
    "meio": ("meio_agressao", "dim_meio_agressao", "Meio da agressão"),
}
IGNORADOS = {"local_ignorado", "meio_nao_especificado"}
COR_IGNORADO = "#b5b4ae"
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


def _destaque(df: pd.DataFrame) -> str | None:
    if set(CORES_SEXO) - set(df["sexo"]):
        return None
    base = df[~df["codigo"].isin(IGNORADOS)].pivot_table(index="descricao", columns="sexo", values="pct",
                                                           aggfunc="sum").fillna(0)
    if base.empty:
        return None
    categoria = (base["Mulheres"] - base["Homens"]).idxmax()
    m, h = base.at[categoria, "Mulheres"], base.at[categoria, "Homens"]
    if m <= h:
        return None
    return f"Maior sobrerrepresentação feminina: **{categoria}**, com {numero(m, 1)}% dos óbitos de mulheres contra {numero(h, 1)}% dos de homens."


def _bloco_distribuicao(f: Filtros, dimensao: str, coluna) -> None:
    titulo = DIMENSOES[dimensao][2]
    with coluna:
        st.markdown(f"**{titulo} por sexo**")
        df = _distribuicao(f, dimensao)
        if df.empty:
            st.info("Sem óbitos no recorte selecionado.", icon="🔍")
            return
        st.plotly_chart(_figura_distribuicao(df, titulo), width="stretch", key=f"perfil_{dimensao}",
                        config={"displayModeBar": False})
        notas = []
        destaque = _destaque(df)
        if destaque:
            notas.append(destaque)
        pequenos = [s for s, n in df.groupby("sexo")["obitos"].sum().items() if n < MINIMO_ESTAVEL]
        if pequenos:
            notas.append(f"Menos de {MINIMO_ESTAVEL} óbitos para {', '.join(pequenos).lower()}: percentuais instáveis.")
        if notas:
            st.caption(" ".join(notas))


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
    st.markdown(f"**Taxa de óbitos por agressão por 100 mil hab.{anual} · faixa etária × raça/cor**")
    df = _calor(f)
    if df.empty or df["taxa"].isna().all():
        st.info("Sem população ou óbitos para montar o mapa de calor neste recorte.", icon="🔍")
        return
    st.plotly_chart(_figura_calor(df, f), width="stretch", key="perfil_calor", config={"displayModeBar": False})
    sexo = {"todos": "ambos os sexos", "feminino": "só mulheres", "masculino": "só homens"}[f.sexo]
    st.caption(f"Recorte: {sexo} (filtro Sexo da barra lateral). Cada célula usa como denominador a população do "
               f"mesmo grupo e faixa. * menos de {MINIMO_ESTAVEL} óbitos: estimativa instável (RN21). Raça/cor e "
               "idade ignoradas ficam fora, por não terem população correspondente.")


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


def _bloco_evolucao(f: Filtros) -> None:
    c1, c2 = st.columns([3, 2])
    c1.markdown("**Evolução mensal da taxa de óbitos por agressão**")
    serie = c2.segmented_control("Séries", list(SERIES), format_func=SERIES.get, key="p_serie",
                                 default="grupo", label_visibility="collapsed") or "grupo"
    df = _evolucao(f, serie)
    if df.empty or df["taxa"].isna().all():
        st.info("Sem população ou óbitos para a evolução mensal neste recorte.", icon="🔍")
        return
    st.plotly_chart(_figura_evolucao(df, serie, f), width="stretch", key="perfil_evolucao",
                    config={"displayModeBar": False})
    notas = ["Taxa do mês × 12, para comparar com as taxas anuais. A faixa cinza marca o ano selecionado; os "
             "demais filtros valem para toda a série."]
    if (df["obitos"] < MINIMO_ESTAVEL).any():
        notas.append(f"Pontos vazados: menos de {MINIMO_ESTAVEL} óbitos no mês, estimativa instável.")
    if serie == "grupo" and not f.grupos:
        notas.append("Amarela fica de fora por padrão (poucos casos); selecione-a em Raça/cor para incluí-la.")
    notas.append("Linha pontilhada: último mês de um ano preliminar do SIM, ainda incompleto; os meses anteriores "
                 "a ele também podem crescer quando a base for consolidada.")
    st.caption(" ".join(notas))


def render(f: Filtros) -> None:
    c1, c2 = st.columns(2)
    _bloco_distribuicao(f, "local", c1)
    _bloco_distribuicao(f, "meio", c2)
    st.divider()
    _bloco_calor(f)
    st.divider()
    _bloco_evolucao(f)
