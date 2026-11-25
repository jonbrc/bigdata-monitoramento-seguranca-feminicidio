"""RELACIONAMENTO — junta Sinesp e SIM por município × ano × mês (outer join) e acrescenta atributos de município, UF e população feminina."""

import pandas as pd

from etl import config
from etl.padronizacao import codigo_ibge_6
from etl.transform_sim import colunas_faixa, colunas_raca

CHAVE = ["codigo_ibge_6", "ano", "mes"]


def relacionar(sinesp: pd.DataFrame, sim: pd.DataFrame, municipios: pd.DataFrame,
               populacao: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    est = {"registros_sinesp": len(sinesp), "registros_sim": len(sim)}
    sinesp = sinesp.copy()
    sinesp["codigo_ibge_6"] = sinesp["codigo_ibge"].map(codigo_ibge_6)

    df = sinesp.merge(sim, on=CHAVE, how="outer", indicator="_origem")
    est["relacionados"] = int((df["_origem"] == "both").sum())
    est["somente_sinesp"] = int((df["_origem"] == "left_only").sum())
    est["somente_sim"] = int((df["_origem"] == "right_only").sum())
    est["obitos_somente_sim"] = int(df.loc[df["_origem"] == "right_only", "sim_obitos_fem_agressao"].sum())

    if est["somente_sim"]:
        ref = municipios.assign(
            codigo_ibge_6=municipios["codigo_ibge"].map(codigo_ibge_6),
            uf_ref=municipios["codigo_uf"].map(config.UF_CODIGO_PARA_SIGLA),
        ).set_index("codigo_ibge_6")
        so_sim = df["_origem"] == "right_only"
        df.loc[so_sim, "codigo_ibge"] = df.loc[so_sim, "codigo_ibge_6"].map(ref["codigo_ibge"])
        df.loc[so_sim, "uf"] = df.loc[so_sim, "codigo_ibge_6"].map(ref["uf_ref"])
        df.loc[so_sim, "municipio"] = df.loc[so_sim, "codigo_ibge_6"].map(ref["nome"])

    df["sim_periodo_coberto"] = [
        m in config.SIM_MESES_COBERTOS.get(a, []) for a, m in zip(df["ano"], df["mes"])
    ]
    cols_sim = ["sim_obitos_fem_agressao"] + colunas_raca() + colunas_faixa()
    for c in cols_sim:
        df[c] = df[c].astype("Int64")
        df.loc[df["sim_periodo_coberto"] & df[c].isna(), c] = 0
        df.loc[~df["sim_periodo_coberto"], c] = pd.NA

    cols_sinesp = [c for c in sinesp.columns if c.startswith("sinesp_")]
    for c in cols_sinesp:
        df[c] = df[c].astype("Int64")

    soma = df[cols_sinesp].fillna(0).sum(axis=1) + df["sim_obitos_fem_agressao"].fillna(0)
    est["linhas_sem_ocorrencia_removidas"] = int((soma == 0).sum())
    df = df[soma > 0]

    df["regiao"] = df["uf"].map(config.UF_PARA_REGIAO)

    cols_pop = [c for c in populacao.columns if c.startswith("pop_fem_")]
    df = df.merge(populacao, on="codigo_ibge", how="left")
    est["linhas_sem_populacao"] = int(df["pop_fem_total"].isna().sum())
    df[cols_pop] = df[cols_pop].astype("Int64")

    colunas = (["codigo_ibge", "uf", "regiao", "municipio", "ano", "mes"] + cols_sinesp
               + ["sim_periodo_coberto"] + cols_sim + cols_pop)
    df = (df[colunas]
          .astype({"ano": "int16", "mes": "int16"})
          .sort_values(["uf", "municipio", "ano", "mes"], ignore_index=True))
    est["registros_finais"] = len(df)
    return df, est
