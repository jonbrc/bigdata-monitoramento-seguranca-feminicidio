"""Configuração centralizada do ETL.

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

# Recorte temático (AI02: "violência letal e violência contra mulheres").
# Só eventos registrados por município; Estupro e Estupro de vulnerável ficam
# de fora porque a base só os traz agregados por UF (município "NÃO INFORMADO").
# Valor = sufixo usado nos nomes das colunas do CSV final.
SINESP_EVENTOS = {
    "Feminicídio": "feminicidio",
    "Tentativa de feminicídio": "tentativa_feminicidio",
    "Homicídio doloso": "homicidio_doloso",
    "Tentativa de homicídio": "tentativa_homicidio",
    "Lesão corporal seguida de morte": "lesao_corporal_morte",
    "Roubo seguido de morte (latrocínio)": "latrocinio",
}
SINESP_ABRANGENCIA = "Estadual"
SINESP_MUNICIPIO_NAO_INFORMADO = "NÃO INFORMADO"

# Grafias do Sinesp que não batem com o nome oficial do IBGE mesmo após a
# normalização (nome antigo ou variante). (UF, nome no Sinesp) -> código IBGE.
SINESP_MUNICIPIOS_EQUIVALENCIAS = {
    ("BA", "MUQUÉM DO SÃO FRANCISCO"): "2922250",  # Muquém de São Francisco
    ("BA", "SANTA TEREZINHA"): "2928505",          # Santa Teresinha
    ("MG", "DONA EUZÉBIA"): "3122900",             # Dona Eusébia
    ("MG", "SÃO TOMÉ DAS LETRAS"): "3165206",      # São Thomé das Letras
    ("PE", "SÃO CAITANO"): "2613107",              # São Caetano
    ("RN", "CAMPO GRANDE"): "2401305",             # Augusto Severo (Campo Grande)
    ("RN", "JANUÁRIO CICCO"): "2405306",           # Januário Cicco (Boa Saúde)
    ("SE", "AMPARO DO SÃO FRANCISCO"): "2800100",  # Amparo de São Francisco
    ("SP", "FLORÍNEA"): "3516101",                 # Florínia
    ("TO", "TABOCÃO"): "1708254",                  # Fortaleza do Tabocão
}

# ---------------------------------------------------------------------------
# Base 2 — SIM 2025 preliminar (Ministério da Saúde)
# ---------------------------------------------------------------------------
SIM_FILE = RAW_DIR / "Mortalidade_Geral_2025.csv"
SIM_SEPARATOR = ";"
SIM_ENCODING = "latin-1"
SIM_CHUNKSIZE = 200_000  # leitura em blocos (Pandas chunking)

# Colunas do SIM mapeadas na AI02 (itens 4 — base de dados 2).
SIM_COLUNAS_AI02 = [
    "DTOBITO", "SEXO", "CAUSABAS", "CODMUNRES", "CODMUNOCOR", "RACACOR",
    "IDADE", "ESTCIV", "ESC2010", "LOCOCOR", "CODESTAB", "NATURAL",
    "CODMUNNATU", "TIPOBITO",
]

# Recorte definido na AI02: óbitos de mulheres (SEXO = 2) cuja causa básica
# seja agressão, CID-10 X85 a Y09. A comparação usa os 3 primeiros caracteres
# do CID (categoria), em ordem lexicográfica: X85..X99, Y00..Y09.
SIM_SEXO_FEMININO = "2"
SIM_CID_AGRESSAO_INICIO = "X85"
SIM_CID_AGRESSAO_FIM = "Y09"

# Raça/cor do SIM (dicionário de dados do SIM). Ausente ou fora da lista -> "raca_ignorada".
SIM_RACACOR = {
    "1": "branca",
    "2": "preta",
    "3": "amarela",
    "4": "parda",
    "5": "indigena",
}
SIM_RACACOR_IGNORADA = "raca_ignorada"

# Faixas etárias para as contagens do SIM: (idade mínima, idade máxima ou None, sufixo).
# 0–17 = menores de idade (ECA); 60+ = pessoas idosas (Estatuto da Pessoa Idosa).
SIM_FAIXAS_ETARIAS = [
    (0, 17, "idade_0_17"),
    (18, 29, "idade_18_29"),
    (30, 39, "idade_30_39"),
    (40, 49, "idade_40_49"),
    (50, 59, "idade_50_59"),
    (60, None, "idade_60_mais"),
]
SIM_FAIXA_IGNORADA = "idade_ignorada"

# Base preliminar: há óbitos só até 02/09/2025 e agosto está incompleto
# (~metade do volume dos meses anteriores). Meses de 2025 considerados cobertos:
SIM_ANO = 2025
SIM_MESES_COBERTOS = list(range(1, 9))  # janeiro a agosto

# ---------------------------------------------------------------------------
# Tabela de referência — municípios com código IBGE
# ---------------------------------------------------------------------------
# A base do Sinesp identifica o município apenas por UF + nome; o SIM usa o
# código IBGE. Esta tabela faz a ponte entre os dois (ver README).
# Fonte: https://github.com/kelvins/municipios-brasileiros (csv/municipios.csv)
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

# Região geográfica de cada UF
UF_PARA_REGIAO = {
    "AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte", "RO": "Norte",
    "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste",
    "SE": "Nordeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MS": "Centro-Oeste", "MT": "Centro-Oeste",
}

# ---------------------------------------------------------------------------
# Tabela de referência — população feminina (IBGE, Censo Demográfico 2022)
# ---------------------------------------------------------------------------
# Tabela SIDRA 9606 (população residente por cor ou raça, sexo e idade), sexo =
# Mulheres, idade = Total, todas as categorias de cor ou raça, nível município.
# Gerada por `python -m etl.baixar_populacao`. É o dado oficial mais recente com
# população por sexo e cor/raça no nível municipal (as estimativas anuais do IBGE
# não têm esse detalhamento).
POPULACAO_FILE = REFERENCE_DIR / "populacao_feminina_censo2022.csv"
POPULACAO_SIDRA_URL = (
    "https://apisidra.ibge.gov.br/values/t/9606/n6/all/v/93/p/2022"
    "/c2/5/c86/all/c287/100362/f/c/h/n"
)
# Código SIDRA da categoria de cor ou raça -> sufixo da coluna
POPULACAO_SIDRA_CORES = {
    "95251": "total",   # inclui cor/raça ignorada
    "2776": "branca",
    "2777": "preta",
    "2778": "amarela",
    "2779": "parda",
    "2780": "indigena",
}

# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------
OUTPUT_FILE = PROCESSED_DIR / "violencia_feminicidio_municipio_mes_2025.csv"
OUTPUT_SEPARATOR = ","
OUTPUT_ENCODING = "utf-8"
EDA_REPORT_FILE = DOCS_DIR / "analise_exploratoria.md"
