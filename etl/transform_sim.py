"""TRANSFORMAÇÃO — Base 2: SIM. Trata os óbitos por agressão (CID-10 X85–Y09, ambos os sexos) e gera o painel feminino por município × mês e o detalhamento sexo × raça/cor × faixa etária × local × meio."""

import pandas as pd

from etl import config, extract
from etl.padronizacao import codigo_ibge_6, idade_em_anos

CHAVE = ["codigo_ibge_6", "ano", "mes"]
DIMENSOES = ["sexo", "raca_cor", "faixa_etaria", "local_obito", "meio_agressao"]


def colunas_raca() -> list[str]:
    categorias = list(config.SIM_RACACOR.values()) + [config.SIM_RACACOR_IGNORADA]
    return [f"sim_obitos_fem_{c}" for c in categorias]


def colunas_faixa() -> list[str]:
    categorias = [f for _, _, f in config.SIM_FAIXAS_ETARIAS] + [config.SIM_FAIXA_IGNORADA]
    return [f"sim_obitos_fem_{c}" for c in categorias]


def classificar_faixa(anos: pd.Series) -> pd.Series:
    faixa = pd.Series(config.SIM_FAIXA_IGNORADA, index=anos.index, dtype="object")
    for minimo, maximo, nome in config.SIM_FAIXAS_ETARIAS:
        dentro = anos.ge(minimo) & (anos.le(maximo) if maximo is not None else True)
        faixa[dentro.fillna(False).astype(bool)] = nome
    return faixa


def _contar(df: pd.DataFrame, coluna: str, categorias: list[str]) -> pd.DataFrame:
    t = (df.pivot_table(index=CHAVE, columns=coluna, values="DTOBITO",
                        aggfunc="count", fill_value=0)
         .reindex(columns=categorias, fill_value=0))
    t.columns = [f"sim_obitos_fem_{c}" for c in t.columns]
    return t.astype("int64")


def painel_feminino(df: pd.DataFrame) -> pd.DataFrame:
    fem = df[df["sexo"] == "feminino"]
    por_raca = _contar(fem, "raca_cor",
                       list(config.SIM_RACACOR.values()) + [config.SIM_RACACOR_IGNORADA])
    por_faixa = _contar(fem, "faixa_etaria",
                        [f for _, _, f in config.SIM_FAIXAS_ETARIAS] + [config.SIM_FAIXA_IGNORADA])
    agregado = por_raca.join(por_faixa, how="outer").fillna(0).astype("int64")
    agregado.insert(0, "sim_obitos_fem_agressao", agregado[colunas_raca()].sum(axis=1))
    agregado = agregado.reset_index()

    assert int(agregado["sim_obitos_fem_agressao"].sum()) == len(fem), "agregação alterou o total de óbitos"
    assert (agregado[colunas_faixa()].sum(axis=1) == agregado["sim_obitos_fem_agressao"]).all(), \
        "soma das faixas etárias difere do total"
    assert not agregado.duplicated(CHAVE).any()
    return agregado


def detalhamento(df: pd.DataFrame, municipios: pd.DataFrame) -> pd.DataFrame:
    ref = municipios.assign(codigo_ibge_6=municipios["codigo_ibge"].map(codigo_ibge_6))
    ref = ref.set_index("codigo_ibge_6")
    det = (df.groupby(CHAVE + DIMENSOES, as_index=False)
           .size().rename(columns={"size": "obitos"}))
    det.insert(0, "codigo_ibge", det["codigo_ibge_6"].map(ref["codigo_ibge"]))
    det.insert(1, "uf", det["codigo_ibge_6"].map(
        ref["codigo_uf"].map(config.UF_CODIGO_PARA_SIGLA)))
    det = det.drop(columns="codigo_ibge_6").astype({"ano": "int16", "mes": "int16", "obitos": "int64"})
    assert int(det["obitos"].sum()) == len(df), "detalhamento alterou o total de óbitos"
    return det.sort_values(["codigo_ibge", "ano", "mes"] + DIMENSOES, ignore_index=True)


