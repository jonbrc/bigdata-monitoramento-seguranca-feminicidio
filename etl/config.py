"""Configuração central do ETL: caminhos, bases por ano, recortes temáticos, mapeamentos de categorias e parâmetros de saída e do banco."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
REFERENCE_DIR = DATA_DIR / "reference"
PROCESSED_DIR = DATA_DIR / "processed"
DOCS_DIR = ROOT_DIR / "docs"

SINESP_ARQUIVOS = {
    2024: RAW_DIR / "BancoVDE 2024.xlsx",
    2025: RAW_DIR / "BancoVDE 2025 (1).xlsx",
}
SINESP_EXCEL_ENGINE = "calamine"

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

SINESP_MUNICIPIOS_EQUIVALENCIAS = {
    ("BA", "MUQUÉM DO SÃO FRANCISCO"): "2922250",
    ("BA", "SANTA TEREZINHA"): "2928505",
    ("MG", "DONA EUZÉBIA"): "3122900",
    ("MG", "SÃO TOMÉ DAS LETRAS"): "3165206",
    ("PE", "SÃO CAITANO"): "2613107",
    ("RN", "CAMPO GRANDE"): "2401305",
    ("RN", "JANUÁRIO CICCO"): "2405306",
    ("SE", "AMPARO DO SÃO FRANCISCO"): "2800100",
    ("SP", "FLORÍNEA"): "3516101",
    ("TO", "TABOCÃO"): "1708254",
}

SIM_ARQUIVOS = {
    2024: RAW_DIR / "Mortalidade_Geral_2024.csv",
    2025: RAW_DIR / "Mortalidade_Geral_2025.csv",
}
SIM_SEPARATOR = ";"
SIM_ENCODING = "latin-1"
SIM_CHUNKSIZE = 200_000

SIM_COLUNAS_AI02 = [
    "DTOBITO", "SEXO", "CAUSABAS", "CODMUNRES", "CODMUNOCOR", "RACACOR",
    "IDADE", "ESTCIV", "ESC2010", "LOCOCOR", "CODESTAB", "NATURAL",
    "CODMUNNATU", "TIPOBITO",
]

SIM_SEXO_FEMININO = "2"
SIM_CID_AGRESSAO_INICIO = "X85"
SIM_CID_AGRESSAO_FIM = "Y09"

SIM_RACACOR = {
    "1": "branca",
    "2": "preta",
    "3": "amarela",
    "4": "parda",
    "5": "indigena",
}
SIM_RACACOR_IGNORADA = "raca_ignorada"

SIM_SEXO = {"1": "masculino", "2": "feminino"}

SIM_LOCAL_OBITO = {
    "1": "estabelecimento_saude",
    "2": "estabelecimento_saude",
    "3": "domicilio",
    "4": "via_publica",
    "5": "outros",
    "6": "aldeia_indigena",
}
SIM_LOCAL_IGNORADO = "local_ignorado"

SIM_MEIO_AGRESSAO = {
    **{f"X{n}": "envenenamento" for n in range(85, 91)},
    "X91": "enforcamento_sufocacao",
    "X92": "outros",
    "X93": "arma_fogo", "X94": "arma_fogo", "X95": "arma_fogo",
    "X96": "outros", "X97": "outros", "X98": "outros",
    "X99": "objeto_cortante",
    "Y00": "objeto_contundente",
    "Y01": "outros", "Y02": "outros", "Y03": "outros",
    "Y04": "forca_corporal", "Y05": "forca_corporal",
    "Y06": "maus_tratos", "Y07": "maus_tratos",
    "Y08": "outros",
    "Y09": "meio_nao_especificado",
}

SIM_FAIXAS_ETARIAS = [
    (0, 17, "idade_0_17"),
    (18, 29, "idade_18_29"),
    (30, 39, "idade_30_39"),
    (40, 49, "idade_40_49"),
    (50, 59, "idade_50_59"),
    (60, None, "idade_60_mais"),
]
SIM_FAIXA_IGNORADA = "idade_ignorada"

SIM_MESES_COBERTOS = {
    2024: list(range(1, 13)),
    2025: list(range(1, 9)),
}
ANOS = sorted(SINESP_ARQUIVOS)

MUNICIPIOS_FILE = REFERENCE_DIR / "municipios_ibge.csv"
MUNICIPIOS_ENCODING = "utf-8"

UF_CODIGO_PARA_SIGLA = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}

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

POPULACAO_FILE = REFERENCE_DIR / "populacao_censo2022.csv"
POPULACAO_API_URL = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/9606/periodos/2022/variaveis/93"
    "?localidades=N6[N3[{uf}]]&classificacao=2[{sexos}]|86[all]|287[{idades}]"
)
POPULACAO_API_SEXOS = {"4": "masculino", "5": "feminino"}
POPULACAO_API_CORES = {
    "95251": "total",
    "2776": "branca",
    "2777": "preta",
    "2778": "amarela",
    "2779": "parda",
    "2780": "indigena",
}
POPULACAO_API_IDADES = {
    "93070": "idade_0_17", "93084": "idade_0_17", "93085": "idade_0_17",
    "6572": "idade_0_17", "6573": "idade_0_17", "6574": "idade_0_17",
    "6575": "idade_18_29", "6576": "idade_18_29", "93087": "idade_18_29", "93088": "idade_18_29",
    "93089": "idade_30_39", "93090": "idade_30_39",
    "93091": "idade_40_49", "93092": "idade_40_49",
    "93093": "idade_50_59", "93094": "idade_50_59",
    "93095": "idade_60_mais", "93096": "idade_60_mais", "93097": "idade_60_mais",
    "93098": "idade_60_mais", "49108": "idade_60_mais", "49109": "idade_60_mais",
    "60040": "idade_60_mais", "60041": "idade_60_mais", "6653": "idade_60_mais",
}
POPULACAO_API_UFS_GRANDES = {31, 35}

OUTPUT_FILE = PROCESSED_DIR / "violencia_feminicidio_municipio_mes.csv"
OUTPUT_SIM_FILE = PROCESSED_DIR / "sim_obitos_agressao.csv"
OUTPUT_SEPARATOR = ","
OUTPUT_ENCODING = "utf-8"
EDA_REPORT_FILE = DOCS_DIR / "analise_exploratoria.md"

SCHEMA_SQL_FILE = ROOT_DIR / "sql" / "schema.sql"
DB_SCHEMA = "dw"
ENV_FILE = ROOT_DIR / ".env"
DB_ENV_OBRIGATORIAS = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
DB_SSLMODE_PADRAO = "require"
