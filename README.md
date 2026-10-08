# Monitoramento de Segurança Pública e Feminicídio Interseccional

Projeto prático da disciplina **Big Data & Analytics** (UCSal) — etapa AI03: unificação e tratamento dos dados.

**Grupo:** João Bruno Reis Carvalho dos Santos · Lucas Danilo Santos Araújo · Maria Fernanda Pereira Barcante Costa · Rafael Farias Castro

## Objetivo

Cruzar, por **município e mês**, os registros policiais de violência letal e de violência contra mulheres (Sinesp/MJSP) com os óbitos de mulheres por agressão registrados no sistema de saúde (SIM/Ministério da Saúde), em 2025, permitindo comparar as duas fontes e analisar o perfil racial das vítimas.

Alinhamento: ODS 5 (Igualdade de Gênero) e ODS 18 (Igualdade Étnico-Racial).

## Visão geral

O ETL lê as duas bases públicas sem modificá-las e gera um único CSV tratado, que na etapa seguinte será carregado no PostgreSQL (Aiven). Do **Sinesp VDE 2025** (Ministério da Justiça), que traz ocorrências policiais mensais por município, ficam seis eventos: feminicídio, tentativa de feminicídio, homicídio doloso, tentativa de homicídio, lesão corporal seguida de morte e latrocínio. Do **SIM 2025** (Ministério da Saúde), em que cada linha é uma declaração de óbito, ficam apenas os óbitos de mulheres cuja causa básica foi agressão (CID-10 X85 a Y09). As bases não têm uma chave comum pronta: o Sinesp identifica o município só por UF e nome, enquanto o SIM usa o código IBGE de 6 dígitos do município de residência. O script padroniza o nome do município, obtém o código IBGE por meio de uma tabela de referência e relaciona as bases por **código IBGE + ano + mês**. Como o SIM não registra "feminicídio", o cruzamento é feito por município, e não vítima a vítima: o óbito feminino por agressão serve como aproximação comparada ao que a polícia registrou. **Cada linha do CSV final representa um município em um mês de 2025**, com as vítimas (mulheres e total) de cada evento do Sinesp e os óbitos femininos por agressão do SIM, no total e por raça/cor.

