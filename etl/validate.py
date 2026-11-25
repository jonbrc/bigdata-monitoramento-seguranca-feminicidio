"""VALIDAÇÃO — verificações do painel e do detalhamento do SIM (chave, nulos, domínios e totais); se alguma falhar, nada é gravado."""

import pandas as pd

from etl import config
from etl.transform_sim import colunas_faixa, colunas_raca

COLUNAS_ID = ["codigo_ibge", "uf", "regiao", "municipio", "ano", "mes"]


def validar(df: pd.DataFrame, est_sinesp: dict, est_sim: dict, est_rel: dict) -> list[tuple[str, bool]]:
    cols_sinesp = [c for c in df.columns if c.startswith("sinesp_")]
    cols_sim = [c for c in df.columns if c.startswith("sim_obitos")]
    cols_sinesp_total = [c for c in cols_sinesp if c.endswith("_total")]
    sim_coberto = df["sim_periodo_coberto"]

    checks = [
        ("Resultado não está vazio", len(df) > 0),
        ("Chave codigo_ibge + ano + mes é única", not df.duplicated(["codigo_ibge", "ano", "mes"]).any()),
        ("Sem nulos nas colunas de identificação", not df[COLUNAS_ID].isna().any().any()),
        ("codigo_ibge com 7 dígitos numéricos", df["codigo_ibge"].astype(str).str.fullmatch(r"\d{7}").all()),
        ("UF com 2 letras maiúsculas", df["uf"].str.fullmatch(r"[A-Z]{2}").all()),
        ("Mês entre 1 e 12", df["mes"].between(1, 12).all()),
        ("Sem contagens negativas", not (df[cols_sinesp + cols_sim].fillna(0) < 0).any().any()),
        ("SIM sem nulos nos meses cobertos", not df.loc[sim_coberto, cols_sim].isna().any().any()),
        ("SIM nulo nos meses não cobertos", df.loc[~sim_coberto, cols_sim].isna().all().all()),
        ("Vítimas femininas ≤ total em cada evento do Sinesp",
         all((df[c.replace("_total", "_fem")].fillna(0) <= df[c].fillna(0)).all() for c in cols_sinesp_total)),
        ("Soma por raça/cor = total de óbitos do SIM",
         (df[colunas_raca()].fillna(0).sum(axis=1) == df["sim_obitos_fem_agressao"].fillna(0)).all()),
        ("Soma por faixa etária = total de óbitos do SIM",
         (df[colunas_faixa()].fillna(0).sum(axis=1) == df["sim_obitos_fem_agressao"].fillna(0)).all()),
        ("População feminina presente em todas as linhas",
         not df[[c for c in df.columns if c.startswith("pop_fem_")]].isna().any().any()),
        ("População total ≥ soma das populações por cor/raça",
         (df["pop_fem_total"] >= df[["pop_fem_branca", "pop_fem_preta", "pop_fem_amarela",
                                     "pop_fem_parda", "pop_fem_indigena"]].sum(axis=1)).all()),
        ("Total de vítimas do Sinesp preservado após o relacionamento",
         int(df[cols_sinesp_total].fillna(0).sum().sum()) == est_sinesp["vitimas_total"]),
        ("Total de óbitos do SIM preservado após o relacionamento",
         int(df["sim_obitos_fem_agressao"].fillna(0).sum()) == est_sim["obitos_fem"]),
    ]
    return checks


def validar_detalhamento(det: pd.DataFrame, painel: pd.DataFrame, est_sim: dict) -> list[tuple[str, bool]]:
    categorias = {
        "sexo": set(config.SIM_SEXO.values()),
        "raca_cor": set(config.SIM_RACACOR.values()) | {config.SIM_RACACOR_IGNORADA},
        "faixa_etaria": {f for _, _, f in config.SIM_FAIXAS_ETARIAS} | {config.SIM_FAIXA_IGNORADA},
        "local_obito": set(config.SIM_LOCAL_OBITO.values()) | {config.SIM_LOCAL_IGNORADO},
        "meio_agressao": set(config.SIM_MEIO_AGRESSAO.values()),
    }
    chave = ["codigo_ibge", "ano", "mes"] + list(categorias)
    fem = det[det["sexo"] == "feminino"]
    por_mes = fem.groupby(["codigo_ibge", "ano", "mes"])["obitos"].sum()
    painel_mes = painel[painel["sim_periodo_coberto"]].set_index(["codigo_ibge", "ano", "mes"])["sim_obitos_fem_agressao"]
    painel_mes = painel_mes[painel_mes > 0].astype("int64")
    return [
        ("Detalhamento do SIM não está vazio", len(det) > 0),
        ("Chave do detalhamento é única", not det.duplicated(chave).any()),
        ("Sem nulos no detalhamento", not det.isna().any().any()),
        ("Categorias do detalhamento são as previstas",
         all(set(det[c].unique()) <= v for c, v in categorias.items())),
        ("Óbitos do detalhamento são positivos", bool((det["obitos"] > 0).all())),
        ("Só meses cobertos pelo SIM no detalhamento",
         all(m in config.SIM_MESES_COBERTOS.get(a, []) for a, m in zip(det["ano"], det["mes"]))),
        ("Total do detalhamento = óbitos tratados do SIM", int(det["obitos"].sum()) == est_sim["registros_tratados"]),
        ("Óbitos femininos do detalhamento = painel, por município × mês",
         por_mes.sort_index().equals(painel_mes.sort_index())),
    ]
