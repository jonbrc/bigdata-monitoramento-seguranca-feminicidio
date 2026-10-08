"""TRANSFORMAÇÃO — Base 1: Sinesp VDE 2025.

Entrada: planilha bruta (uma linha por UF × município × mês × evento × ...).
Saída:   uma linha por município × mês, com vítimas (femininas e total) de
         cada evento do recorte em colunas, identificada pelo código IBGE.

Teste isolado (na raiz do repositório):
    python -m etl.transform_sinesp
"""

import pandas as pd

from etl import config, extract
from etl.padronizacao import normalizar_nome

CHAVE_MUNICIPIO_MES = ["uf", "municipio", "evento", "data_referencia"]
SEXOS = ["feminino", "masculino", "nao_informado"]


def associar_codigo_ibge(pares: pd.DataFrame, municipios: pd.DataFrame) -> pd.DataFrame:
    """Recebe pares únicos (uf, municipio) do Sinesp e devolve, para cada um,
    o código IBGE (7 dígitos) e o nome oficial.

    1. Casa por UF + nome normalizado (sem acento, maiúsculas, sem hífen/apóstrofo).
    2. Os que sobram são resolvidos pela lista explícita de equivalências do config.
    """
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
    """Aplica o tratamento da Base 1 e devolve (dados tratados, estatísticas)."""
    est = {"registros_originais": len(df)}

    # 1. Padronização de texto das colunas usadas como chave
    df = df.copy()
    for col in ["uf", "municipio", "evento", "abrangencia"]:
        df[col] = df[col].astype("string").str.strip()
    df["uf"] = df["uf"].str.upper()
    df["municipio"] = df["municipio"].str.upper()

    # 2. Recorte temático: eventos de violência letal / contra a mulher, registro estadual
    df = df[df["evento"].isin(config.SINESP_EVENTOS) & (df["abrangencia"] == config.SINESP_ABRANGENCIA)]
    est["registros_recorte_tematico"] = len(df)

    # 3. Município "NÃO INFORMADO" (AI02: tratar como nulo). Sem município não há como
    #    relacionar com o SIM; as linhas saem e as vítimas descartadas são contabilizadas.
    nao_inf = df["municipio"] == config.SINESP_MUNICIPIO_NAO_INFORMADO
    est["registros_municipio_nao_informado"] = int(nao_inf.sum())
    est["vitimas_descartadas_municipio_nao_informado"] = int(df.loc[nao_inf, "total_vitima"].sum())
    df = df[~nao_inf]

    # 4. Nulos nas colunas por sexo. Em todas as linhas, total_vitima está preenchido e é
    #    igual à soma feminino + masculino + nao_informado (com nulo = 0). O nulo significa
    #    "nenhuma vítima nessa categoria", então é preenchido com 0.
    est["nulos_preenchidos_com_zero"] = int(df[SEXOS].isna().sum().sum())
    df[SEXOS] = df[SEXOS].fillna(0)
    inconsistentes = (df[SEXOS].sum(axis=1) != df["total_vitima"]).sum()
    if inconsistentes:
        raise ValueError(f"Sinesp: {inconsistentes} linhas com total_vitima ≠ soma por sexo")

    # 5. Colunas sem uso no recorte (100% nulas ou constantes) saem
    df = df[CHAVE_MUNICIPIO_MES + SEXOS + ["total_vitima"]]

    # 6. Duplicidades: o DF aparece com várias linhas por mês/evento, todas com o nome
    #    "BRASÍLIA" (provavelmente uma por região administrativa). Não são cópias a
    #    descartar: as linhas são somadas para obter o total do município.
    est["registros_duplicados_na_chave"] = int(df.duplicated(CHAVE_MUNICIPIO_MES).sum())
    vitimas_antes = int(df["total_vitima"].sum())
    df = df.groupby(CHAVE_MUNICIPIO_MES, as_index=False)[SEXOS + ["total_vitima"]].sum()
    assert int(df["total_vitima"].sum()) == vitimas_antes, "agregação alterou o total de vítimas"
    est["registros_apos_agregacao"] = len(df)

    # 7. Tipos: contagens inteiras; data -> ano e mês
    df[SEXOS + ["total_vitima"]] = df[SEXOS + ["total_vitima"]].astype("int64")
    data = pd.to_datetime(df["data_referencia"])
    df["ano"] = data.dt.year.astype("int16")
    df["mes"] = data.dt.month.astype("int16")

    # 8. Código IBGE (chave de relacionamento com o SIM)
    pares = df[["uf", "municipio"]].drop_duplicates()
    mapa = associar_codigo_ibge(pares, municipios)
    sem_codigo = mapa[mapa["codigo_ibge"].isna()]
    est["municipios"] = len(pares)
    est["municipios_sem_codigo_ibge"] = len(sem_codigo)
    if len(sem_codigo):
        print("  AVISO: municípios do Sinesp sem código IBGE (descartados):")
        print(sem_codigo[["uf", "municipio"]].to_string(index=False))
    df = df.merge(mapa, on=["uf", "municipio"], how="inner")

    # 9. Pivot: um evento por coluna (vítimas femininas e total), uma linha por município × mês
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

    # Conferência: total de vítimas preservado no pivot
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
