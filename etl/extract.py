"""EXTRAÇÃO — leitura das bases brutas.

Este módulo só lê os arquivos de data/raw e data/reference; nunca grava
nada neles.
"""

from collections.abc import Callable, Iterator

import pandas as pd

from etl import config


def _verificar_arquivo(caminho) -> None:
    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {caminho}\n"
            "Copie as bases brutas para data/raw/ (ver README, seção "
            "'Preparação dos dados brutos')."
        )


# ---------------------------------------------------------------------------
# Base 1 — Sinesp VDE
# ---------------------------------------------------------------------------
def ler_sinesp_ano(ano: int) -> pd.DataFrame:
    arquivo = config.SINESP_ARQUIVOS[ano]
    _verificar_arquivo(arquivo)
    return pd.read_excel(arquivo, sheet_name=str(ano), engine=config.SINESP_EXCEL_ENGINE)


def ler_sinesp() -> pd.DataFrame:
    return pd.concat([ler_sinesp_ano(ano) for ano in config.ANOS], ignore_index=True)


# ---------------------------------------------------------------------------
# Base 2 — SIM
# ---------------------------------------------------------------------------
def iterar_sim(ano: int, usecols: list[str] | None = None) -> Iterator[pd.DataFrame]:
    """Lê o CSV do SIM em blocos.

    Todas as colunas entram como texto: os campos do SIM são códigos
    (ex.: CODESTAB "0000655", datas "ddmmaaaa") e a conversão numérica
    automática perderia zeros à esquerda. A tipagem é feita na transformação.
    """
    arquivo = config.SIM_ARQUIVOS[ano]
    _verificar_arquivo(arquivo)
    yield from pd.read_csv(
        arquivo,
        sep=config.SIM_SEPARATOR,
        encoding=config.SIM_ENCODING,
        dtype=str,
        usecols=usecols,
        chunksize=config.SIM_CHUNKSIZE,
    )


def ler_sim_filtrado(
    ano: int,
    filtro: Callable[[pd.DataFrame], pd.Series],
    usecols: list[str] | None = None,
) -> tuple[pd.DataFrame, int]:
    """Lê o SIM em blocos aplicando `filtro` durante a leitura.

    Retorna (registros filtrados, total de registros lidos). Só o subconjunto
    filtrado fica em memória, como previsto na AI02.
    """
    partes, total = [], 0
    for bloco in iterar_sim(ano, usecols):
        total += len(bloco)
        partes.append(bloco[filtro(bloco)])
    return pd.concat(partes, ignore_index=True), total


def filtro_feminino_agressao(df: pd.DataFrame) -> pd.Series:
    """Recorte da AI02: SEXO feminino e CAUSABAS entre X85 e Y09."""
    cid3 = df["CAUSABAS"].str.replace("*", "", regex=False).str.strip().str[:3]
    return (
        (df["SEXO"] == config.SIM_SEXO_FEMININO)
        & (cid3 >= config.SIM_CID_AGRESSAO_INICIO)
        & (cid3 <= config.SIM_CID_AGRESSAO_FIM)
    )


# ---------------------------------------------------------------------------
# Referência — municípios IBGE
# ---------------------------------------------------------------------------
def ler_populacao_detalhada() -> pd.DataFrame:
    _verificar_arquivo(config.POPULACAO_FILE)
    return pd.read_csv(config.POPULACAO_FILE, dtype={"codigo_ibge": str})


def ler_populacao() -> pd.DataFrame:
    pop = ler_populacao_detalhada()
    cols = [c for c in pop.columns if c.startswith("pop_")]
    fem = pop[pop["sexo"] == "feminino"].groupby("codigo_ibge", as_index=False)[cols].sum()
    return fem.rename(columns={c: c.replace("pop_", "pop_fem_") for c in cols})


def ler_municipios() -> pd.DataFrame:
    """Lê a tabela de municípios com código IBGE de 7 dígitos."""
    _verificar_arquivo(config.MUNICIPIOS_FILE)
    return pd.read_csv(
        config.MUNICIPIOS_FILE,
        encoding=config.MUNICIPIOS_ENCODING,
        dtype={"codigo_ibge": str},
    )
