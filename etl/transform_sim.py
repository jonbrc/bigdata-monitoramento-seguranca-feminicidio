"""TRANSFORMAÇÃO — Base 2: SIM 2025 (preliminar).

Entrada: CSV bruto (uma linha por declaração de óbito), lido em blocos e já
         filtrado durante a leitura (mulheres, causa básica X85–Y09).
Saída:   uma linha por município de residência × mês, com o número de óbitos
         femininos por agressão, no total, por raça/cor e por faixa etária.

Teste isolado (na raiz do repositório):
    python -m etl.transform_sim
"""

import pandas as pd

from etl import config, extract
from etl.padronizacao import codigo_ibge_6, idade_em_anos

CHAVE = ["codigo_ibge_6", "ano", "mes"]


def colunas_raca() -> list[str]:
    categorias = list(config.SIM_RACACOR.values()) + [config.SIM_RACACOR_IGNORADA]
    return [f"sim_obitos_fem_{c}" for c in categorias]


def colunas_faixa() -> list[str]:
    categorias = [f for _, _, f in config.SIM_FAIXAS_ETARIAS] + [config.SIM_FAIXA_IGNORADA]
    return [f"sim_obitos_fem_{c}" for c in categorias]


def classificar_faixa(anos: pd.Series) -> pd.Series:
    """Idade em anos -> sufixo da faixa etária (config.SIM_FAIXAS_ETARIAS)."""
    faixa = pd.Series(config.SIM_FAIXA_IGNORADA, index=anos.index, dtype="object")
    for minimo, maximo, nome in config.SIM_FAIXAS_ETARIAS:
        dentro = anos.ge(minimo) & (anos.le(maximo) if maximo is not None else True)
        faixa[dentro.fillna(False).astype(bool)] = nome
    return faixa


def _contar(df: pd.DataFrame, coluna: str, categorias: list[str]) -> pd.DataFrame:
    """Conta óbitos por município × mês para cada categoria de `coluna`."""
    t = (df.pivot_table(index=CHAVE, columns=coluna, values="DTOBITO",
                        aggfunc="count", fill_value=0)
         .reindex(columns=categorias, fill_value=0))
    t.columns = [f"sim_obitos_fem_{c}" for c in t.columns]
    return t.astype("int64")


