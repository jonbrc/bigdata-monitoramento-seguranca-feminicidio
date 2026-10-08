# Monitoramento de Segurança Pública e Feminicídio Interseccional

Projeto prático da disciplina **Big Data & Analytics** (UCSal).

**Grupo:** João Bruno Reis Carvalho dos Santos · Lucas Danilo Santos Araújo · Maria Fernanda Pereira Barcante Costa · Rafael Farias Castro

## Objetivo

Cruzar, por **município e mês**, os registros policiais de violência letal e de violência contra mulheres (Sinesp/MJSP) com os óbitos de mulheres por agressão registrados no sistema de saúde (SIM/Ministério da Saúde), em 2025. O SIM não tem a categoria "feminicídio", então o óbito feminino por agressão (CID-10 X85–Y09) serve como aproximação, e a comparação é feita por município, não vítima a vítima.

Alinhamento: ODS 5 (Igualdade de Gênero) e ODS 18 (Igualdade Étnico-Racial).

> Esta etapa (AI03) cobre só o ETL até um CSV final tratado. A carga no PostgreSQL (Aiven) fica para a etapa seguinte.

## Bases de dados

| Base | Origem | Formato | Período | Granularidade |
|---|---|---|---|---|
| **Sinesp VDE 2025** | Ministério da Justiça e Segurança Pública (portal de dados abertos) | `.xlsx` (~26 MB) | jan–dez/2025, mensal | município × mês × tipo de evento |
| **SIM 2025 – preliminar** | Ministério da Saúde (OpenDataSUS) | `.csv` `;` latin-1 (~300 MB) | 2025 (dados preliminares) | uma linha por declaração de óbito |
| **Municípios IBGE** (referência) | [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) | `.csv` UTF-8 | — | um município por linha |

A tabela de municípios é necessária porque o Sinesp identifica o município só por **UF + nome**, enquanto o SIM usa o **código IBGE**.

## Estrutura do repositório

```text
.
├── data/
│   ├── raw/          # bases brutas (fora do Git; ver abaixo)
│   ├── reference/    # municipios_ibge.csv (versionado)
│   └── processed/    # CSV final gerado pelo ETL
├── docs/
│   └── analise_exploratoria.md   # gerado por etl/exploratory_analysis.py
├── etl/
│   ├── config.py                 # caminhos e parâmetros centralizados
│   ├── extract.py                # leitura das bases (SIM em blocos)
│   ├── padronizacao.py           # normalização de nomes e códigos IBGE
│   └── exploratory_analysis.py   # análise exploratória das bases brutas
├── requirements.txt
└── README.md
```

## Preparação dos dados brutos

As bases brutas **não são versionadas** (o CSV do SIM passa do limite de 100 MB do GitHub). Baixe-as e copie para `data/raw/` com estes nomes exatos:

```text
data/raw/BancoVDE 2025 (1).xlsx
data/raw/Mortalidade_Geral_2025.csv
```

Os nomes ficam configurados em `etl/config.py`. O ETL apenas lê esses arquivos e nunca os modifica.

## Ambiente

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Análise exploratória

Na raiz do repositório:

```bash
python -m etl.exploratory_analysis
```

Lê as duas bases (o SIM em blocos de 200 mil linhas) e gera [`docs/analise_exploratoria.md`](docs/analise_exploratoria.md) com o perfil de cada uma: registros, colunas, tipos, nulos, duplicidades, período, consistência dos códigos e compatibilidade das chaves de município entre as fontes. Leva cerca de 1 minuto.
