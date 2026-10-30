"""CARGA — CSV tratado → PostgreSQL (Aiven), no modelo estrela de sql/schema.sql.

Entrada:
    data/processed/violencia_feminicidio_municipio_mes_2025.csv  (gerado por `python -m etl.main`)
    data/reference/municipios_ibge.csv                           (dim_municipio)
    data/reference/populacao_feminina_censo2022.csv              (fato_populacao)

O CSV tem formato largo (uma linha por município × mês, uma coluna por evento,
raça/cor e faixa etária). Na carga, essas colunas viram linhas nas tabelas fato
(formato longo), e só são gravadas as combinações com pelo menos um caso.

Credenciais: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD (e, opcionalmente,
DB_SSLMODE), lidas do arquivo .env na raiz — modelo em .env.example.

Execução (na raiz do repositório):
    python -m etl.load             # recria o schema "dw" e carrega tudo
    python -m etl.load --dry-run   # só monta e confere as tabelas, sem conectar ao banco

A carga pode ser repetida: o schema é recriado a cada execução, dentro de uma
única transação (se algo falhar, nada é gravado).
"""

import argparse
import io
import os
import sys
import time

import pandas as pd

from etl import config, extract

# Tabelas carregadas pelo script, na ordem de carga (dimensões antes dos fatos).
# dim_uf, dim_evento, dim_raca_cor e dim_faixa_etaria são fixas e vêm do schema.sql.
COLUNAS = {
    "dim_municipio": ["codigo_ibge", "codigo_ibge_6", "nome", "sigla_uf", "capital",
                      "latitude", "longitude"],
    "dim_tempo": ["id_tempo", "ano", "mes", "nome_mes", "trimestre", "semestre",
                  "data_inicio", "sim_periodo_coberto"],
    "fato_ocorrencia_sinesp": ["codigo_ibge", "id_tempo", "id_evento", "vitimas_fem", "vitimas_total"],
    "fato_obito_sim_raca": ["codigo_ibge", "id_tempo", "id_raca_cor", "obitos"],
    "fato_obito_sim_faixa": ["codigo_ibge", "id_tempo", "id_faixa_etaria", "obitos"],
    "fato_populacao": ["codigo_ibge", "id_raca_cor", "ano_censo", "pop_fem"],
}

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]
ANO_CENSO = 2022


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# ---------------------------------------------------------------------------
# Ids das dimensões fixas (os mesmos inseridos por sql/schema.sql)
# ---------------------------------------------------------------------------
def ids_evento() -> dict[str, int]:
    """Na ordem de config.SINESP_EVENTOS: feminicidio = 1, ..., latrocinio = 6."""
    return {codigo: i for i, codigo in enumerate(config.SINESP_EVENTOS.values(), start=1)}


def ids_raca() -> dict[str, int]:
    """Código do SIM/IBGE (1–5) como id; raça/cor ignorada = 9."""
    ids = {nome: int(codigo) for codigo, nome in config.SIM_RACACOR.items()}
    ids[config.SIM_RACACOR_IGNORADA] = 9
    return ids


def ids_faixa() -> dict[str, int]:
    """Na ordem de config.SIM_FAIXAS_ETARIAS: idade_0_17 = 1, ..., idade_60_mais = 6; ignorada = 9."""
    ids = {nome: i for i, (_, _, nome) in enumerate(config.SIM_FAIXAS_ETARIAS, start=1)}
    ids[config.SIM_FAIXA_IGNORADA] = 9
    return ids


# ---------------------------------------------------------------------------
# Montagem das tabelas
# ---------------------------------------------------------------------------
def ler_csv_tratado() -> pd.DataFrame:
    if not config.OUTPUT_FILE.exists():
        sys.exit(f"Arquivo não encontrado: {config.OUTPUT_FILE.relative_to(config.ROOT_DIR).as_posix()}\n"
                 "Gere-o antes com: python -m etl.main")
    df = pd.read_csv(config.OUTPUT_FILE, sep=config.OUTPUT_SEPARATOR,
                     encoding=config.OUTPUT_ENCODING, dtype={"codigo_ibge": str})
    df["id_tempo"] = df["ano"] * 100 + df["mes"]
    return df