def tratar_sim(df: pd.DataFrame, total_lido: int,
               municipios: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    est = {"registros_originais": total_lido, "registros_recorte_tematico": len(df)}
    df = df.copy()

    colunas_sem_contador = [c for c in df.columns if c not in ("contador", "arquivo_ano")]
    duplicadas = df.duplicated(colunas_sem_contador + ["arquivo_ano"])
    est["duplicados_removidos"] = int(duplicadas.sum())
    df = df[~duplicadas]

    df = df[config.SIM_COLUNAS_AI02].copy()
    for col in config.SIM_COLUNAS_AI02:
        df[col] = df[col].str.strip()
    df["CAUSABAS"] = df["CAUSABAS"].str.replace("*", "", regex=False).str.upper()

    cid3 = df["CAUSABAS"].str[:3]
    fora = ~cid3.between(config.SIM_CID_AGRESSAO_INICIO, config.SIM_CID_AGRESSAO_FIM)
    if fora.any():
        raise ValueError(f"SIM: {int(fora.sum())} registros fora do recorte após a leitura")

    data = pd.to_datetime(df["DTOBITO"], format="%d%m%Y", errors="coerce")
    est["datas_invalidas_removidas"] = int(data.isna().sum())
    df = df[data.notna()].copy()
    df["ano"] = data[data.notna()].dt.year.astype("int16")
    df["mes"] = data[data.notna()].dt.month.astype("int16")

    coberto = pd.Series(
        [m in config.SIM_MESES_COBERTOS.get(a, []) for a, m in zip(df["ano"], df["mes"])],
        index=df.index,
    )
    est["fora_periodo_coberto_removidos"] = int((~coberto).sum())
    df = df[coberto]

    df["sexo"] = df["SEXO"].map(config.SIM_SEXO)
    est["sexo_ignorado_removidos"] = int(df["sexo"].isna().sum())
    df = df[df["sexo"].notna()]

    ibge6 = set(municipios["codigo_ibge"].map(codigo_ibge_6))
    ignorado = df["CODMUNRES"].str.endswith("0000", na=True)
    fora_tabela = ~ignorado & ~df["CODMUNRES"].isin(ibge6)
    est["municipio_residencia_ignorado"] = int(ignorado.sum())
    est["municipio_fora_tabela_ibge"] = int(fora_tabela.sum())
    df = df[~ignorado & ~fora_tabela].rename(columns={"CODMUNRES": "codigo_ibge_6"})

    est["racacor_nulo_ou_ignorado"] = int((~df["RACACOR"].isin(config.SIM_RACACOR)).sum())
    df["raca_cor"] = df["RACACOR"].map(config.SIM_RACACOR).fillna(config.SIM_RACACOR_IGNORADA)

    df["faixa_etaria"] = classificar_faixa(idade_em_anos(df["IDADE"]))
    est["idade_ignorada"] = int((df["faixa_etaria"] == config.SIM_FAIXA_IGNORADA).sum())

    df["local_obito"] = df["LOCOCOR"].map(config.SIM_LOCAL_OBITO).fillna(config.SIM_LOCAL_IGNORADO)
    est["local_ignorado"] = int((df["local_obito"] == config.SIM_LOCAL_IGNORADO).sum())

    df["meio_agressao"] = df["CAUSABAS"].str[:3].map(config.SIM_MEIO_AGRESSAO)
    if df["meio_agressao"].isna().any():
        raise ValueError("SIM: CID de agressão sem meio mapeado em SIM_MEIO_AGRESSAO")

    est["registros_tratados"] = len(df)
    est["obitos_por_sexo"] = df["sexo"].value_counts().to_dict()
    est["obitos_fem"] = int((df["sexo"] == "feminino").sum())
    fem = df[df["sexo"] == "feminino"]
    est["fem_residencia_diferente_ocorrencia"] = float((fem["codigo_ibge_6"] != fem["CODMUNOCOR"]).mean())

    agregado = painel_feminino(df)
    detalhado = detalhamento(df, municipios)

    est["registros_agregados"] = len(agregado)
    est["registros_detalhados"] = len(detalhado)
    est["municipios_com_obito"] = agregado["codigo_ibge_6"].nunique()
    est["obitos_por_raca"] = {c.removeprefix("sim_obitos_fem_"): int(agregado[c].sum()) for c in colunas_raca()}
    est["obitos_por_faixa"] = {c.removeprefix("sim_obitos_fem_"): int(agregado[c].sum()) for c in colunas_faixa()}
    est["obitos_por_local"] = df["local_obito"].value_counts().to_dict()
    est["obitos_por_meio"] = df["meio_agressao"].value_counts().to_dict()
    return agregado, detalhado, est


def ler_e_tratar_sim(municipios: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    partes, total = [], 0
    for ano in config.ANOS:
        bruto, lidos = extract.ler_sim_filtrado(ano, extract.filtro_agressao)
        partes.append(bruto.assign(arquivo_ano=ano))
        total += lidos
    return tratar_sim(pd.concat(partes, ignore_index=True), total, municipios)


def resumo(est: dict) -> str:
    def dist(d: dict) -> str:
        return "; ".join(f"{k}={v}" for k, v in d.items())
    return "\n".join([
        "Base 2 — SIM:",
        f"  Registros originais:                     {est['registros_originais']:>9,}",
        f"  Após recorte (agressão X85–Y09):         {est['registros_recorte_tematico']:>9,}",
        f"  Duplicados removidos:                    {est['duplicados_removidos']:>9,}",
        f"  Datas inválidas removidas:               {est['datas_invalidas_removidas']:>9,}",
        f"  Fora do período coberto removidos:       {est['fora_periodo_coberto_removidos']:>9,}",
        f"  Sexo ignorado removidos:                 {est['sexo_ignorado_removidos']:>9,}",
        f"  Município de residência ignorado:        {est['municipio_residencia_ignorado']:>9,}",
        f"  Município fora da tabela IBGE:           {est['municipio_fora_tabela_ibge']:>9,}",
        f"  Registros após tratamento (óbitos):      {est['registros_tratados']:>9,}",
        f"  Óbitos femininos:                        {est['obitos_fem']:>9,}",
        f"  Raça/cor nula ou ignorada:               {est['racacor_nulo_ou_ignorado']:>9,}",
        f"  Idade ignorada:                          {est['idade_ignorada']:>9,}",
        f"  Local do óbito ignorado:                 {est['local_ignorado']:>9,}",
        f"  Painel feminino (município × mês):       {est['registros_agregados']:>9,}",
        f"  Detalhamento (linhas):                   {est['registros_detalhados']:>9,}",
        f"  Municípios com óbito feminino:           {est['municipios_com_obito']:>9,}",
    ]).replace(",", ".") + "\n".join([
        "",
        f"  Óbitos por sexo: {dist(est['obitos_por_sexo'])}",
        f"  Óbitos femininos por raça/cor: {dist(est['obitos_por_raca'])}",
        f"  Óbitos femininos por faixa etária: {dist(est['obitos_por_faixa'])}",
        f"  Óbitos por local: {dist(est['obitos_por_local'])}",
        f"  Óbitos por meio: {dist(est['obitos_por_meio'])}",
        f"  Mulheres com residência ≠ ocorrência: {est['fem_residencia_diferente_ocorrencia']:.1%}",
    ])


if __name__ == "__main__":
    print("Lendo SIM em blocos...")
    agregado, detalhado, estatisticas = ler_e_tratar_sim(extract.ler_municipios())
    print(resumo(estatisticas))
    print("\nDetalhamento:", list(detalhado.columns))
    print(detalhado.head(3).to_string())
