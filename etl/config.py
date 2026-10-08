""" Configuração centralizada do ETL.

Todos os caminhos, nomes de arquivo, encodings e parâmetros de tratamento
ficam aqui. Os demais módulos importam deste arquivo e não definem caminhos
próprios. Os caminhos são relativos à raiz do repositório, então o processo
roda em qualquer máquina sem editar o código.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Diretórios
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"              # bases brutas (somente leitura)
REFERENCE_DIR = DATA_DIR / "reference"  # tabelas auxiliares versionadas
PROCESSED_DIR = DATA_DIR / "processed"  # saída do ETL
DOCS_DIR = ROOT_DIR / "docs"

# ---------------------------------------------------------------------------
# Base 1 — Sinesp VDE 2025 (MJSP)
# ---------------------------------------------------------------------------
SINESP_FILE = RAW_DIR / "BancoVDE 2025 (1).xlsx"
SINESP_SHEET = "2025"
# O motor "calamine" lê o .xlsx ~7x mais rápido que o openpyxl (≈15 s vs ≈110 s).
SINESP_EXCEL_ENGINE = "calamine"

# ---------------------------------------------------------------------------
# Base 2 — SIM 2025 preliminar (Ministério da Saúde)
# ---------------------------------------------------------------------------
SIM_FILE = RAW_DIR / "Mortalidade_Geral_2025.csv"
SIM_SEPARATOR = ";"
SIM_ENCODING = "latin-1"
SIM_CHUNKSIZE = 200_000  # leitura em blocos (Pandas chunking)

# ---------------------------------------------------------------------------
# Tabela de referência — municípios com código IBGE
# ---------------------------------------------------------------------------
# A base do Sinesp identifica o município apenas por UF + nome; o SIM usa o
# código IBGE. Esta tabela faz a ponte entre os dois (ver README).
MUNICIPIOS_FILE = REFERENCE_DIR / "municipios_ibge.csv"
MUNICIPIOS_ENCODING = "utf-8"

# Código numérico da UF (2 primeiros dígitos do código IBGE) -> sigla
UF_CODIGO_PARA_SIGLA = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}

# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------
OUTPUT_ENCODING = "utf-8"
