"""RELACIONAMENTO — Sinesp × SIM.

Chave:  Sinesp.codigo_ibge (7 dígitos, derivado de UF + nome) → 6 primeiros dígitos
        + ano + mês
            ↕
        SIM.CODMUNRES (6 dígitos) + ano e mês de DTOBITO

Tipo: FULL OUTER JOIN na grade município × mês. A grade do Sinesp já cobre
todos os municípios em todos os meses; o outer join garante que nenhum óbito
do SIM se perca caso o município não exista no Sinesp.
"""

import pandas as pd

from etl import config
from etl.padronizacao import codigo_ibge_6
from etl.transform_sim import colunas_raca

CHAVE = ["codigo_ibge_6", "ano", "mes"]


def relacionar(sinesp: pd.DataFrame, sim: pd.DataFrame,
               municipios: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    est = {"registros_sinesp": len(sinesp), "registros_sim": len(sim)}
    sinesp = sinesp.copy()
    sinesp["codigo_ibge_6"] = sinesp["codigo_ibge"].map(codigo_ibge_6)

    df = sinesp.merge(sim, on=CHAVE, how="outer", indicator="_origem")
    est["relacionados"] = int((df["_origem"] == "both").sum())
    est["somente_sinesp"] = int((df["_origem"] == "left_only").sum())
    est["somente_sim"] = int((df["_origem"] == "right_only").sum())
    est["obitos_somente_sim"] = int(df.loc[df["_origem"] == "right_only", "sim_obitos_fem_agressao"].sum())

    # Linhas que só existem no SIM: identificação do município vem da tabela IBGE;
    # as colunas do Sinesp ficam nulas (sem dado, e não zero).
    if est["somente_sim"]:
        ref = municipios.assign(
            codigo_ibge_6=municipios["codigo_ibge"].map(codigo_ibge_6),
            uf_ref=municipios["codigo_uf"].map(config.UF_CODIGO_PARA_SIGLA),
        ).set_index("codigo_ibge_6")
        so_sim = df["_origem"] == "right_only"
        df.loc[so_sim, "codigo_ibge"] = df.loc[so_sim, "codigo_ibge_6"].map(ref["codigo_ibge"])
        df.loc[so_sim, "uf"] = df.loc[so_sim, "codigo_ibge_6"].map(ref["uf_ref"])
        df.loc[so_sim, "municipio"] = df.loc[so_sim, "codigo_ibge_6"].map(ref["nome"])

    # Cobertura do SIM (base preliminar): nos meses cobertos, ausência de óbito = 0;
    # nos meses não cobertos, as colunas do SIM ficam nulas (sem dado).
    df["sim_periodo_coberto"] = (df["ano"] == config.SIM_ANO) & df["mes"].isin(config.SIM_MESES_COBERTOS)
    cols_sim = ["sim_obitos_fem_agressao"] + colunas_raca()
    for c in cols_sim:
        df[c] = df[c].astype("Int64")
        df.loc[df["sim_periodo_coberto"] & df[c].isna(), c] = 0
        df.loc[~df["sim_periodo_coberto"], c] = pd.NA

    cols_sinesp = [c for c in sinesp.columns if c.startswith("sinesp_")]
    for c in cols_sinesp:
        df[c] = df[c].astype("Int64")

    # Remoção de linhas sem ocorrência (AI02, otimização de volume): todas as contagens
    # das duas bases iguais a zero (ou sem dado).
    soma = df[cols_sinesp].fillna(0).sum(axis=1) + df["sim_obitos_fem_agressao"].fillna(0)
    est["linhas_sem_ocorrencia_removidas"] = int((soma == 0).sum())
    df = df[soma > 0]

    # Colunas auxiliares saem; ordem final
    colunas = (["codigo_ibge", "uf", "municipio", "ano", "mes"] + cols_sinesp
               + ["sim_periodo_coberto"] + cols_sim)
    df = (df[colunas]
          .astype({"ano": "int16", "mes": "int16"})
          .sort_values(["uf", "municipio", "ano", "mes"], ignore_index=True))
    est["registros_finais"] = len(df)
    return df, est
