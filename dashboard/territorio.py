"""Drill-down geográfico do dashboard (Brasil → região → UF → município): ranking e mapa por território, navegação por clique que atualiza os filtros e supressão de células pequenas (RN22) já na consulta SQL."""

import math
from functools import partial

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db
from filtros import CHAVES, Filtros, Opcoes
from kpis import MINIMO_ESTAVEL, numero

SUPRESSAO = 3
COR = "#2a78d6"
ESCALA = [[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]]
COR_SUPRIMIDO = "#b5b4ae"
TOP_MUNICIPIOS = 15

INDICADORES = {
    "taxa_sim": ("Taxa de óbitos", "Óbitos por agressão por 100 mil hab. (SIM)"),
    "taxa_fem": ("Taxa de feminicídio", "Feminicídios por 100 mil mulheres (Sinesp)"),
    "obitos": ("Óbitos", "Óbitos por agressão (SIM)"),
    "feminicidios": ("Feminicídios", "Vítimas de feminicídio (Sinesp)"),
}
CONTAGEM = {"taxa_sim": "obitos", "taxa_fem": "feminicidios", "obitos": "obitos", "feminicidios": "feminicidios"}
SUPRIMIDO = {"obitos": "obitos_suprimido", "feminicidios": "feminicidios_suprimido"}


def nivel(f: Filtros) -> str:
    if len(f.ufs) == 1:
        return "municipio"
    if f.regioes or f.ufs:
        return "uf"
    return "regiao"


def _anualizar(f: Filtros) -> float:
    return 12 / f.meses_sim


def _por_territorio(f: Filtros, campo: str) -> pd.DataFrame:
    w_sim, p_sim = f.where()
    w_sin, p_sin = f.where(perfil=False)
    df = db.consultar(f"""
        WITH s AS (
            SELECT {campo} AS chave, SUM(obitos) AS obitos, SUM(populacao) AS populacao
            FROM vw_taxa_sim_uf WHERE {w_sim} GROUP BY 1
        ), k AS (
            SELECT {campo} AS chave, SUM(feminicidios) AS feminicidios, SUM(pop_fem) AS pop_fem
            FROM vw_kpi_uf WHERE {w_sin} GROUP BY 1
        ), cap AS (
            SELECT {'u.regiao' if campo == 'regiao' else 'u.sigla_uf'} AS chave,
                   AVG(m.latitude) AS latitude, AVG(m.longitude) AS longitude,
                   MIN(u.regiao) AS regiao, MIN(u.nome_uf) AS nome_uf
            FROM dim_municipio m JOIN dim_uf u USING (sigla_uf)
            WHERE m.capital GROUP BY 1
        )
        SELECT cap.chave, cap.regiao, cap.nome_uf, cap.latitude, cap.longitude,
               COALESCE(s.obitos, 0) AS obitos, COALESCE(s.populacao, 0) AS populacao,
               COALESCE(k.feminicidios, 0) AS feminicidios, COALESCE(k.pop_fem, 0) AS pop_fem
        FROM cap JOIN k USING (chave) LEFT JOIN s USING (chave)
    """, tuple(p_sim + p_sin))
    df = df.astype({"obitos": "int64", "populacao": "int64", "feminicidios": "int64", "pop_fem": "int64",
                    "latitude": "float64", "longitude": "float64"})
    df["taxa_sim"] = df["obitos"] * 100000 / df["populacao"].where(df["populacao"] > 0) * _anualizar(f)
    df["taxa_fem"] = df["feminicidios"] * 100000 / df["pop_fem"].where(df["pop_fem"] > 0)
    df["obitos_suprimido"] = False
    df["feminicidios_suprimido"] = False
    df["nome"] = df["chave"] if campo == "regiao" else df["chave"] + " · " + df["nome_uf"]
    return df


