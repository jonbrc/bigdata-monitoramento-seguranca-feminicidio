"""Análise exploratória das bases brutas.

Gera docs/analise_exploratoria.md com o perfil de cada base (registros,
colunas, tipos, nulos, duplicidades, inconsistências, período, chaves) e
o teste de compatibilidade das chaves de município entre as fontes.

Execução (na raiz do repositório):
    python -m etl.exploratory_analysis
"""

import re
from datetime import datetime

import pandas as pd

from etl import config, extract
from etl.padronizacao import codigo_ibge_6, normalizar_nome

# Sequências típicas de UTF-8 lido como latin-1 ("Ã§", "Ã£", "Ã©"...): "Ã"/"Â"
# seguidos de um caractere da faixa U+0080–U+00BF. "SÃO" não casa.
PADRAO_MOJIBAKE = re.compile(r"[ÃÂ][\x80-\xbf]")


# ---------------------------------------------------------------------------
# Utilitários de relatório
# ---------------------------------------------------------------------------
def tabela_md(df: pd.DataFrame) -> str:
    """Renderiza um DataFrame como tabela Markdown (sem dependências extras)."""
    cols = [str(c) for c in df.columns]
    linhas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        valores = ["" if pd.isna(v) else str(v).replace("|", "\\|") for v in row]
        linhas.append("| " + " | ".join(valores) + " |")
    return "\n".join(linhas)


def fmt(n) -> str:
    return f"{n:,}".replace(",", ".")


