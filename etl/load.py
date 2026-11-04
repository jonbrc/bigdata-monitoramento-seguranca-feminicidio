"""CARGA — monta o modelo estrela de sql/schema.sql a partir dos CSVs tratados e o carrega no PostgreSQL (Aiven) em uma única transação; `--dry-run` só monta e confere."""

import argparse
import io
import os
import sys
import time

import pandas as pd

from etl import config, extract

COLUNAS = {
    "dim_municipio": ["codigo_ibge", "codigo_ibge_6", "nome", "sigla_uf", "capital",
                      "latitude", "longitude"],
    "dim_tempo": ["id_tempo", "ano", "mes", "nome_mes", "trimestre", "semestre",
                  "data_inicio", "sim_periodo_coberto"],
    "fato_ocorrencia_sinesp": ["codigo_ibge", "id_tempo", "id_evento", "vitimas_fem", "vitimas_total"],
    "fato_obito_sim": ["codigo_ibge", "id_tempo", "id_sexo", "id_raca_cor", "id_faixa_etaria",
                       "id_local_obito", "id_meio_agressao", "obitos"],
    "fato_populacao": ["codigo_ibge", "id_sexo", "id_raca_cor", "id_faixa_etaria", "ano_censo", "populacao"],
}

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]
ANO_CENSO = 2022

IDS_SEXO = {"masculino": 1, "feminino": 2}
IDS_LOCAL = {"domicilio": 1, "via_publica": 2, "estabelecimento_saude": 3,
             "aldeia_indigena": 4, "outros": 5, "local_ignorado": 9}
IDS_MEIO = {"arma_fogo": 1, "objeto_cortante": 2, "objeto_contundente": 3, "forca_corporal": 4,
            "enforcamento_sufocacao": 5, "envenenamento": 6, "maus_tratos": 7, "outros": 8,
            "meio_nao_especificado": 9}


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def ids_evento() -> dict[str, int]:
    return {codigo: i for i, codigo in enumerate(config.SINESP_EVENTOS.values(), start=1)}


def ids_raca() -> dict[str, int]:
    ids = {nome: int(codigo) for codigo, nome in config.SIM_RACACOR.items()}
    ids[config.SIM_RACACOR_IGNORADA] = 9
    return ids


def ids_faixa() -> dict[str, int]:
    ids = {nome: i for i, (_, _, nome) in enumerate(config.SIM_FAIXAS_ETARIAS, start=1)}
    ids[config.SIM_FAIXA_IGNORADA] = 9
    return ids


def ids_dimensoes() -> dict[str, dict[str, int]]:
    return {
        "dim_evento": ids_evento(),
        "dim_sexo": IDS_SEXO,
        "dim_raca_cor": ids_raca(),
        "dim_faixa_etaria": ids_faixa(),
        "dim_local_obito": IDS_LOCAL,
        "dim_meio_agressao": IDS_MEIO,
    }


def ler_csv(caminho) -> pd.DataFrame:
    if not caminho.exists():
        sys.exit(f"Arquivo não encontrado: {caminho.relative_to(config.ROOT_DIR).as_posix()}\n"
                 "Gere-o antes com: python -m etl.main")
    df = pd.read_csv(caminho, sep=config.OUTPUT_SEPARATOR,
                     encoding=config.OUTPUT_ENCODING, dtype={"codigo_ibge": str})
    df["id_tempo"] = df["ano"] * 100 + df["mes"]
    return df