def colunas_para_linhas(df: pd.DataFrame, colunas: dict[str, int], coluna_id: str) -> pd.DataFrame:
    """Formato largo → longo: cada coluna de contagem vira uma linha com o id da dimensão.
    Valores vazios (meses sem cobertura do SIM) e zeros não são gravados."""
    longo = df.melt(id_vars=["codigo_ibge", "id_tempo"], value_vars=list(colunas),
                    var_name="coluna", value_name="obitos").dropna(subset=["obitos"])
    longo = longo[longo["obitos"] > 0].copy()
    longo[coluna_id] = longo["coluna"].map(colunas)
    longo["obitos"] = longo["obitos"].astype("int64")
    return longo


def montar_tabelas(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tabelas: dict[str, pd.DataFrame] = {}

    # dim_municipio — todos os municípios da tabela de referência
    mun = extract.ler_municipios()
    tabelas["dim_municipio"] = pd.DataFrame({
        "codigo_ibge": mun["codigo_ibge"],
        "codigo_ibge_6": mun["codigo_ibge"].str[:6],
        "nome": mun["nome"],
        "sigla_uf": mun["codigo_uf"].map(config.UF_CODIGO_PARA_SIGLA),
        "capital": mun["capital"].astype(bool),
        "latitude": mun["latitude"].round(5),
        "longitude": mun["longitude"].round(5),
    })

    # dim_tempo — os 12 meses do ano de referência
    t = pd.DataFrame({"ano": config.SIM_ANO, "mes": range(1, 13)})
    t["id_tempo"] = t["ano"] * 100 + t["mes"]
    t["nome_mes"] = t["mes"].map(lambda m: MESES[m - 1])
    t["trimestre"] = (t["mes"] - 1) // 3 + 1
    t["semestre"] = (t["mes"] - 1) // 6 + 1
    t["data_inicio"] = pd.to_datetime(dict(year=t["ano"], month=t["mes"], day=1)).dt.date
    t["sim_periodo_coberto"] = t["mes"].isin(config.SIM_MESES_COBERTOS)
    tabelas["dim_tempo"] = t

    # fato_ocorrencia_sinesp — sinesp_<evento>_fem / _total → uma linha por evento
    partes = []
    for codigo, id_evento in ids_evento().items():
        p = df[["codigo_ibge", "id_tempo"]].copy()
        p["id_evento"] = id_evento
        p["vitimas_fem"] = df[f"sinesp_{codigo}_fem"].fillna(0).astype("int64")
        p["vitimas_total"] = df[f"sinesp_{codigo}_total"].fillna(0).astype("int64")
        partes.append(p[p["vitimas_total"] > 0])
    tabelas["fato_ocorrencia_sinesp"] = pd.concat(partes, ignore_index=True)

    # fato_obito_sim_raca — sim_obitos_fem_<raça> → uma linha por raça/cor
    tabelas["fato_obito_sim_raca"] = colunas_para_linhas(
        df, {f"sim_obitos_fem_{r}": i for r, i in ids_raca().items()}, "id_raca_cor")

    # fato_obito_sim_faixa — sim_obitos_fem_<faixa> → uma linha por faixa etária
    tabelas["fato_obito_sim_faixa"] = colunas_para_linhas(
        df, {f"sim_obitos_fem_{f}": i for f, i in ids_faixa().items()}, "id_faixa_etaria")

    # fato_populacao — arquivo de referência completo (todos os municípios, inclusive os
    # sem ocorrência). Raça ignorada = total − soma das cinco categorias.
    pop = extract.ler_populacao()
    cores = list(config.SIM_RACACOR.values())
    pop[f"pop_fem_{config.SIM_RACACOR_IGNORADA}"] = (
        pop["pop_fem_total"] - pop[[f"pop_fem_{c}" for c in cores]].sum(axis=1))
    longo = pop.melt(id_vars="codigo_ibge",
                     value_vars=[f"pop_fem_{r}" for r in ids_raca()],
                     var_name="coluna", value_name="pop_fem")
    longo["id_raca_cor"] = longo["coluna"].str.removeprefix("pop_fem_").map(ids_raca())
    longo["ano_censo"] = ANO_CENSO
    tabelas["fato_populacao"] = longo

    return {nome: tabela[COLUNAS[nome]] for nome, tabela in tabelas.items()}


def conferir(df: pd.DataFrame, tabelas: dict[str, pd.DataFrame]) -> list[tuple[str, bool]]:
    """Conferências antes da carga: nada se perdeu na conversão para o modelo estrela."""
    s = tabelas["fato_ocorrencia_sinesp"]
    raca, faixa = tabelas["fato_obito_sim_raca"], tabelas["fato_obito_sim_faixa"]
    pop = tabelas["fato_populacao"]
    municipios = set(tabelas["dim_municipio"]["codigo_ibge"])
    cols_total = [c for c in df.columns if c.startswith("sinesp_") and c.endswith("_total")]
    cols_fem = [c for c in df.columns if c.startswith("sinesp_") and c.endswith("_fem")]
    obitos_csv = int(df["sim_obitos_fem_agressao"].fillna(0).sum())
    return [
        ("Sem ids nulos após o mapeamento das dimensões",
         not any(t.drop(columns=["latitude", "longitude"], errors="ignore").isna().any().any()
                 for t in tabelas.values())),
        ("Todos os municípios dos fatos existem em dim_municipio",
         set(s["codigo_ibge"]) | set(raca["codigo_ibge"]) | set(faixa["codigo_ibge"])
         | set(pop["codigo_ibge"]) <= municipios),
        ("Todos os meses dos fatos existem em dim_tempo",
         set(s["id_tempo"]) | set(raca["id_tempo"]) <= set(tabelas["dim_tempo"]["id_tempo"])),
        ("Vítimas do Sinesp (total e femininas) iguais ao CSV",
         int(s["vitimas_total"].sum()) == int(df[cols_total].sum().sum())
         and int(s["vitimas_fem"].sum()) == int(df[cols_fem].sum().sum())),
        ("Óbitos do SIM por raça/cor = total do CSV", int(raca["obitos"].sum()) == obitos_csv),
        ("Óbitos do SIM por faixa etária = total do CSV", int(faixa["obitos"].sum()) == obitos_csv),
        ("População por raça/cor = total do Censo 2022",
         int(pop["pop_fem"].sum()) == int(extract.ler_populacao()["pop_fem_total"].sum())),
        ("Sem população negativa (raça ignorada = total − soma das cores)",
         bool((pop["pop_fem"] >= 0).all())),
        ("Chaves primárias únicas nos fatos",
         not s.duplicated(["codigo_ibge", "id_tempo", "id_evento"]).any()
         and not raca.duplicated(["codigo_ibge", "id_tempo", "id_raca_cor"]).any()
         and not faixa.duplicated(["codigo_ibge", "id_tempo", "id_faixa_etaria"]).any()
         and not pop.duplicated(["codigo_ibge", "id_raca_cor", "ano_censo"]).any()),
    ]


# ---------------------------------------------------------------------------
# Conexão e carga
# ---------------------------------------------------------------------------
def conectar():
    """Abre a conexão com as credenciais do .env. Nenhuma credencial fica no código."""
    import psycopg
    from dotenv import load_dotenv

    load_dotenv(config.ENV_FILE)
    faltando = [v for v in config.DB_ENV_OBRIGATORIAS if not os.getenv(v)]
    if faltando:
        sys.exit(f"Variáveis ausentes no .env: {', '.join(faltando)}.\n"
                 "Copie .env.example para .env e preencha com os dados do serviço no Aiven.")
    return psycopg.connect(
        host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        sslmode=os.getenv("DB_SSLMODE") or config.DB_SSLMODE_PADRAO, connect_timeout=30,
    )


def copiar(cur, tabela: str, df: pd.DataFrame) -> None:
    """COPY a partir da memória (bem mais rápido que INSERT linha a linha)."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    colunas = ", ".join(df.columns)
    with cur.copy(f"COPY {config.DB_SCHEMA}.{tabela} ({colunas}) FROM STDIN WITH (FORMAT csv)") as cp:
        cp.write(buffer.getvalue())


def carregar(tabelas: dict[str, pd.DataFrame]) -> None:
    sql = config.SCHEMA_SQL_FILE.read_text(encoding="utf-8")
    with conectar() as conn:  # uma transação: commit no fim, rollback se der erro
        with conn.cursor() as cur:
            print(f"  Recriando o schema '{config.DB_SCHEMA}' a partir de "
                  f"{config.SCHEMA_SQL_FILE.relative_to(config.ROOT_DIR).as_posix()}...")
            cur.execute(sql)
            for nome, df in tabelas.items():
                copiar(cur, nome, df)
                print(f"  {nome:<24} {fmt(len(df)):>8} linhas")

            # Conferência no banco: totais iguais aos montados em memória
            esquema = config.DB_SCHEMA
            cur.execute(f"""
                SELECT (SELECT COALESCE(SUM(vitimas_total), 0) FROM {esquema}.fato_ocorrencia_sinesp),
                       (SELECT COALESCE(SUM(obitos), 0)        FROM {esquema}.fato_obito_sim_raca),
                       (SELECT COALESCE(SUM(obitos), 0)        FROM {esquema}.fato_obito_sim_faixa),
                       (SELECT COALESCE(SUM(pop_fem), 0)       FROM {esquema}.fato_populacao)""")
            no_banco = tuple(int(v) for v in cur.fetchone())
            esperado = (int(tabelas["fato_ocorrencia_sinesp"]["vitimas_total"].sum()),
                        int(tabelas["fato_obito_sim_raca"]["obitos"].sum()),
                        int(tabelas["fato_obito_sim_faixa"]["obitos"].sum()),
                        int(tabelas["fato_populacao"]["pop_fem"].sum()))
            if no_banco != esperado:
                raise RuntimeError(f"Totais no banco {no_banco} ≠ esperados {esperado}; carga desfeita")

            cur.execute("""SELECT pg_size_pretty(SUM(pg_total_relation_size(c.oid)))
                           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                           WHERE n.nspname = %s""", (esquema,))
            tamanho = cur.fetchone()[0]
    print(f"\n  No banco: {fmt(no_banco[0])} vítimas (Sinesp) · {fmt(no_banco[1])} óbitos (SIM) · "
          f"{fmt(no_banco[3])} mulheres (Censo 2022) · tamanho do schema: {tamanho}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga do CSV tratado no PostgreSQL (Aiven).")
    parser.add_argument("--dry-run", action="store_true",
                        help="só monta e confere as tabelas, sem conectar ao banco")
    args = parser.parse_args()

    inicio = time.time()
    print("=" * 64)
    print("CARGA — PostgreSQL (Aiven), modelo estrela")
    print("=" * 64)

    print("\n[1/3] Montando dimensões e fatos...")
    df = ler_csv_tratado()
    tabelas = montar_tabelas(df)
    for nome, tabela in tabelas.items():
        print(f"  {nome:<24} {fmt(len(tabela)):>8} linhas")

    print("\n[2/3] Conferindo...")
    checks = conferir(df, tabelas)
    for descricao, ok in checks:
        print(f"  [{'OK' if ok else 'FALHOU'}] {descricao}")
    if not all(ok for _, ok in checks):
        print("\nConferência falhou: nada foi carregado.")
        return 1

    if args.dry_run:
        print("\n[3/3] --dry-run: carga não executada.")
        return 0

    print("\n[3/3] Carregando no PostgreSQL...")
    carregar(tabelas)
    print(f"\nCarga concluída em {time.time() - inicio:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