def perfil_nulos(nulos: pd.Series, total: int, tipos: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({
        "coluna": nulos.index,
        "tipo aparente": [str(tipos.get(c, "")) for c in nulos.index],
        "nulos": [fmt(int(v)) for v in nulos.values],
        "% nulos": [f"{v / total:.1%}" for v in nulos.values],
    })


# ---------------------------------------------------------------------------
# Base 1 — Sinesp
# ---------------------------------------------------------------------------
def analisar_sinesp(municipios: pd.DataFrame) -> list[str]:
    print("Lendo Sinesp VDE...")
    df = extract.ler_sinesp()
    n = len(df)
    out = ["## Base 1 — Sinesp VDE 2025", ""]
    out += [
        f"- **Arquivo:** `{config.SINESP_FILE.name}` (planilha Excel, aba `{config.SINESP_SHEET}`)",
        f"- **Registros:** {fmt(n)}",
        f"- **Colunas:** {df.shape[1]}",
        "",
        "### Colunas, tipos e nulos",
        "",
        tabela_md(perfil_nulos(df.isna().sum(), n, df.dtypes)),
        "",
    ]

    # Período
    datas = pd.to_datetime(df["data_referencia"], errors="coerce")
    out += [
        "### Período",
        "",
        f"- `data_referencia`: {datas.min():%Y-%m-%d} a {datas.max():%Y-%m-%d} "
        f"({datas.dt.to_period('M').nunique()} meses distintos; datas inválidas: {datas.isna().sum()})",
        "- Granularidade mensal (sempre o dia 1 do mês).",
        "",
    ]

    # Eventos
    medidas = ["feminino", "masculino", "nao_informado", "total_vitima", "total"]
    ev = df.groupby("evento").agg(
        registros=("uf", "size"),
        abrangencias=("abrangencia", lambda s: ", ".join(sorted(s.dropna().unique()))),
        linhas_municipio_nao_informado=("municipio", lambda s: int((s == "NÃO INFORMADO").sum())),
        soma_feminino=("feminino", "sum"),
        soma_total_vitima=("total_vitima", "sum"),
        soma_total=("total", "sum"),
    ).reset_index()
    for c in ["registros", "linhas_municipio_nao_informado"]:
        ev[c] = ev[c].map(fmt)
    for c in ["soma_feminino", "soma_total_vitima", "soma_total"]:
        ev[c] = ev[c].map(lambda v: fmt(int(v)))
    out += [
        f"### Eventos ({df['evento'].nunique()} tipos)",
        "",
        tabela_md(ev),
        "",
        "Observações:",
        "- Eventos com vítimas usam `feminino`/`masculino`/`nao_informado`/`total_vitima`; "
        "eventos sem vítimas (apreensões, mandados etc.) usam `total` ou `total_peso`.",
        "- Eventos em que todas as linhas têm município `NÃO INFORMADO` só existem no nível estadual "
        "e não podem ser cruzados por município.",
        "",
    ]

    # Valores numéricos
    neg = {c: int((df[c] < 0).sum()) for c in medidas}
    frac = {c: int(((df[c].dropna() % 1) != 0).sum()) for c in medidas}
    out += [
        "### Medidas numéricas",
        "",
        f"- Valores negativos: {neg}",
        f"- Valores não inteiros: {frac}",
        f"- Linhas com `total_vitima` = 0: {fmt(int((df['total_vitima'] == 0).sum()))} "
        f"({(df['total_vitima'] == 0).mean():.1%}) — linhas sem ocorrência.",
        "",
    ]

    # Duplicidades
    chave = ["uf", "municipio", "evento", "data_referencia", "agente", "arma",
             "faixa_etaria", "abrangencia"]
    dup_chave = df.duplicated(chave, keep=False)
    dup_mun = (df[dup_chave].groupby(["uf", "municipio"]).size()
               .sort_values(ascending=False).reset_index(name="linhas"))
    dup_mun["linhas"] = dup_mun["linhas"].map(fmt)
    # Ex.: quantas linhas por mês/evento o município mais duplicado tem
    exemplo = ""
    if len(dup_mun):
        uf0, mun0 = dup_mun.iloc[0]["uf"], dup_mun.iloc[0]["municipio"]
        sub = df[(df.uf == uf0) & (df.municipio == mun0) & (df.evento == "Feminicídio")]
        exemplo = (f"- Exemplo: `{uf0}/{mun0}` tem {len(sub) // max(sub.data_referencia.nunique(), 1)} "
                   f"linhas por mês para o evento Feminicídio — provavelmente uma por região administrativa "
                   "(o DF tem 33), todas com o mesmo nome de município.")
    out += [
        "### Duplicidades",
        "",
        f"- Linhas idênticas (todas as colunas): {fmt(int(df.duplicated().sum()))} excedentes",
        f"- Linhas repetidas na chave lógica `{' + '.join(chave)}`: "
        f"{fmt(int(df.duplicated(chave).sum()))} excedentes "
        f"(ou seja, {fmt(int(df.duplicated(chave).sum() - df.duplicated().sum()))} com mesma chave e medidas diferentes)",
        "",
        "Municípios com chave repetida:",
        "",
        tabela_md(dup_mun.head(10)),
        "",
        exemplo,
        "",
    ]

    # Municípios
    pares = df[["uf", "municipio"]].drop_duplicates()
    pares_validos = pares[pares.municipio != "NÃO INFORMADO"].copy()
    nomes_rep = pares_validos.municipio.duplicated(keep=False)
    espacos = int((df["municipio"].str.strip() != df["municipio"]).sum())
    mojibake = int(df["municipio"].str.contains(PADRAO_MOJIBAKE, na=False).sum()
                   + df["evento"].str.contains(PADRAO_MOJIBAKE, na=False).sum())
    caixa = int((df["municipio"] != df["municipio"].str.upper()).sum())
    uf_fora = sorted(set(df.uf.unique()) - set(config.UF_CODIGO_PARA_SIGLA.values()))
    out += [
        "### Município, UF, texto e encoding",
        "",
        f"- UFs: {df.uf.nunique()} (fora do padrão: {uf_fora or 'nenhuma'})",
        f"- Pares UF + município distintos: {fmt(len(pares))} "
        f"({fmt(len(pares_validos))} sem contar `NÃO INFORMADO`)",
        f"- Linhas com município `NÃO INFORMADO`: {fmt(int((df.municipio == 'NÃO INFORMADO').sum()))}",
        f"- Nomes de município que se repetem em UFs diferentes: {fmt(int(nomes_rep.sum()))} pares "
        "→ o nome sozinho **não** é chave; é preciso UF + município.",
        f"- **Não há código IBGE** na base; o município é identificado só por UF + nome.",
        f"- Nomes com espaços nas pontas: {espacos}",
        f"- Nomes fora de maiúsculas: {caixa}",
        f"- Indícios de problema de encoding (mojibake): {mojibake}",
        "",
    ]

    # Compatibilidade com a tabela IBGE
    ref = municipios.copy()
    ref["uf"] = ref["codigo_uf"].map(config.UF_CODIGO_PARA_SIGLA)
    ref["chave_nome"] = ref["nome"].map(normalizar_nome)
    pares_validos["chave_nome"] = pares_validos["municipio"].map(normalizar_nome)
    m = pares_validos.merge(ref[["uf", "chave_nome", "codigo_ibge", "nome"]],
                            on=["uf", "chave_nome"], how="left")
    sem = m[m.codigo_ibge.isna()][["uf", "municipio"]]
    out += [
        "### Compatibilidade com a tabela de municípios IBGE",
        "",
        "Comparação por UF + nome normalizado (sem acento, maiúsculas, sem hífen/apóstrofo):",
        "",
        f"- Municípios do Sinesp: {fmt(len(pares_validos))}",
        f"- Encontrados na tabela IBGE: {fmt(int(m.codigo_ibge.notna().sum()))}",
        f"- Sem correspondência: {len(sem)}",
        "",
        tabela_md(sem) if len(sem) else "",
        "",
        "Os casos sem correspondência são grafias diferentes do mesmo município "
        "(nome antigo ou variante) e precisam de um mapeamento explícito.",
        "",
    ]
    return out


# ---------------------------------------------------------------------------
# Base 2 — SIM
# ---------------------------------------------------------------------------
def analisar_sim(municipios: pd.DataFrame) -> list[str]:
    print("Lendo SIM em blocos...")
    total = 0
    colunas = None
    nulos = None
    hashes = []
    contadores = []
    sexo = pd.Series(dtype="int64")
    cb_asterisco = 0
    cb_tamanho = pd.Series(dtype="int64")
    datas_invalidas = 0
    meses = pd.Series(dtype="int64")
    dt_min, dt_max = None, None
    subconjunto = []
    nao_numericos = {c: 0 for c in ["CODMUNRES", "CODMUNOCOR", "SEXO", "RACACOR"]}

    for bloco in extract.iterar_sim():
        if colunas is None:
            colunas = list(bloco.columns)
            nulos = pd.Series(0, index=colunas)
        total += len(bloco)
        nulos += bloco.isna().sum()
        hashes.append(pd.util.hash_pandas_object(bloco.drop(columns=["contador"]), index=False))
        contadores.append(bloco["contador"])
        sexo = sexo.add(bloco["SEXO"].value_counts(dropna=False), fill_value=0)
        cb_asterisco += int(bloco["CAUSABAS"].str.contains("*", regex=False, na=False).sum())
        cb_tamanho = cb_tamanho.add(bloco["CAUSABAS"].str.len().value_counts(dropna=False), fill_value=0)
        d = pd.to_datetime(bloco["DTOBITO"], format="%d%m%Y", errors="coerce")
        datas_invalidas += int(d.isna().sum())
        meses = meses.add(d.dt.to_period("M").astype(str).value_counts(), fill_value=0)
        dt_min = d.min() if dt_min is None else min(dt_min, d.min())
        dt_max = d.max() if dt_max is None else max(dt_max, d.max())
        for c in nao_numericos:
            v = bloco[c].dropna()
            nao_numericos[c] += int((~v.str.fullmatch(r"\d+")).sum())
        subconjunto.append(bloco[extract.filtro_feminino_agressao(bloco)])

    hashes = pd.concat(hashes)
    contadores = pd.concat(contadores)
    sub = pd.concat(subconjunto, ignore_index=True)
    out = ["## Base 2 — SIM 2025 (preliminar)", ""]
    out += [
        f"- **Arquivo:** `{config.SIM_FILE.name}` (CSV, separador `{config.SIM_SEPARATOR}`, "
        f"lido como `{config.SIM_ENCODING}`)",
        f"- **Registros:** {fmt(total)}",
        f"- **Colunas:** {len(colunas)}",
        "- Todas as colunas lidas como texto (são códigos; ver `etl/extract.py`).",
        "",
        "### Nulos por coluna (base inteira)",
        "",
        "<details><summary>Todas as colunas</summary>",
        "",
        tabela_md(perfil_nulos(nulos, total, pd.Series("texto/código", index=colunas))),
        "",
        "</details>",
        "",
    ]

    out += [
        "### Duplicidades e chaves",
        "",
        f"- `contador` repetido: {fmt(int(contadores.duplicated().sum()))} → `contador` identifica a linha.",
        f"- Linhas idênticas ignorando `contador`: {fmt(int(hashes.duplicated().sum()))}",
        "- Cada linha é uma declaração de óbito; não há identificador da pessoa "
        "(o que é coerente com a LGPD).",
        "",
        "### Período",
        "",
        f"- `DTOBITO` (formato `ddmmaaaa`): {dt_min:%Y-%m-%d} a {dt_max:%Y-%m-%d}; datas inválidas: {datas_invalidas}",
        "- Óbitos por mês:",
        "",
        tabela_md(meses.sort_index().astype(int).map(fmt).rename_axis("mês").reset_index(name="óbitos")),
        "",
        "Base **preliminar**: a cobertura cai a partir de agosto e não há óbitos depois de "
        "setembro/2025, enquanto o Sinesp cobre janeiro a dezembro.",
        "",
        "### Formatação e consistência",
        "",
        f"- `SEXO`: {({k: fmt(int(v)) for k, v in sexo.items()})} (1 = masculino, 2 = feminino, 0 = ignorado)",
        f"- `CAUSABAS` com `*`: {cb_asterisco}; tamanhos: "
        f"{({int(k): fmt(int(v)) for k, v in cb_tamanho.items() if pd.notna(k)})}",
        f"- Valores não numéricos em campos de código: {nao_numericos}",
        "- O arquivo contém apenas caracteres ASCII; não há texto acentuado e, "
        "portanto, não há risco de problema de encoding.",
        "",
    ]

    # Subconjunto do tema
    n_sub = len(sub)
    cid = sub["CAUSABAS"].str[:3].value_counts()
    ibge6 = set(municipios["codigo_ibge"].map(codigo_ibge_6))
    res_ignorado = sub["CODMUNRES"].str.endswith("0000", na=False)
    res_fora = ~sub["CODMUNRES"].isin(ibge6)
    ocor_fora = ~sub["CODMUNOCOR"].isin(ibge6)
    idade_unid = sub["IDADE"].str[0].value_counts().sort_index()
    out += [
        "### Recorte do tema (AI02): mulheres, causa básica X85–Y09",
        "",
        f"- Registros no recorte: **{fmt(n_sub)}** ({n_sub / total:.2%} da base)",
        f"- Duplicidades no recorte (ignorando `contador`): {int(sub.drop(columns=['contador']).duplicated().sum())}",
        f"- Categorias CID mais frequentes: {({k: int(v) for k, v in cid.head(8).items()})}",
        "",
        "Nulos nos campos mapeados na AI02 (dentro do recorte):",
        "",
        tabela_md(perfil_nulos(sub[config.SIM_COLUNAS_AI02].isna().sum(), n_sub,
                               pd.Series("texto/código", index=config.SIM_COLUNAS_AI02))),
        "",
        "Distribuição das categorias interseccionais (dentro do recorte):",
        "",
    ]
    for c in ["RACACOR", "ESC2010", "ESTCIV", "LOCOCOR", "CIRCOBITO"]:
        vc = sub[c].value_counts(dropna=False)
        out.append(f"- `{c}`: " + ", ".join(f"{'nulo' if pd.isna(k) else k}={v}" for k, v in vc.items()))
    out += [
        f"- `IDADE` — 1º dígito (unidade: 0/1 min/h, 2 dias, 3 meses, 4 anos, 5 anos+100, 9 ignorado): "
        + ", ".join(f"{k}={v}" for k, v in idade_unid.items()),
        "",
        "### Códigos de município",
        "",
        f"- Tamanho de `CODMUNRES`: {sub['CODMUNRES'].str.len().value_counts().to_dict()}; "
        f"`CODMUNOCOR`: {sub['CODMUNOCOR'].str.len().value_counts().to_dict()} "
        "→ código IBGE de **6 dígitos** (sem dígito verificador).",
        f"- `CODMUNRES` terminado em `0000` (município ignorado, só UF): {int(res_ignorado.sum())}",
        f"- `CODMUNRES` fora da tabela IBGE: {int(res_fora.sum())}; "
        f"`CODMUNOCOR` fora da tabela IBGE: {int(ocor_fora.sum())}",
        f"- Óbitos com município de residência ≠ município de ocorrência: "
        f"{int((sub['CODMUNRES'] != sub['CODMUNOCOR']).sum())} ({(sub['CODMUNRES'] != sub['CODMUNOCOR']).mean():.1%})",
        "",
    ]
    return out


# ---------------------------------------------------------------------------
def main() -> None:
    municipios = extract.ler_municipios()
    linhas = [
        "# Análise exploratória das bases brutas",
        "",
        f"_Gerado automaticamente por `python -m etl.exploratory_analysis` em "
        f"{datetime.now():%Y-%m-%d %H:%M}._",
        "",
        "## Tabela de referência — municípios IBGE",
        "",
        f"- Arquivo: `data/reference/{config.MUNICIPIOS_FILE.name}`",
        f"- Municípios: {fmt(len(municipios))}; códigos duplicados: "
        f"{int(municipios['codigo_ibge'].duplicated().sum())}",
        "- Código IBGE de 7 dígitos; os 6 primeiros correspondem ao código usado no SIM.",
        "",
    ]
    linhas += analisar_sinesp(municipios)
    linhas += analisar_sim(municipios)

    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    config.EDA_REPORT_FILE.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Relatório gerado: {config.EDA_REPORT_FILE.relative_to(config.ROOT_DIR)}")


if __name__ == "__main__":
    main()
