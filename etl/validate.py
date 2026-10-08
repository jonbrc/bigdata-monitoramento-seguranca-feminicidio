"""VALIDAÇÃO — verificações sobre o resultado final antes da gravação.

Cada verificação devolve (descrição, ok). Se alguma falhar, o ETL é
interrompido e o CSV não é gravado.
"""

import pandas as pd

COLUNAS_ID = ["codigo_ibge", "uf", "municipio", "ano", "mes"]


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
         (df[cols_sim[1:]].fillna(0).sum(axis=1) == df["sim_obitos_fem_agressao"].fillna(0)).all()),
        ("Total de vítimas do Sinesp preservado após o relacionamento",
         int(df[cols_sinesp_total].fillna(0).sum().sum()) == est_sinesp["vitimas_total"]),
        ("Total de óbitos do SIM preservado após o relacionamento",
         int(df["sim_obitos_fem_agressao"].fillna(0).sum()) == est_sim["registros_tratados"]),
    ]
    return checks
