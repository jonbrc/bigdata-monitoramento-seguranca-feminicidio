"""Baixa da API de agregados do IBGE (Censo 2022, tabela 9606) a população por município, sexo, faixa etária e cor/raça e grava data/reference/populacao_censo2022.csv."""

import csv
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from etl import config


def baixar(uf: int, idades: list[str]) -> list[dict]:
    url = config.POPULACAO_API_URL.format(
        uf=uf,
        sexos=",".join(config.POPULACAO_API_SEXOS),
        idades=",".join(idades),
    )
    for tentativa in range(5):
        try:
            with urllib.request.urlopen(url, timeout=180) as resp:
                return json.load(resp)[0]["resultados"]
        except Exception:
            if tentativa == 4:
                raise
            time.sleep(3 * (tentativa + 1))
    return []


def acumular(resultados: list[dict], acc: dict) -> None:
    for res in resultados:
        cat = {c["id"]: next(iter(c["categoria"])) for c in res["classificacoes"]}
        sexo = config.POPULACAO_API_SEXOS[cat["2"]]
        cor = config.POPULACAO_API_CORES[cat["86"]]
        faixa = config.POPULACAO_API_IDADES[cat["287"]]
        for serie in res["series"]:
            valor = serie["serie"]["2022"]
            n = 0 if valor in ("-", "0") else int(valor)
            chave = (serie["localidade"]["id"], sexo, faixa)
            linha = acc.setdefault(chave, {})
            linha[cor] = linha.get(cor, 0) + n


def tarefas() -> list[tuple[int, list[str]]]:
    idades = list(config.POPULACAO_API_IDADES)
    lista = []
    for uf in config.UF_CODIGO_PARA_SIGLA:
        passo = 2 if uf in config.POPULACAO_API_UFS_GRANDES else 4
        lista += [(uf, idades[i:i + passo]) for i in range(0, len(idades), passo)]
    return lista


def main() -> None:
    acc: dict = {}
    lista = tarefas()
    print(f"Consultando a API do IBGE ({len(lista)} requisições)...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        for resultados in pool.map(lambda t: baixar(*t), lista):
            acumular(resultados, acc)

    cores = list(config.POPULACAO_API_CORES.values())
    faixas = [f for _, _, f in config.SIM_FAIXAS_ETARIAS]
    chaves = sorted(acc, key=lambda k: (k[0], k[1], faixas.index(k[2])))
    config.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.POPULACAO_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["codigo_ibge", "sexo", "faixa_etaria"] + [f"pop_{c}" for c in cores])
        for chave in chaves:
            w.writerow(list(chave) + [acc[chave][c] for c in cores])

    total = sum(acc[k]["total"] for k in chaves)
    print(f"{len(chaves):,} linhas · população total: {total:,}".replace(",", "."))
    print(f"Arquivo gerado: {config.POPULACAO_FILE.relative_to(config.ROOT_DIR).as_posix()}")


if __name__ == "__main__":
    main()