def montar_tabelas(painel: pd.DataFrame, sim: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tabelas: dict[str, pd.DataFrame] = {}

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

    t = pd.DataFrame([(a, m) for a in config.ANOS for m in range(1, 13)], columns=["ano", "mes"])
    t["id_tempo"] = t["ano"] * 100 + t["mes"]
    t["nome_mes"] = t["mes"].map(lambda m: MESES[m - 1])
    t["trimestre"] = (t["mes"] - 1) // 3 + 1
    t["semestre"] = (t["mes"] - 1) // 6 + 1
    t["data_inicio"] = pd.to_datetime(dict(year=t["ano"], month=t["mes"], day=1)).dt.date
    t["sim_periodo_coberto"] = [m in config.SIM_MESES_COBERTOS.get(a, []) for a, m in zip(t["ano"], t["mes"])]
    tabelas["dim_tempo"] = t

    partes = []
    for codigo, id_evento in ids_evento().items():
        p = painel[["codigo_ibge", "id_tempo"]].copy()
        p["id_evento"] = id_evento
        p["vitimas_fem"] = painel[f"sinesp_{codigo}_fem"].fillna(0).astype("int64")
        p["vitimas_total"] = painel[f"sinesp_{codigo}_total"].fillna(0).astype("int64")
        partes.append(p[p["vitimas_total"] > 0])
    tabelas["fato_ocorrencia_sinesp"] = pd.concat(partes, ignore_index=True)

    tabelas["fato_obito_sim"] = sim.assign(
        id_sexo=sim["sexo"].map(IDS_SEXO),
        id_raca_cor=sim["raca_cor"].map(ids_raca()),
        id_faixa_etaria=sim["faixa_etaria"].map(ids_faixa()),
        id_local_obito=sim["local_obito"].map(IDS_LOCAL),
        id_meio_agressao=sim["meio_agressao"].map(IDS_MEIO),
    )

    pop = extract.ler_populacao_detalhada()
    cores = list(config.SIM_RACACOR.values())
    pop[f"pop_{config.SIM_RACACOR_IGNORADA}"] = pop["pop_total"] - pop[[f"pop_{c}" for c in cores]].sum(axis=1)
    longo = pop.melt(id_vars=["codigo_ibge", "sexo", "faixa_etaria"],
                     value_vars=[f"pop_{r}" for r in ids_raca()],
                     var_name="coluna", value_name="populacao")
    if (longo["populacao"] < 0).any():
        raise ValueError("População negativa: soma das cores maior que o total em algum município")
    longo = longo[longo["populacao"] > 0].copy()
    longo["id_sexo"] = longo["sexo"].map(IDS_SEXO)
    longo["id_raca_cor"] = longo["coluna"].str.removeprefix("pop_").map(ids_raca())
    longo["id_faixa_etaria"] = longo["faixa_etaria"].map(ids_faixa())
    longo["ano_censo"] = ANO_CENSO
    tabelas["fato_populacao"] = longo

    return {nome: tabela[COLUNAS[nome]] for nome, tabela in tabelas.items()}


def conferir(painel: pd.DataFrame, sim: pd.DataFrame, tabelas: dict[str, pd.DataFrame]) -> list[tuple[str, bool]]:
    s, o, pop = tabelas["fato_ocorrencia_sinesp"], tabelas["fato_obito_sim"], tabelas["fato_populacao"]
    municipios = set(tabelas["dim_municipio"]["codigo_ibge"])
    tempos = set(tabelas["dim_tempo"]["id_tempo"])
    cols_total = [c for c in painel.columns if c.startswith("sinesp_") and c.endswith("_total")]
    cols_fem = [c for c in painel.columns if c.startswith("sinesp_") and c.endswith("_fem")]
    pop_bruta = extract.ler_populacao_detalhada()
    chave_sim = [c for c in COLUNAS["fato_obito_sim"] if c != "obitos"]
    chave_pop = [c for c in COLUNAS["fato_populacao"] if c != "populacao"]
    return [
        ("Sem ids nulos após o mapeamento das dimensões",
         not any(t.drop(columns=["latitude", "longitude"], errors="ignore").isna().any().any()
                 for t in tabelas.values())),
        ("Todos os municípios dos fatos existem em dim_municipio",
         set(s["codigo_ibge"]) | set(o["codigo_ibge"]) | set(pop["codigo_ibge"]) <= municipios),
        ("Todos os meses dos fatos existem em dim_tempo",
         set(s["id_tempo"]) | set(o["id_tempo"]) <= tempos),
        ("Vítimas do Sinesp (total e femininas) iguais ao CSV",
         int(s["vitimas_total"].sum()) == int(painel[cols_total].sum().sum())
         and int(s["vitimas_fem"].sum()) == int(painel[cols_fem].sum().sum())),
        ("Óbitos do SIM iguais ao CSV detalhado", int(o["obitos"].sum()) == int(sim["obitos"].sum())),
        ("Óbitos femininos do SIM iguais ao painel",
         int(o.loc[o["id_sexo"] == IDS_SEXO["feminino"], "obitos"].sum())
         == int(painel["sim_obitos_fem_agressao"].fillna(0).sum())),
        ("População igual ao total do Censo 2022, por sexo",
         pop.groupby("id_sexo")["populacao"].sum().to_dict()
         == {IDS_SEXO[k]: int(v) for k, v in pop_bruta.groupby("sexo")["pop_total"].sum().items()}),
        ("Chaves primárias únicas nos fatos",
         not s.duplicated(["codigo_ibge", "id_tempo", "id_evento"]).any()
         and not o.duplicated(chave_sim).any()
         and not pop.duplicated(chave_pop).any()),
    ]


def conectar():
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
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    colunas = ", ".join(df.columns)
    with cur.copy(f"COPY {config.DB_SCHEMA}.{tabela} ({colunas}) FROM STDIN WITH (FORMAT csv)") as cp:
        cp.write(buffer.getvalue())


def conferir_dimensoes(cur) -> None:
    for tabela, esperado in ids_dimensoes().items():
        id_col = "id_" + tabela.removeprefix("dim_")
        cur.execute(f"SELECT codigo, {id_col} FROM {config.DB_SCHEMA}.{tabela}")
        no_banco = dict(cur.fetchall())
        if no_banco != esperado:
            raise RuntimeError(f"{tabela}: ids do schema.sql diferentes dos do load.py; carga desfeita")


def carregar(tabelas: dict[str, pd.DataFrame]) -> None:
    sql = config.SCHEMA_SQL_FILE.read_text(encoding="utf-8")
    esquema = config.DB_SCHEMA
    with conectar() as conn:
        with conn.cursor() as cur:
            print(f"  Recriando o schema '{esquema}' a partir de "
                  f"{config.SCHEMA_SQL_FILE.relative_to(config.ROOT_DIR).as_posix()}...")
            cur.execute(sql)
            conferir_dimensoes(cur)
            for nome, df in tabelas.items():
                copiar(cur, nome, df)
                print(f"  {nome:<24} {fmt(len(df)):>8} linhas")

            cur.execute(f"""
                SELECT (SELECT COALESCE(SUM(vitimas_total), 0) FROM {esquema}.fato_ocorrencia_sinesp),
                       (SELECT COALESCE(SUM(obitos), 0)        FROM {esquema}.fato_obito_sim),
                       (SELECT COALESCE(SUM(populacao), 0)     FROM {esquema}.fato_populacao)""")
            no_banco = tuple(int(v) for v in cur.fetchone())
            esperado = (int(tabelas["fato_ocorrencia_sinesp"]["vitimas_total"].sum()),
                        int(tabelas["fato_obito_sim"]["obitos"].sum()),
                        int(tabelas["fato_populacao"]["populacao"].sum()))
            if no_banco != esperado:
                raise RuntimeError(f"Totais no banco {no_banco} ≠ esperados {esperado}; carga desfeita")

            cur.execute("""SELECT pg_size_pretty(SUM(pg_total_relation_size(c.oid)))
                           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                           WHERE n.nspname = %s""", (esquema,))
            tamanho = cur.fetchone()[0]
    print(f"\n  No banco: {fmt(no_banco[0])} vítimas (Sinesp) · {fmt(no_banco[1])} óbitos (SIM) · "
          f"{fmt(no_banco[2])} pessoas (Censo 2022) · tamanho do schema: {tamanho}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga dos CSVs tratados no PostgreSQL (Aiven).")
    parser.add_argument("--dry-run", action="store_true",
                        help="só monta e confere as tabelas, sem conectar ao banco")
    args = parser.parse_args()

    inicio = time.time()
    print("=" * 64)
    print("CARGA — PostgreSQL (Aiven), modelo estrela")
    print("=" * 64)

    print("\n[1/3] Montando dimensões e fatos...")
    painel = ler_csv(config.OUTPUT_FILE)
    sim = ler_csv(config.OUTPUT_SIM_FILE)
    tabelas = montar_tabelas(painel, sim)
    for nome, tabela in tabelas.items():
        print(f"  {nome:<24} {fmt(len(tabela)):>8} linhas")

    print("\n[2/3] Conferindo...")
    checks = conferir(painel, sim, tabelas)
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