def _municipios(f: Filtros) -> pd.DataFrame:
    w_sim, p_sim = f.where(colunas={"uf": "sigla_uf"})
    w_pop, p_pop = f.where(ignorar=("ano",))
    w_sin, p_sin = f.where(perfil=False)
    w_pf, p_pf = f.where(perfil=False, ignorar=("ano",))
    df = db.consultar(f"""
        WITH o AS (SELECT codigo_ibge, SUM(obitos) AS n FROM vw_sim WHERE {w_sim} GROUP BY 1),
             p AS (SELECT codigo_ibge, SUM(populacao) AS n FROM vw_populacao WHERE {w_pop} GROUP BY 1),
             fe AS (SELECT codigo_ibge, SUM(vitimas_fem) AS n FROM vw_sinesp
                    WHERE evento = 'feminicidio' AND {w_sin} GROUP BY 1),
             pf AS (SELECT codigo_ibge, SUM(populacao) AS n FROM vw_populacao
                    WHERE sexo = 'feminino' AND {w_pf} GROUP BY 1)
        SELECT m.codigo_ibge AS chave, m.nome, m.latitude, m.longitude, m.capital,
               CASE WHEN COALESCE(o.n, 0) BETWEEN 1 AND %s THEN NULL ELSE COALESCE(o.n, 0) END AS obitos,
               COALESCE(o.n, 0) BETWEEN 1 AND %s AS obitos_suprimido,
               CASE WHEN o.n >= %s AND p.n > 0 THEN o.n * 100000.0 / p.n * %s END AS taxa_sim,
               CASE WHEN COALESCE(fe.n, 0) BETWEEN 1 AND %s THEN NULL ELSE COALESCE(fe.n, 0) END AS feminicidios,
               COALESCE(fe.n, 0) BETWEEN 1 AND %s AS feminicidios_suprimido,
               CASE WHEN fe.n >= %s AND pf.n > 0 THEN fe.n * 100000.0 / pf.n END AS taxa_fem
        FROM dim_municipio m
        LEFT JOIN o USING (codigo_ibge) LEFT JOIN p USING (codigo_ibge)
        LEFT JOIN fe USING (codigo_ibge) LEFT JOIN pf USING (codigo_ibge)
        WHERE m.sigla_uf = ANY(%s)
    """, tuple(p_sim + p_pop + p_sin + p_pf + [
        SUPRESSAO - 1, SUPRESSAO - 1, MINIMO_ESTAVEL, _anualizar(f),
        SUPRESSAO - 1, SUPRESSAO - 1, MINIMO_ESTAVEL, list(f.ufs)]))
    for c in ("obitos", "feminicidios", "taxa_sim", "taxa_fem", "latitude", "longitude"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


def _texto(indicador: str, linha) -> str:
    if indicador in SUPRIMIDO and linha[SUPRIMIDO[indicador]]:
        return f"≤ {SUPRESSAO - 1}"
    v = linha[indicador]
    if pd.isna(v):
        return "—"
    return numero(v, 2) if indicador.startswith("taxa") else numero(v)


def _instavel(indicador: str, linha) -> bool:
    contagem = linha[CONTAGEM[indicador]]
    return indicador.startswith("taxa") and not pd.isna(contagem) and contagem < MINIMO_ESTAVEL


def _ir_para(regioes: list[str], ufs: list[str]) -> None:
    st.session_state[CHAVES["regiao"]] = regioes
    st.session_state[CHAVES["uf"]] = ufs


def _ao_clicar(chave_grafico: str, campo: str, opcoes: Opcoes) -> None:
    evento = st.session_state.get(chave_grafico) or {}
    pontos = (evento.get("selection") or {}).get("points") or []
    if not pontos:
        return
    alvo = (pontos[0].get("customdata") or [None])[0]
    if campo == "regiao" and alvo in opcoes.regioes:
        _ir_para([alvo], [])
    elif campo == "sigla_uf" and alvo in set(opcoes.ufs["sigla_uf"]):
        regiao = opcoes.ufs.set_index("sigla_uf").at[alvo, "regiao"]
        _ir_para([regiao], [alvo])


def _trilha(f: Filtros, opcoes: Opcoes) -> None:
    passos = [("Brasil", ([], []))]
    if f.regioes:
        passos.append((", ".join(f.regioes), (f.regioes, [])))
    if f.ufs:
        passos.append((", ".join(f.ufs), (f.regioes, f.ufs)))
    colunas = st.columns([1.2] * len(passos) + [max(1, 8 - len(passos))])
    for i, (rotulo, destino) in enumerate(passos):
        atual = i == len(passos) - 1
        colunas[i].button(("› " if i else "") + rotulo, key=f"trilha_{i}", disabled=atual,
                          type="secondary", width="stretch",
                          on_click=_ir_para, args=destino)


def _cores_barras(d: pd.DataFrame, indicador: str):
    cores = [COR_SUPRIMIDO if (indicador in SUPRIMIDO and r[SUPRIMIDO[indicador]]) else COR for _, r in d.iterrows()]
    return cores[0] if len(set(cores)) == 1 else cores


def _barras(df: pd.DataFrame, indicador: str, rotulo: str) -> go.Figure:
    d = df.copy()
    d["_ordem"] = d[indicador].fillna(-1)
    d = d.sort_values("_ordem", ascending=True)
    fig = go.Figure(go.Bar(
        x=d[indicador].fillna(0), y=d["nome"], orientation="h",
        customdata=list(zip(d["chave"], [_texto(indicador, r) for _, r in d.iterrows()],
                            [_texto(CONTAGEM[indicador], r) for _, r in d.iterrows()])),
        text=[_texto(indicador, r) for _, r in d.iterrows()], textposition="outside", cliponaxis=False,
        marker=dict(color=_cores_barras(d, indicador),
                    cornerradius=4,
                    pattern=dict(shape=["/" if _instavel(indicador, r) else "" for _, r in d.iterrows()],
                                 fillmode="overlay", fgcolor="rgba(255,255,255,0.9)", size=6, solidity=0.4)),
        hovertemplate=f"<b>%{{y}}</b><br>{rotulo}: %{{customdata[1]}}"
                      "<br>Casos: %{customdata[2]}<extra></extra>",
    ))
    fig.update_layout(
        height=max(260, 28 * len(d) + 60), margin=dict(t=10, b=10, l=10, r=40), separators=",.",
        xaxis=dict(title=rotulo, rangemode="tozero", gridcolor="rgba(128,128,128,0.18)"),
        yaxis=dict(title=None, automargin=True), bargap=0.3, clickmode="event+select",
        dragmode=False,
    )
    return fig


def _mapa(df: pd.DataFrame, indicador: str, rotulo: str, nivel_atual: str) -> go.Figure:
    d = df.dropna(subset=["latitude", "longitude"]).copy()
    contagem = d[CONTAGEM[indicador]].fillna(SUPRESSAO - 1)
    maximo = max(float(contagem.max() or 1), 1)
    tamanho = 6 + 30 * (contagem / maximo).pow(0.5)
    if nivel_atual == "municipio":
        d = d[(contagem > 0) | d[SUPRIMIDO[CONTAGEM[indicador]]]]
        tamanho = tamanho.loc[d.index]
    valores = d[indicador]
    fig = go.Figure()
    com_valor = valores.notna()
    fig.add_trace(go.Scattermap(
        lat=d.loc[~com_valor, "latitude"], lon=d.loc[~com_valor, "longitude"], mode="markers",
        marker=dict(size=tamanho[~com_valor], color=COR_SUPRIMIDO, opacity=0.7),
        customdata=list(zip(d.loc[~com_valor, "chave"], d.loc[~com_valor, "nome"],
                            [_texto(indicador, r) for _, r in d[~com_valor].iterrows()],
                            [_texto(CONTAGEM[indicador], r) for _, r in d[~com_valor].iterrows()])),
        hovertemplate="<b>%{customdata[1]}</b><br>" + rotulo + ": %{customdata[2]}"
                      "<br>Casos: %{customdata[3]}<extra></extra>",
        showlegend=False,
    ))
    fig.add_trace(go.Scattermap(
        lat=d.loc[com_valor, "latitude"], lon=d.loc[com_valor, "longitude"], mode="markers",
        marker=dict(size=tamanho[com_valor], color=valores[com_valor], colorscale=ESCALA, opacity=0.85,
                    cmin=0, colorbar=dict(title=dict(text="", side="right"), thickness=10, len=0.6,
                                          tickformat=",.2f" if indicador.startswith("taxa") else ",d")),
        customdata=list(zip(d.loc[com_valor, "chave"], d.loc[com_valor, "nome"],
                            [_texto(indicador, r) for _, r in d[com_valor].iterrows()],
                            [_texto(CONTAGEM[indicador], r) for _, r in d[com_valor].iterrows()])),
        hovertemplate="<b>%{customdata[1]}</b><br>" + rotulo + ": %{customdata[2]}"
                      "<br>Casos: %{customdata[3]}<extra></extra>",
        showlegend=False,
    ))
    lat_min, lat_max = d["latitude"].min(), d["latitude"].max()
    lon_min, lon_max = d["longitude"].min(), d["longitude"].max()
    extensao = max(lat_max - lat_min, (lon_max - lon_min) * 0.8, 1.5)
    zoom = max(2.6, min(8.5, math.log2(360 / extensao) - 1.3))
    fig.update_layout(
        map=dict(style="carto-positron", zoom=zoom,
                 center=dict(lat=(lat_min + lat_max) / 2, lon=(lon_min + lon_max) / 2)),
        height=460, margin=dict(t=0, b=0, l=0, r=0), separators=",.", clickmode="event+select",
    )
    return fig


def render(f: Filtros, opcoes: Opcoes) -> None:
    nivel_atual = nivel(f)
    _trilha(f, opcoes)

    indicador = st.segmented_control(
        "Indicador", list(INDICADORES), format_func=lambda k: INDICADORES[k][0],
        key="t_indicador", default="taxa_sim",
    ) or "taxa_sim"
    rotulo = INDICADORES[indicador][1]
    if indicador == "taxa_sim" and f.sim_parcial:
        rotulo += " · anualizada"

    if nivel_atual == "municipio":
        df = _municipios(f)
        alvo_clique = None
        ranking = df[df[indicador].notna()].nlargest(TOP_MUNICIPIOS, indicador)
        titulo = f"Municípios de {f.ufs[0]} · {TOP_MUNICIPIOS} maiores valores"
    else:
        campo = "regiao" if nivel_atual == "regiao" else "sigla_uf"
        df = _por_territorio(f, campo)
        if nivel_atual == "uf":
            df = df[df["chave"].isin(f.ufs or opcoes.ufs_de(f.regioes))]
        ranking, alvo_clique = df, campo
        titulo = "Regiões" if campo == "regiao" else "Unidades da Federação"
    mapa_df = df if nivel_atual != "regiao" else _por_territorio(f, "sigla_uf")

    if ranking.empty:
        st.info("Nenhum território com valor exibível para este indicador no recorte selecionado.", icon="🔍")
        return

    recorte = "_".join([str(f.ano), *f.regioes, *f.ufs])
    c1, c2 = st.columns([1, 1.25])
    with c1:
        st.markdown(f"**{titulo}**")
        chave_barras = f"barras_{nivel_atual}_{indicador}_{recorte}"
        if alvo_clique:
            st.plotly_chart(_barras(ranking, indicador, rotulo), width="stretch",
                            key=chave_barras, on_select=partial(_ao_clicar, chave_barras, alvo_clique, opcoes),
                            selection_mode="points", config={"displayModeBar": False})
        else:
            st.plotly_chart(_barras(ranking, indicador, rotulo), width="stretch",
                            key=chave_barras, config={"displayModeBar": False})
    with c2:
        st.markdown("**Mapa**" + (" · clique numa UF para aprofundar" if nivel_atual != "municipio" else ""))
        chave_mapa = f"mapa_{nivel_atual}_{indicador}_{recorte}"
        figura_mapa = _mapa(mapa_df, indicador, rotulo, nivel_atual)
        if nivel_atual != "municipio":
            st.plotly_chart(figura_mapa, width="stretch", key=chave_mapa,
                            on_select=partial(_ao_clicar, chave_mapa, "sigla_uf", opcoes), selection_mode="points",
                            config={"displaylogo": False, "scrollZoom": True})
        else:
            st.plotly_chart(figura_mapa, width="stretch", key=chave_mapa,
                            config={"displaylogo": False, "scrollZoom": True})

    notas = []
    if nivel_atual != "municipio":
        notas.append("Clique numa barra ou num ponto do mapa para aprofundar; use a trilha acima para voltar.")
    else:
        notas.append(f"Proteção de dados (RN22): municípios com 1 ou 2 casos aparecem como \"≤ 2\", e taxas "
                     f"municipais só são calculadas a partir de {MINIMO_ESTAVEL} casos; no mapa, esses municípios "
                     "ficam em cinza. Em municípios pequenos, poucos casos geram taxas altas e voláteis: compare "
                     "também o número de casos (passe o mouse ou use o indicador de contagem).")
    if indicador.startswith("taxa") and nivel_atual != "municipio" and ranking.apply(
            lambda r: _instavel(indicador, r), axis=1).any():
        notas.append("Barras hachuradas: menos de 10 casos, estimativa instável (RN21).")
    if indicador in ("taxa_fem", "feminicidios") and (f.sexo != "todos" or f.grupos or f.faixas):
        notas.append("Indicadores do Sinesp seguem só os filtros de ano e território.")
    st.caption(" ".join(notas))
