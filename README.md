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
│   └── processed/    # violencia_feminicidio_municipio_mes_2025.csv (saída do ETL)
├── docs/
│   └── analise_exploratoria.md   # gerado por etl/exploratory_analysis.py
├── etl/
│   ├── config.py                 # caminhos e parâmetros centralizados
│   ├── extract.py                # leitura das bases (SIM em blocos)
│   ├── padronizacao.py           # normalização de nomes e códigos IBGE
│   ├── transform_sinesp.py       # tratamento da Base 1 (Sinesp)
│   ├── transform_sim.py          # tratamento da Base 2 (SIM)
│   ├── merge.py                  # relacionamento Sinesp × SIM
│   ├── validate.py               # verificações do resultado
│   ├── main.py                   # pipeline completo (ponto de entrada)
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

## Execução do ETL

Com as bases em `data/raw/` e o ambiente ativado, na raiz do repositório:

```bash
python -m etl.main
```

O script lê as duas bases, trata cada uma, relaciona, valida e grava
`data/processed/violencia_feminicidio_municipio_mes_2025.csv` (cerca de 30 s).
Se alguma verificação falhar, o CSV não é gravado e o script termina com código 1.

## Análise exploratória

Na raiz do repositório:

```bash
python -m etl.exploratory_analysis
```

Lê as duas bases (o SIM em blocos de 200 mil linhas) e gera [`docs/analise_exploratoria.md`](docs/analise_exploratoria.md) com o perfil de cada uma: registros, colunas, tipos, nulos, duplicidades, período, consistência dos códigos e compatibilidade das chaves de município entre as fontes. Leva cerca de 1 minuto.

## Tratamento — Base 1 (Sinesp VDE)

Teste isolado: `python -m etl.transform_sinesp` (imprime as contagens de cada passo).

| # | Passo | Decisão e justificativa |
|---|---|---|
| 1 | Padronização de texto | `uf`, `municipio`, `evento` sem espaços nas pontas; `uf` e `municipio` em maiúsculas. |
| 2 | Recorte temático | Mantém 6 eventos de violência letal e contra a mulher, registrados por município: Feminicídio, Tentativa de feminicídio, Homicídio doloso, Tentativa de homicídio, Lesão corporal seguida de morte, Latrocínio. Estupro e Estupro de vulnerável ficam de fora porque só existem agregados por UF. |
| 3 | Município "NÃO INFORMADO" | Tratado como nulo (AI02). Como não pode ser relacionado a um município do SIM, a linha sai; as vítimas descartadas são contadas (7 no recorte). |
| 4 | Nulos por sexo | `feminino`/`masculino`/`nao_informado` nulos viram 0: em todas as linhas `total_vitima` está preenchido e é igual à soma por sexo, então o nulo significa "nenhuma vítima nessa categoria". O script interrompe se essa regra for violada. |
| 5 | Colunas sem uso | `agente`, `arma`, `faixa_etaria`, `total`, `total_peso` (100% nulas no recorte) e `abrangencia` (constante) saem. |
| 6 | Duplicidades | O DF tem 33 linhas por mês/evento, todas como "BRASÍLIA" (provavelmente uma por região administrativa). São **somadas**, não descartadas, para obter o total do município. O script confere que o total de vítimas não muda. |
| 7 | Tipos | Contagens como inteiros; `data_referencia` vira `ano` e `mes`. |
| 8 | Código IBGE | Associado por UF + nome normalizado com `data/reference/municipios_ibge.csv`; 10 grafias divergentes resolvidas por uma lista explícita de equivalências em `etl/config.py`. O nome do município passa a ser o oficial da tabela de referência. |
| 9 | Pivot | Uma linha por **município × mês**; para cada evento, as colunas `sinesp_<evento>_fem` (vítimas femininas) e `sinesp_<evento>_total` (todas as vítimas). |

## Tratamento — Base 2 (SIM)

Teste isolado: `python -m etl.transform_sim` (imprime as contagens de cada passo).

| # | Passo | Decisão e justificativa |
|---|---|---|
| 1 | Recorte na leitura | O CSV (~937 mil linhas) é lido em blocos de 200 mil e só ficam em memória os óbitos com `SEXO = 2` (feminino) e causa básica entre X85 e Y09 (agressão), como definido na AI02. O `*` do CID é removido antes da comparação, se existir. |
| 2 | Duplicidades | `contador` é só um número sequencial. Linhas idênticas em todas as outras colunas seriam a mesma declaração repetida e são removidas (nenhuma no arquivo atual). |
| 3 | Colunas | Ficam só as colunas mapeadas na AI02. Data de nascimento, dados da mãe e demais campos saem (minimização de dados, LGPD). |
| 4 | Datas | `DTOBITO` (`ddmmaaaa`) vira data e depois `ano` e `mes`; datas inválidas sairiam (nenhuma). |
| 5 | Período coberto | Base preliminar: óbitos só até 02/09/2025, agosto incompleto. Meses considerados cobertos: janeiro a agosto (`SIM_MESES_COBERTOS` em `etl/config.py`). |
| 6 | Município de residência | `CODMUNRES` é a chave de relacionamento (AI02). Códigos terminados em `0000` indicam município ignorado (só a UF é conhecida) e saem, pois não podem ser ligados a um município (6 óbitos). |
| 7 | Raça/cor | Código convertido em categoria (branca, preta, amarela, parda, indígena); nulo vira "ignorada". |
| 8 | Agregação | Uma linha por município × mês: `sim_obitos_fem_agressao` (total) e `sim_obitos_fem_<raça>`. O script confere que o total de óbitos não muda. |

## Relacionamento (Sinesp × SIM)

```text
Sinesp.uf + Sinesp.municipio ──(tabela IBGE)──► codigo_ibge (7 díg.) ──► 6 primeiros dígitos ┐
Sinesp.data_referencia ──► ano + mes                                                         ├─ chave
SIM.CODMUNRES (6 díg.) + SIM.DTOBITO ──► ano + mes                                           ┘
```

- **Campos:** código IBGE do município (6 dígitos) + ano + mês. O município do SIM é o de **residência** (`CODMUNRES`), como definido na AI02.
- **Padronização:** o Sinesp só tem UF + nome; o nome é normalizado (sem acento, maiúsculas, sem hífen/apóstrofo) e associado ao código IBGE pela tabela de referência. O código de 7 dígitos é reduzido aos 6 usados pelo SIM.
- **Tipo de JOIN:** `FULL OUTER JOIN` sobre a grade município × mês. Assim nenhum óbito do SIM se perde e os municípios sem óbito continuam presentes com os dados do Sinesp.
- **Por quê:** o SIM não registra "feminicídio" e não há identificador comum de vítima entre as bases; o óbito feminino por agressão é usado como aproximação e o cruzamento é feito por município e mês (AI02).
- **Período:** nos meses cobertos pelo SIM (jan–ago/2025), município sem óbito recebe 0; nos meses sem cobertura (set–dez), as colunas do SIM ficam vazias (NULL) e `sim_periodo_coberto = False`.
- **Linhas sem ocorrência:** município × mês em que todas as contagens das duas bases são zero é removido (AI02, otimização de volume).
