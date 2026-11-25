"""TRANSFORMAÇÃO — Base 1: Sinesp VDE. Recorta os eventos, associa o código IBGE pelo par UF + nome e pivota para uma linha por município × mês."""

import pandas as pd

from etl import config, extract
from etl.padronizacao import normalizar_nome

CHAVE_MUNICIPIO_MES = ["uf", "municipio", "evento", "data_referencia"]
SEXOS = ["feminino", "masculino", "nao_informado"]


def associar_codigo_ibge(pares: pd.DataFrame, municipios: pd.DataFrame) -> pd.DataFrame:
    ref = municipios[["codigo_ibge", "nome", "codigo_uf"]].copy()
    ref["uf"] = ref["codigo_uf"].map(config.UF_CODIGO_PARA_SIGLA)
    ref["chave_nome"] = ref["nome"].map(normalizar_nome)

    pares = pares.copy()
    pares["chave_nome"] = pares["municipio"].map(normalizar_nome)
    out = pares.merge(ref[["uf", "chave_nome", "codigo_ibge"]],
                      on=["uf", "chave_nome"], how="left")

    equivalencias = out.apply(
        lambda r: config.SINESP_MUNICIPIOS_EQUIVALENCIAS.get((r["uf"], r["municipio"])), axis=1
    )
    out["codigo_ibge"] = out["codigo_ibge"].fillna(equivalencias)

    nomes_oficiais = ref.set_index("codigo_ibge")["nome"]
    out["municipio_ibge"] = out["codigo_ibge"].map(nomes_oficiais)
    return out.drop(columns="chave_nome")


def tratar_sinesp(df: pd.DataFrame, municipios: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    est = {"registros_originais": len(df)}

    df = df.copy()
    for col in ["uf", "municipio", "evento", "abrangencia"]:
        df[col] = df[col].astype("string").str.strip()
    df["uf"] = df["uf"].str.upper()
    df["municipio"] = df["municipio"].str.upper()

    df = df[df["evento"].isin(config.SINESP_EVENTOS) & (df["abrangencia"] == config.SINESP_ABRANGENCIA)]
    est["registros_recorte_tematico"] = len(df)

    nao_inf = df["municipio"] == config.SINESP_MUNICIPIO_NAO_INFORMADO
    est["registros_municipio_nao_informado"] = int(nao_inf.sum())
    est["vitimas_descartadas_municipio_nao_informado"] = int(df.loc[nao_inf, "total_vitima"].sum())
    df = df[~nao_inf]

    est["nulos_preenchidos_com_zero"] = int(df[SEXOS].isna().sum().sum())
    df[SEXOS] = df[SEXOS].fillna(0)
    inconsistentes = (df[SEXOS].sum(axis=1) != df["total_vitima"]).sum()
    if inconsistentes:
        raise ValueError(f"Sinesp: {inconsistentes} linhas com total_vitima ≠ soma por sexo")

    df = df[CHAVE_MUNICIPIO_MES + SEXOS + ["total_vitima"]]

    est["registros_duplicados_na_chave"] = int(df.duplicated(CHAVE_MUNICIPIO_MES).sum())
    vitimas_antes = int(df["total_vitima"].sum())
    df = df.groupby(CHAVE_MUNICIPIO_MES, as_index=False)[SEXOS + ["total_vitima"]].sum()
    assert int(df["total_vitima"].sum()) == vitimas_antes, "agregação alterou o total de vítimas"
    est["registros_apos_agregacao"] = len(df)

    df[SEXOS + ["total_vitima"]] = df[SEXOS + ["total_vitima"]].astype("int64")
    data = pd.to_datetime(df["data_referencia"])
    df["ano"] = data.dt.year.astype("int16")
    df["mes"] = data.dt.month.astype("int16")

    pares = df[["uf", "municipio"]].drop_duplicates()
    mapa = associar_codigo_ibge(pares, municipios)
    sem_codigo = mapa[mapa["codigo_ibge"].isna()]
    est["municipios"] = len(pares)
    est["municipios_sem_codigo_ibge"] = len(sem_codigo)
    if len(sem_codigo):
        print("  AVISO: municípios do Sinesp sem código IBGE (descartados):")
        print(sem_codigo[["uf", "municipio"]].to_string(index=False))
    df = df.merge(mapa, on=["uf", "municipio"], how="inner")

    df["evento"] = df["evento"].map(config.SINESP_EVENTOS)
    largo = df.pivot_table(
        index=["codigo_ibge", "uf", "municipio_ibge", "ano", "mes"],
        columns="evento",
        values=["feminino", "total_vitima"],
        aggfunc="sum",
        fill_value=0,
    )
    largo.columns = [
        f"sinesp_{evento}_{'fem' if medida == 'feminino' else 'total'}"
        for medida, evento in largo.columns
    ]
    ordem = [f"sinesp_{ev}_{m}" for ev in config.SINESP_EVENTOS.values() for m in ("fem", "total")]
    largo = (largo[ordem].reset_index()
             .rename(columns={"municipio_ibge": "municipio"})
             .sort_values(["uf", "municipio", "ano", "mes"], ignore_index=True))

    soma_pivot = int(largo[[c for c in ordem if c.endswith("_total")]].sum().sum())
    assert soma_pivot == vitimas_antes, "pivot alterou o total de vítimas"

    est["registros_tratados"] = len(largo)
    est["vitimas_total"] = vitimas_antes
    return largo, est


def resumo(est: dict) -> str:
    return "\n".join([
        "Base 1 — Sinesp VDE:",
        f"  Registros originais:                {est['registros_originais']:>9,}",
        f"  Após recorte temático (6 eventos):  {est['registros_recorte_tematico']:>9,}",
        f"  Município 'NÃO INFORMADO' removido: {est['registros_municipio_nao_informado']:>9,}"
        f"  ({est['vitimas_descartadas_municipio_nao_informado']} vítimas)",
        f"  Nulos por sexo preenchidos com 0:   {est['nulos_preenchidos_com_zero']:>9,}",
        f"  Linhas repetidas na chave (somadas):{est['registros_duplicados_na_chave']:>9,}",
        f"  Após agregação (mun × mês × evento):{est['registros_apos_agregacao']:>9,}",
        f"  Municípios / sem código IBGE:       {est['municipios']:>9,} / {est['municipios_sem_codigo_ibge']}",
        f"  Registros após tratamento (mun×mês):{est['registros_tratados']:>9,}",
        f"  Total de vítimas preservado:        {est['vitimas_total']:>9,}",
    ]).replace(",", ".")


if __name__ == "__main__":
    print("Lendo Sinesp VDE...")
    tratado, estatisticas = tratar_sinesp(extract.ler_sinesp(), extract.ler_municipios())
    print(resumo(estatisticas))
    print("\nColunas:", list(tratado.columns))
    print(tratado.head(3).to_string())
