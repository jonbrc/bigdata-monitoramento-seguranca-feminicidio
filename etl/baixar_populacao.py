"""Gera data/reference/populacao_feminina_censo2022.csv a partir da API SIDRA do IBGE.

O arquivo já está versionado no repositório; este script só precisa ser
executado para regerá-lo (requer acesso à internet):

    python -m etl.baixar_populacao

Fonte: IBGE, Censo Demográfico 2022, tabela 9606 — população residente por cor
ou raça, segundo o sexo e a idade. Filtros: sexo = Mulheres, idade = Total,
nível territorial = município.
"""

import csv
import json
import urllib.request

from etl import config


def converter(registros: list[dict]) -> list[list]:
    """Converte a resposta da API (formato /f/c/h/n: uma linha por município × cor)
    em uma linha por município, com uma coluna por cor ou raça.

    D1C = código do município; D5C = código da cor ou raça; V = valor.
    No SIDRA, "-" significa zero absoluto.
    """
    cores = list(config.POPULACAO_SIDRA_CORES.values())
    por_municipio: dict[str, dict] = {}
    for r in registros:
        cor = config.POPULACAO_SIDRA_CORES.get(str(r["D5C"]))
        if cor is None:
            continue
        valor = 0 if r["V"] in ("-", "0") else int(r["V"])
        por_municipio.setdefault(str(r["D1C"]), {})[cor] = valor
    linhas = []
    for codigo in sorted(por_municipio):
        valores = por_municipio[codigo]
        faltando = [c for c in cores if c not in valores]
        if faltando:
            raise ValueError(f"Município {codigo} sem as categorias {faltando}")
        linhas.append([codigo] + [valores[c] for c in cores])
    return linhas


def main() -> None:
    print(f"Baixando {config.POPULACAO_SIDRA_URL} ...")
    with urllib.request.urlopen(config.POPULACAO_SIDRA_URL, timeout=120) as resp:
        registros = json.load(resp)
    linhas = converter(registros)

    cabecalho = ["codigo_ibge"] + [f"pop_fem_{c}" for c in config.POPULACAO_SIDRA_CORES.values()]
    config.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.POPULACAO_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cabecalho)
        w.writerows(linhas)

    total = sum(linha[1] for linha in linhas)
    print(f"{len(linhas)} municípios; população feminina total: {total:,}".replace(",", "."))
    print(f"Arquivo gerado: {config.POPULACAO_FILE.relative_to(config.ROOT_DIR).as_posix()}")


if __name__ == "__main__":
    main()
