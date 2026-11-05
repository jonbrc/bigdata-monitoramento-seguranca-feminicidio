"""Orquestra o ETL completo (extração → transformação → relacionamento → validação) e grava os CSVs tratados em data/processed/."""

import sys
import time

from etl import config, extract
from etl.merge import relacionar
from etl.transform_sim import ler_e_tratar_sim
from etl.transform_sim import resumo as resumo_sim
from etl.transform_sinesp import resumo as resumo_sinesp
from etl.transform_sinesp import tratar_sinesp
from etl.validate import validar, validar_detalhamento


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main() -> int:
    inicio = time.time()
    print("=" * 64)
    print(f"ETL — Monitoramento de Segurança Pública e Feminicídio ({'-'.join(map(str, config.ANOS))})")
    print("=" * 64)

    municipios = extract.ler_municipios()
    print("\n[1/4] Sinesp: lendo e tratando...")
    sinesp, est_sinesp = tratar_sinesp(extract.ler_sinesp(), municipios)
    print(resumo_sinesp(est_sinesp))

    print("\n[2/4] SIM: lendo em blocos e tratando...")
    sim, sim_detalhado, est_sim = ler_e_tratar_sim(municipios)
    print(resumo_sim(est_sim))

    print("\n[3/4] Relacionando Sinesp × SIM (código IBGE 6 dígitos + ano + mês)...")
    final, est_rel = relacionar(sinesp, sim, municipios, extract.ler_populacao())
    print("Relacionamento:")
    print(f"  Registros antes do JOIN:   Sinesp {fmt(est_rel['registros_sinesp'])} | SIM {fmt(est_rel['registros_sim'])}")
    print(f"  Registros relacionados:    {fmt(est_rel['relacionados'])} (município × mês presentes nas duas bases)")
    print(f"  Sem correspondência:       {fmt(est_rel['somente_sinesp'])} só no Sinesp (sem óbito no SIM) | "
          f"{fmt(est_rel['somente_sim'])} só no SIM ({est_rel['obitos_somente_sim']} óbitos)")
    print(f"  Linhas sem ocorrência removidas: {fmt(est_rel['linhas_sem_ocorrencia_removidas'])}")
    print(f"  Linhas sem população (Censo 2022): {fmt(est_rel['linhas_sem_populacao'])}")

    print("\n[4/4] Validando...")
    checks = validar(final, est_sinesp, est_sim, est_rel) + validar_detalhamento(sim_detalhado, final, est_sim)
    for descricao, ok in checks:
        print(f"  [{'OK' if ok else 'FALHOU'}] {descricao}")
    if not all(ok for _, ok in checks):
        print("\nValidação falhou: o CSV não foi gerado.")
        return 1

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    final.to_csv(config.OUTPUT_FILE, index=False, sep=config.OUTPUT_SEPARATOR,
                 encoding=config.OUTPUT_ENCODING)
    sim_detalhado.to_csv(config.OUTPUT_SIM_FILE, index=False, sep=config.OUTPUT_SEPARATOR,
                         encoding=config.OUTPUT_ENCODING)

    print("\nResultado:")
    print(f"  Registros finais: {fmt(len(final))}")
    print(f"  Colunas finais:   {final.shape[1]}")
    print(f"  Municípios:       {fmt(final['codigo_ibge'].nunique())}")
    print(f"  Detalhamento SIM: {fmt(len(sim_detalhado))} linhas · {fmt(int(sim_detalhado['obitos'].sum()))} óbitos")
    print("\nArquivos gerados:")
    print(f"  {config.OUTPUT_FILE.relative_to(config.ROOT_DIR).as_posix()}")
    print(f"  {config.OUTPUT_SIM_FILE.relative_to(config.ROOT_DIR).as_posix()}")
    print(f"\nTempo total: {time.time() - inicio:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