> Esta etapa não inclui a carga no PostgreSQL/Aiven; o CSV foi preparado para isso (ver [Próxima etapa](#próxima-etapa-postgresql--aiven)).

## Bases de dados

| Base | Origem | Formato | Período | Granularidade | Registros |
|---|---|---|---|---|---|
| **Sinesp VDE 2025** | Ministério da Justiça e Segurança Pública (portal de dados abertos) | `.xlsx` (~26 MB), aba `2025` | jan–dez/2025, mensal | UF × município × mês × evento | 832.293 |
| **SIM 2025 – preliminar** | Ministério da Saúde (OpenDataSUS), atualizado em 31/08/2026 | `.csv`, separador `;`, latin-1 (~300 MB) | 01/01 a 02/09/2025 | uma linha por declaração de óbito | 937.033 |
| **Municípios IBGE** (referência) | [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) (`csv/municipios.csv`) | `.csv` UTF-8 | — | um município por linha | 5.571 |

**Principais campos utilizados**

- **Sinesp:** `uf`, `municipio`, `evento`, `data_referencia`, `feminino`, `masculino`, `nao_informado`, `total_vitima`, `abrangencia`.
- **SIM:** `DTOBITO`, `SEXO`, `CAUSABAS`, `CODMUNRES`, `RACACOR` (usados no resultado), além dos demais campos mapeados na AI02 (`CODMUNOCOR`, `IDADE`, `ESTCIV`, `ESC2010`, `LOCOCOR`, `CODESTAB`, `NATURAL`, `CODMUNNATU`, `TIPOBITO`), mantidos durante o tratamento.
- **Referência:** `codigo_ibge`, `nome`, `codigo_uf` — necessária porque o Sinesp não tem código IBGE.

O perfil completo das bases brutas (nulos, duplicidades, períodos, inconsistências) está em [`docs/analise_exploratoria.md`](docs/analise_exploratoria.md).

## Estrutura do repositório

```text
.
├── data/
│   ├── raw/                      # bases brutas (fora do Git)
│   ├── reference/
│   │   └── municipios_ibge.csv   # tabela de municípios (versionada)
│   └── processed/
│       └── violencia_feminicidio_municipio_mes_2025.csv   # saída do ETL (versionada)
├── docs/
│   └── analise_exploratoria.md   # gerado por etl/exploratory_analysis.py
├── etl/
│   ├── config.py                 # caminhos e parâmetros centralizados
│   ├── extract.py                # EXTRAÇÃO: leitura das bases (SIM em blocos)
│   ├── padronizacao.py           # normalização de nomes e códigos IBGE
│   ├── transform_sinesp.py       # TRANSFORMAÇÃO da Base 1
│   ├── transform_sim.py          # TRANSFORMAÇÃO da Base 2
│   ├── merge.py                  # RELACIONAMENTO Sinesp × SIM
│   ├── validate.py               # VALIDAÇÃO do resultado
│   ├── main.py                   # pipeline completo (ponto de entrada)
│   └── exploratory_analysis.py   # análise exploratória das bases brutas
├── requirements.txt
└── README.md
```

## Execução

### 1. Dados brutos

As bases brutas **não são versionadas**: o CSV do SIM tem ~300 MB, acima do limite de 100 MB do GitHub. Baixe-as nos portais de origem e copie para `data/raw/` com estes nomes exatos (configurados em `etl/config.py`):

```text
data/raw/BancoVDE 2025 (1).xlsx
data/raw/Mortalidade_Geral_2025.csv
```

O ETL apenas lê esses arquivos e nunca os modifica.

### 2. Ambiente (Python 3.10+)

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

No Windows, se o PowerShell bloquear a ativação, execute uma vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### 3. Rodar o ETL

Na raiz do repositório:

```bash
python -m etl.main
```

Leva cerca de 30 segundos e gera `data/processed/violencia_feminicidio_municipio_mes_2025.csv`. O terminal mostra as contagens de cada etapa e o resultado de cada verificação. Se alguma verificação falhar, o CSV **não** é gravado e o script termina com código 1.

Comandos auxiliares:

| Comando | O que faz |
|---|---|
| `python -m etl.transform_sinesp` | Executa só o tratamento do Sinesp e imprime as contagens |
| `python -m etl.transform_sim` | Executa só o tratamento do SIM e imprime as contagens |
| `python -m etl.exploratory_analysis` | Regenera `docs/analise_exploratoria.md` (~1 min) |

## Fluxo do ETL

```text
EXTRAÇÃO         Sinesp (.xlsx, inteiro)              SIM (.csv, blocos de 200 mil; filtro na leitura)
                        │                                     │
TRANSFORMAÇÃO    recorte de eventos                    duplicidades
                 município "NÃO INFORMADO"             colunas da AI02 (LGPD)
                 nulos por sexo → 0                    datas → ano/mês
                 soma de linhas repetidas              período coberto
                 tipos, ano/mês                        município de residência ignorado
                 código IBGE (UF + nome)               raça/cor
                 pivot → município × mês               agregação → município × mês
                        │                                     │
RELACIONAMENTO          └──── código IBGE 6 dígitos + ano + mês (FULL OUTER JOIN) ────┘
                                              │
                         cobertura do SIM · remoção de linhas sem ocorrência
                                              │
VALIDAÇÃO                         13 verificações (chave, nulos, totais...)
                                              │
CARGA                  data/processed/violencia_feminicidio_municipio_mes_2025.csv
```

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

## Validação

Antes de gravar o CSV, `etl/validate.py` verifica:

- o resultado não está vazio;
- a chave `codigo_ibge + ano + mes` é única;
- não há nulos nas colunas de identificação;
- `codigo_ibge` tem 7 dígitos, `uf` tem 2 letras maiúsculas e `mes` está entre 1 e 12;
- não há contagens negativas;
- as colunas do SIM não têm nulos nos meses cobertos e são nulas nos meses não cobertos;
- em cada evento do Sinesp, vítimas femininas ≤ total de vítimas;
- a soma por raça/cor é igual ao total de óbitos do SIM;
- o total de vítimas do Sinesp e o total de óbitos do SIM são os mesmos antes e depois do relacionamento.

Além disso, cada etapa de transformação confere que as agregações não alteraram os totais.

## Resultado

Execução com as bases descritas acima:

| Etapa | Registros |
|---|---|
| **Sinesp** — original | 832.293 |
| Sinesp — após recorte dos 6 eventos | 405.381 |
| Sinesp — após remover município "NÃO INFORMADO" e somar linhas repetidas | 401.040 |
| Sinesp — tratado (município × mês) | **66.840** (5.570 municípios × 12 meses; 72.605 vítimas) |
| **SIM** — original | 937.033 |
| SIM — após recorte (mulheres, X85–Y09) | 1.842 |
| SIM — após remover município de residência ignorado | 1.836 óbitos |
| SIM — tratado (município × mês) | **1.494** (983 municípios) |
| Relacionamento — registros presentes nas duas bases | 1.494 |
| Relacionamento — só no Sinesp (sem óbito no SIM) / só no SIM | 65.346 / 0 |
| Linhas sem nenhuma ocorrência removidas | 45.483 |
| **CSV final** | **21.357 linhas · 25 colunas · 4.490 municípios** |

Totais no CSV final: 1.566 vítimas de feminicídio (Sinesp, jan–dez) e 1.836 óbitos femininos por agressão (SIM, jan–ago), sendo 1.087 de mulheres pardas, 556 brancas, 145 pretas, 34 indígenas, 1 amarela e 13 com raça/cor ignorada.

## Dicionário de dados — CSV final

Arquivo: `data/processed/violencia_feminicidio_municipio_mes_2025.csv` · UTF-8 · separador `,` · cabeçalho na primeira linha · valor vazio = nulo.

**Granularidade:** uma linha por município × mês. **Chave:** `codigo_ibge + ano + mes`.

| Coluna | Tipo | Origem | Descrição |
|---|---|---|---|
| `codigo_ibge` | texto (7 dígitos) | Referência IBGE | Código IBGE do município |
| `uf` | texto (2) | Sinesp | Sigla da UF |
| `municipio` | texto | Referência IBGE | Nome oficial do município |
| `ano` | inteiro | Sinesp / SIM | Ano de referência (2025) |
| `mes` | inteiro (1–12) | Sinesp / SIM | Mês de referência |
| `sinesp_feminicidio_fem` | inteiro | Sinesp | Vítimas do sexo feminino de feminicídio |
| `sinesp_feminicidio_total` | inteiro | Sinesp | Total de vítimas de feminicídio |
| `sinesp_tentativa_feminicidio_fem` | inteiro | Sinesp | Vítimas femininas de tentativa de feminicídio |
| `sinesp_tentativa_feminicidio_total` | inteiro | Sinesp | Total de vítimas de tentativa de feminicídio |
| `sinesp_homicidio_doloso_fem` | inteiro | Sinesp | Vítimas femininas de homicídio doloso |
| `sinesp_homicidio_doloso_total` | inteiro | Sinesp | Total de vítimas de homicídio doloso |
| `sinesp_tentativa_homicidio_fem` | inteiro | Sinesp | Vítimas femininas de tentativa de homicídio |
| `sinesp_tentativa_homicidio_total` | inteiro | Sinesp | Total de vítimas de tentativa de homicídio |
| `sinesp_lesao_corporal_morte_fem` | inteiro | Sinesp | Vítimas femininas de lesão corporal seguida de morte |
| `sinesp_lesao_corporal_morte_total` | inteiro | Sinesp | Total de vítimas de lesão corporal seguida de morte |
| `sinesp_latrocinio_fem` | inteiro | Sinesp | Vítimas femininas de latrocínio |
| `sinesp_latrocinio_total` | inteiro | Sinesp | Total de vítimas de latrocínio |
| `sim_periodo_coberto` | booleano | ETL | `True` se o SIM tem dados para o mês (jan–ago/2025) |
| `sim_obitos_fem_agressao` | inteiro (nulo fora do período) | SIM | Óbitos de mulheres com causa básica X85–Y09, por município de residência |
| `sim_obitos_fem_branca` | inteiro (nulo fora do período) | SIM | Idem, raça/cor branca |
| `sim_obitos_fem_preta` | inteiro (nulo fora do período) | SIM | Idem, raça/cor preta |
| `sim_obitos_fem_amarela` | inteiro (nulo fora do período) | SIM | Idem, raça/cor amarela |
| `sim_obitos_fem_parda` | inteiro (nulo fora do período) | SIM | Idem, raça/cor parda |
| `sim_obitos_fem_indigena` | inteiro (nulo fora do período) | SIM | Idem, raça/cor indígena |
| `sim_obitos_fem_ignorada` | inteiro (nulo fora do período) | SIM | Idem, raça/cor não informada |

Regras de leitura: valor `0` significa "nenhum caso registrado"; valor vazio significa "sem dado" (meses não cobertos pelo SIM). Municípios × meses sem nenhuma ocorrência em nenhuma das bases não aparecem no arquivo e devem ser lidos como zero.

## Limitações

- **Feminicídio × óbito por agressão:** o SIM não tem a categoria feminicídio. O óbito feminino por agressão (X85–Y09) inclui feminicídios e outros homicídios de mulheres, então a comparação com o Sinesp é aproximada e só faz sentido no agregado por município, não vítima a vítima.
- **SIM preliminar:** só há óbitos até 02/09/2025, e agosto está incompleto (cerca de metade do volume dos meses anteriores). Comparações entre as bases devem usar `sim_periodo_coberto = True` e considerar a subnotificação de agosto.
- **Residência × ocorrência:** o SIM é relacionado pelo município de **residência** (AI02), enquanto o Sinesp registra o local da ocorrência. Em 21,3% dos óbitos do recorte os dois municípios são diferentes.
- **Registros descartados por falta de município:** 7 vítimas do Sinesp (município "NÃO INFORMADO") e 6 óbitos do SIM (município de residência ignorado).
- **Eventos sem detalhe municipal:** Estupro e Estupro de vulnerável existem no Sinesp só por UF e não entram no cruzamento.
- **Perfil das vítimas:** com a granularidade município × mês, só raça/cor é preservada do SIM; idade, escolaridade, estado civil e local de ocorrência não estão no CSV final.
- **Distrito Federal:** o Sinesp traz várias linhas por mês para "BRASÍLIA" (provavelmente uma por região administrativa); elas foram somadas e não é possível separá-las.
- **Tabela de municípios:** vem de um repositório público mantido pela comunidade, não diretamente do IBGE. Alguns nomes incluem a denominação alternativa entre parênteses (ex.: "Augusto Severo (Campo Grande)").

## Próxima etapa: PostgreSQL / Aiven

O CSV já está no formato esperado pelo `COPY ... FROM ... WITH (FORMAT csv, HEADER true)` do PostgreSQL: UTF-8, cabeçalho, nulos como campo vazio e booleanos como `True`/`False`. O schema (tabelas, tipos e o modelo estrela previsto na AI02) será definido na próxima etapa a partir do dicionário de dados acima. Nenhuma credencial ou conexão foi implementada nesta etapa; quando houver, as credenciais devem ficar em `.env` (já ignorado pelo Git).