def tratar_sim(df: pd.DataFrame, total_lido: int, municipios: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Aplica o tratamento da Base 2 e devolve (dados agregados, estatísticas)."""
    est = {"registros_originais": total_lido, "registros_recorte_tematico": len(df)}
    df = df.copy()

    # 1. Duplicidades. `contador` é único por linha, mas é só um número sequencial do
    #    arquivo. Linhas idênticas em todas as demais colunas seriam a mesma declaração
    #    repetida e são removidas (no arquivo atual não há nenhuma dentro do recorte).
    colunas_sem_contador = [c for c in df.columns if c != "contador"]
    duplicadas = df.duplicated(colunas_sem_contador)
    est["duplicados_removidos"] = int(duplicadas.sum())
    df = df[~duplicadas]

    # 2. Mantém só as colunas mapeadas na AI02 (descarta, entre outras, DTNASC e
    #    dados da mãe, que não são usados — minimização de dados, LGPD).
    df = df[config.SIM_COLUNAS_AI02].copy()

    # 3. Padronização de texto nos campos de código
    for col in config.SIM_COLUNAS_AI02:
        df[col] = df[col].str.strip()
    df["CAUSABAS"] = df["CAUSABAS"].str.replace("*", "", regex=False).str.upper()

    # Conferência do recorte (o filtro já foi aplicado na leitura)
    cid3 = df["CAUSABAS"].str[:3]
    fora = ~((df["SEXO"] == config.SIM_SEXO_FEMININO)
             & cid3.between(config.SIM_CID_AGRESSAO_INICIO, config.SIM_CID_AGRESSAO_FIM))
    if fora.any():
        raise ValueError(f"SIM: {int(fora.sum())} registros fora do recorte após a leitura")

    # 4. Datas: DTOBITO "ddmmaaaa" -> data -> ano e mês. Datas inválidas saem.
    data = pd.to_datetime(df["DTOBITO"], format="%d%m%Y", errors="coerce")
    est["datas_invalidas_removidas"] = int(data.isna().sum())
    df = df[data.notna()].copy()
    df["ano"] = data[data.notna()].dt.year.astype("int16")
    df["mes"] = data[data.notna()].dt.month.astype("int16")

    # Óbitos fora do período considerado coberto (não deve haver; se houver, são contados)
    fora_periodo = (df["ano"] != config.SIM_ANO) | (~df["mes"].isin(config.SIM_MESES_COBERTOS))
    est["fora_periodo_coberto_removidos"] = int(fora_periodo.sum())
    df = df[~fora_periodo]

    # 5. Município de residência (chave de relacionamento, AI02).
    #    Código terminado em "0000" = município ignorado (só a UF é conhecida): não pode ser
    #    relacionado a nenhum município e sai. Códigos fora da tabela IBGE também saem.
    ibge6 = set(municipios["codigo_ibge"].map(codigo_ibge_6))
    ignorado = df["CODMUNRES"].str.endswith("0000", na=True)
    fora_tabela = ~ignorado & ~df["CODMUNRES"].isin(ibge6)
    est["municipio_residencia_ignorado"] = int(ignorado.sum())
    est["municipio_fora_tabela_ibge"] = int(fora_tabela.sum())
    df = df[~ignorado & ~fora_tabela].rename(columns={"CODMUNRES": "codigo_ibge_6"})
    est["registros_tratados"] = len(df)

    # 6. Raça/cor: código -> categoria; ausente ou não previsto -> "raca_ignorada"
    est["racacor_nulo_ou_ignorado"] = int((~df["RACACOR"].isin(config.SIM_RACACOR)).sum())
    df["raca_cor"] = df["RACACOR"].map(config.SIM_RACACOR).fillna(config.SIM_RACACOR_IGNORADA)

    # 7. Idade: campo IDADE decodificado (unidade + quantidade) e classificado em faixas;
    #    "999" ou inválido -> faixa "idade_ignorada"
    df["faixa_etaria"] = classificar_faixa(idade_em_anos(df["IDADE"]))
    est["idade_ignorada"] = int((df["faixa_etaria"] == config.SIM_FAIXA_IGNORADA).sum())

    # 8. Agregação: um registro por município × mês (total, por raça/cor e por faixa etária)
    por_raca = _contar(df, "raca_cor",
                       list(config.SIM_RACACOR.values()) + [config.SIM_RACACOR_IGNORADA])
    por_faixa = _contar(df, "faixa_etaria",
                        [f for _, _, f in config.SIM_FAIXAS_ETARIAS] + [config.SIM_FAIXA_IGNORADA])
    agregado = por_raca.join(por_faixa, how="outer").fillna(0).astype("int64")
    agregado.insert(0, "sim_obitos_fem_agressao", agregado[colunas_raca()].sum(axis=1))
    agregado = agregado.reset_index()

    assert int(agregado["sim_obitos_fem_agressao"].sum()) == len(df), "agregação alterou o total de óbitos"
    assert (agregado[colunas_faixa()].sum(axis=1) == agregado["sim_obitos_fem_agressao"]).all(), \
        "soma das faixas etárias difere do total"
    assert not agregado.duplicated(CHAVE).any()

    est["registros_agregados"] = len(agregado)
    est["municipios_com_obito"] = agregado["codigo_ibge_6"].nunique()
    est["obitos_por_raca"] = {c.removeprefix("sim_obitos_fem_"): int(agregado[c].sum()) for c in colunas_raca()}
    est["obitos_por_faixa"] = {c.removeprefix("sim_obitos_fem_"): int(agregado[c].sum()) for c in colunas_faixa()}
    return agregado, est


def ler_e_tratar_sim(municipios: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Extração com filtro durante a leitura + tratamento."""
    bruto, total = extract.ler_sim_filtrado(extract.filtro_feminino_agressao)
    return tratar_sim(bruto, total, municipios)


def resumo(est: dict) -> str:
    return "\n".join([
        "Base 2 — SIM:",
        f"  Registros originais:                     {est['registros_originais']:>9,}",
        f"  Após recorte (mulheres e X85–Y09):       {est['registros_recorte_tematico']:>9,}",
        f"  Duplicados removidos:                    {est['duplicados_removidos']:>9,}",
        f"  Datas inválidas removidas:               {est['datas_invalidas_removidas']:>9,}",
        f"  Fora do período coberto removidos:       {est['fora_periodo_coberto_removidos']:>9,}",
        f"  Município de residência ignorado:        {est['municipio_residencia_ignorado']:>9,}",
        f"  Município fora da tabela IBGE:           {est['municipio_fora_tabela_ibge']:>9,}",
        f"  Registros após tratamento (óbitos):      {est['registros_tratados']:>9,}",
        f"  Raça/cor nula ou ignorada:               {est['racacor_nulo_ou_ignorado']:>9,}",
        f"  Idade ignorada:                          {est['idade_ignorada']:>9,}",
        f"  Agregado (município × mês):              {est['registros_agregados']:>9,}",
        f"  Municípios com ao menos um óbito:        {est['municipios_com_obito']:>9,}",
    ]).replace(",", ".") + "\n  Óbitos por raça/cor: " + "; ".join(
        f"{raca}={n}" for raca, n in est["obitos_por_raca"].items()) + \
        "\n  Óbitos por faixa etária: " + "; ".join(
        f"{faixa}={n}" for faixa, n in est["obitos_por_faixa"].items())


if __name__ == "__main__":
    print("Lendo SIM em blocos...")
    agregado, estatisticas = ler_e_tratar_sim(extract.ler_municipios())
    print(resumo(estatisticas))
    print("\nColunas:", list(agregado.columns))
    print(agregado.head(3).to_string())
