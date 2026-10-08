# Análise exploratória das bases brutas

_Gerado automaticamente por `python -m etl.exploratory_analysis` em 2026-10-08 13:35._

## Tabela de referência — municípios IBGE

- Arquivo: `data/reference/municipios_ibge.csv`
- Municípios: 5.571; códigos duplicados: 0
- Código IBGE de 7 dígitos; os 6 primeiros correspondem ao código usado no SIM.

## Base 1 — Sinesp VDE 2025

- **Arquivo:** `BancoVDE 2025 (1).xlsx` (planilha Excel, aba `2025`)
- **Registros:** 832.293
- **Colunas:** 14

### Colunas, tipos e nulos

| coluna | tipo aparente | nulos | % nulos |
|---|---|---|---|
| uf | str | 0 | 0.0% |
| municipio | str | 0 | 0.0% |
| evento | str | 0 | 0.0% |
| data_referencia | datetime64[us] | 0 | 0.0% |
| agente | str | 826.461 | 99.3% |
| arma | str | 826.461 | 99.3% |
| faixa_etaria | str | 830.349 | 99.8% |
| feminino | float64 | 154.606 | 18.6% |
| masculino | float64 | 154.157 | 18.5% |
| nao_informado | float64 | 154.921 | 18.6% |
| total_vitima | float64 | 147.084 | 17.7% |
| total | float64 | 690.217 | 82.9% |
| total_peso | float64 | 831.105 | 99.9% |
| abrangencia | str | 0 | 0.0% |

### Período

- `data_referencia`: 2025-01-01 a 2025-12-01 (12 meses distintos; datas inválidas: 0)
- Granularidade mensal (sempre o dia 1 do mês).

### Eventos (31 tipos)

| evento | registros | abrangencias | linhas_municipio_nao_informado | soma_feminino | soma_total_vitima | soma_total |
|---|---|---|---|---|---|---|
| Apreensão de Cocaína | 648 | Estadual, Polícia Federal | 648 | 0 | 0 | 0 |
| Apreensão de Maconha | 648 | Estadual, Polícia Federal | 648 | 0 | 0 | 0 |
| Arma de Fogo Apreendida | 5.832 | Estadual, Polícia Federal | 5.832 | 0 | 0 | 110.360 |
| Atendimento pré-hospitalar | 324 | Estadual | 324 | 0 | 0 | 1.054.625 |
| Busca e salvamento | 324 | Estadual | 324 | 0 | 0 | 523.603 |
| Combate a incêndios | 324 | Estadual | 324 | 0 | 0 | 348.520 |
| Emissão de Alvarás de licença | 324 | Estadual | 324 | 0 | 0 | 1.770.049 |
| Estupro | 324 | Estadual | 324 | 18.251 | 19.909 | 0 |
| Estupro de vulnerável | 324 | Estadual | 324 | 53.732 | 63.690 | 0 |
| Feminicídio | 67.565 | Estadual | 341 | 1.566 | 1.578 | 0 |
| Furto de veículo | 648 | Estadual, Polícia Federal | 648 | 0 | 0 | 201.926 |
| Homicídio doloso | 67.565 | Estadual | 341 | 2.084 | 31.518 | 0 |
| Lesão corporal seguida de morte | 67.565 | Estadual | 341 | 54 | 644 | 0 |
| Mandado de prisão cumprido | 135.096 | Estadual, Polícia Federal | 648 | 0 | 0 | 297.651 |
| Morte de Agente do Estado | 2.916 | Estadual, Polícia Federal, Polícia Rodoviária Federal | 2.916 | 7 | 192 | 0 |
| Morte no trânsito ou em decorrência dele (exceto homicídio doloso) | 67.565 | Estadual | 341 | 4.817 | 25.074 | 0 |
| Morte por intervenção de Agente do Estado | 972 | Estadual, Polícia Federal, Polícia Rodoviária Federal | 972 | 45 | 6.601 | 0 |
| Mortes a esclarecer (sem indício de crime) | 67.565 | Estadual | 341 | 3.213 | 13.537 | 0 |
| Mortes no trânsito | 67.737 | Polícia Federal, Polícia Rodoviária Federal | 513 | 1.067 | 6.056 | 0 |
| Pessoa Desaparecida | 972 | Estadual | 972 | 30.081 | 85.066 | 0 |
| Pessoa Localizada | 972 | Estadual | 972 | 20.745 | 57.672 | 0 |
| Realização de vistorias | 324 | Estadual | 324 | 0 | 0 | 760.400 |
| Roubo a instituição financeira | 648 | Estadual, Polícia Federal | 648 | 0 | 0 | 60 |
| Roubo de carga | 648 | Estadual, Polícia Federal | 648 | 0 | 0 | 8.565 |
| Roubo de veículo | 648 | Estadual, Polícia Federal | 648 | 0 | 0 | 104.534 |
| Roubo seguido de morte (latrocínio) | 67.565 | Estadual | 341 | 83 | 803 | 0 |
| Suicídio | 67.565 | Estadual | 341 | 3.615 | 16.592 | 0 |
| Suicídio de Agente do Estado | 2.916 | Estadual, Polícia Federal, Polícia Rodoviária Federal | 2.916 | 7 | 138 | 0 |
| Tentativa de feminicídio | 67.556 | Estadual | 332 | 4.140 | 4.188 | 0 |
| Tentativa de homicídio | 67.565 | Estadual | 341 | 4.778 | 33.881 | 0 |
| Tráfico de drogas | 648 | Estadual, Polícia Federal | 648 | 0 | 0 | 219.763 |

Observações:
- Eventos com vítimas usam `feminino`/`masculino`/`nao_informado`/`total_vitima`; eventos sem vítimas (apreensões, mandados etc.) usam `total` ou `total_peso`.
- Eventos em que todas as linhas têm município `NÃO INFORMADO` só existem no nível estadual e não podem ser cruzados por município.

### Medidas numéricas

- Valores negativos: {'feminino': 0, 'masculino': 0, 'nao_informado': 0, 'total_vitima': 0, 'total': 0}
- Valores não inteiros: {'feminino': 0, 'masculino': 0, 'nao_informado': 0, 'total_vitima': 0, 'total': 0}
- Linhas com `total_vitima` = 0: 618.365 (74.3%) — linhas sem ocorrência.

### Duplicidades

- Linhas idênticas (todas as colunas): 4.078 excedentes
- Linhas repetidas na chave lógica `uf + municipio + evento + data_referencia + agente + arma + faixa_etaria + abrangencia`: 4.752 excedentes (ou seja, 674 com mesma chave e medidas diferentes)

Municípios com chave repetida:

| uf | municipio | linhas |
|---|---|---|
| DF | BRASÍLIA | 4.752 |
| AM | NÃO INFORMADO | 34 |
| BA | NÃO INFORMADO | 34 |
| GO | NÃO INFORMADO | 34 |
| PE | NÃO INFORMADO | 34 |
| RN | NÃO INFORMADO | 34 |
| RJ | NÃO INFORMADO | 34 |
| RS | NÃO INFORMADO | 34 |
| MT | NÃO INFORMADO | 18 |
| DF | NÃO INFORMADO | 16 |

- Exemplo: `DF/BRASÍLIA` tem 33 linhas por mês para o evento Feminicídio — provavelmente uma por região administrativa (o DF tem 33), todas com o mesmo nome de município.

### Município, UF, texto e encoding

- UFs: 27 (fora do padrão: nenhuma)
- Pares UF + município distintos: 5.597 (5.570 sem contar `NÃO INFORMADO`)
- Linhas com município `NÃO INFORMADO`: 25.605
- Nomes de município que se repetem em UFs diferentes: 505 pares → o nome sozinho **não** é chave; é preciso UF + município.
- **Não há código IBGE** na base; o município é identificado só por UF + nome.
- Nomes com espaços nas pontas: 0
- Nomes fora de maiúsculas: 0
- Indícios de problema de encoding (mojibake): 0

### Compatibilidade com a tabela de municípios IBGE

Comparação por UF + nome normalizado (sem acento, maiúsculas, sem hífen/apóstrofo):

- Municípios do Sinesp: 5.570
- Encontrados na tabela IBGE: 5.560
- Sem correspondência: 10

| uf | municipio |
|---|---|
| BA | MUQUÉM DO SÃO FRANCISCO |
| BA | SANTA TEREZINHA |
| MG | DONA EUZÉBIA |
| MG | SÃO TOMÉ DAS LETRAS |
| PE | SÃO CAITANO |
| RN | CAMPO GRANDE |
| RN | JANUÁRIO CICCO |
| SE | AMPARO DO SÃO FRANCISCO |
| SP | FLORÍNEA |
| TO | TABOCÃO |

Os casos sem correspondência são grafias diferentes do mesmo município (nome antigo ou variante) e precisam de um mapeamento explícito.

## Base 2 — SIM 2025 (preliminar)

- **Arquivo:** `Mortalidade_Geral_2025.csv` (CSV, separador `;`, lido como `latin-1`)
- **Registros:** 937.033
- **Colunas:** 86
- Todas as colunas lidas como texto (são códigos; ver `etl/extract.py`).

### Nulos por coluna (base inteira)

<details><summary>Todas as colunas</summary>

| coluna | tipo aparente | nulos | % nulos |
|---|---|---|---|
| contador | texto/código | 0 | 0.0% |
| ORIGEM | texto/código | 0 | 0.0% |
| TIPOBITO | texto/código | 0 | 0.0% |
| DTOBITO | texto/código | 0 | 0.0% |
| HORAOBITO | texto/código | 28.276 | 3.0% |
| NATURAL | texto/código | 34.102 | 3.6% |
| CODMUNNATU | texto/código | 45.578 | 4.9% |
| DTNASC | texto/código | 1.381 | 0.1% |
| IDADE | texto/código | 7 | 0.0% |
| SEXO | texto/código | 0 | 0.0% |
| RACACOR | texto/código | 12.322 | 1.3% |
| ESTCIV | texto/código | 37.539 | 4.0% |
| ESC | texto/código | 48.373 | 5.2% |
| ESC2010 | texto/código | 56.092 | 6.0% |
| SERIESCFAL | texto/código | 652.702 | 69.7% |
| OCUP | texto/código | 117.941 | 12.6% |
| CODMUNRES | texto/código | 0 | 0.0% |
| LOCOCOR | texto/código | 0 | 0.0% |
| CODESTAB | texto/código | 242.672 | 25.9% |
| CODMUNOCOR | texto/código | 0 | 0.0% |
| IDADEMAE | texto/código | 919.861 | 98.2% |
| ESCMAE | texto/código | 920.089 | 98.2% |
| ESCMAE2010 | texto/código | 920.280 | 98.2% |
| SERIESCMAE | texto/código | 929.898 | 99.2% |
| OCUPMAE | texto/código | 921.587 | 98.4% |
| QTDFILVIVO | texto/código | 919.944 | 98.2% |
| QTDFILMORT | texto/código | 920.492 | 98.2% |
| GRAVIDEZ | texto/código | 919.491 | 98.1% |
| SEMAGESTAC | texto/código | 920.272 | 98.2% |
| GESTACAO | texto/código | 920.272 | 98.2% |
| PARTO | texto/código | 919.606 | 98.1% |
| OBITOPARTO | texto/código | 919.746 | 98.2% |
| PESO | texto/código | 920.208 | 98.2% |
| TPMORTEOCO | texto/código | 886.615 | 94.6% |
| OBITOGRAV | texto/código | 886.187 | 94.6% |
| OBITOPUERP | texto/código | 886.199 | 94.6% |
| ASSISTMED | texto/código | 422.679 | 45.1% |
| EXAME | texto/código | 933.104 | 99.6% |
| CIRURGIA | texto/código | 934.253 | 99.7% |
| NECROPSIA | texto/código | 407.107 | 43.4% |
| LINHAA | texto/código | 21.283 | 2.3% |
| LINHAB | texto/código | 217.091 | 23.2% |
| LINHAC | texto/código | 490.652 | 52.4% |
| LINHAD | texto/código | 749.514 | 80.0% |
| LINHAII | texto/código | 537.381 | 57.3% |
| CAUSABAS | texto/código | 0 | 0.0% |
| CB_PRE | texto/código | 937.033 | 100.0% |
| COMUNSVOIM | texto/código | 803.068 | 85.7% |
| DTATESTADO | texto/código | 184.417 | 19.7% |
| CIRCOBITO | texto/código | 862.912 | 92.1% |
| ACIDTRAB | texto/código | 911.504 | 97.3% |
| FONTE | texto/código | 878.559 | 93.8% |
| NUMEROLOTE | texto/código | 181.937 | 19.4% |
| DTINVESTIG | texto/código | 846.189 | 90.3% |
| DTCADASTRO | texto/código | 264 | 0.0% |
| ATESTANTE | texto/código | 229.634 | 24.5% |
| STCODIFICA | texto/código | 182.435 | 19.5% |
| CODIFICADO | texto/código | 181.937 | 19.4% |
| VERSAOSIST | texto/código | 181.937 | 19.4% |
| VERSAOSCB | texto/código | 195.165 | 20.8% |
| FONTEINV | texto/código | 844.986 | 90.2% |
| DTRECEBIM | texto/código | 379 | 0.0% |
| ATESTADO | texto/código | 0 | 0.0% |
| DTRECORIGA | texto/código | 0 | 0.0% |
| OPOR_DO | texto/código | 0 | 0.0% |
| CAUSAMAT | texto/código | 937.026 | 100.0% |
| ESCMAEAGR1 | texto/código | 920.280 | 98.2% |
| ESCFALAGR1 | texto/código | 56.092 | 6.0% |
| STDOEPIDEM | texto/código | 181.937 | 19.4% |
| STDONOVA | texto/código | 0 | 0.0% |
| DIFDATA | texto/código | 0 | 0.0% |
| NUDIASOBCO | texto/código | 911.459 | 97.3% |
| DTCADINV | texto/código | 908.498 | 97.0% |
| TPOBITOCOR | texto/código | 908.498 | 97.0% |
| DTCONINV | texto/código | 908.666 | 97.0% |
| FONTES | texto/código | 925.182 | 98.7% |
| TPRESGINFO | texto/código | 936.011 | 99.9% |
| TPNIVELINV | texto/código | 911.313 | 97.3% |
| DTCADINF | texto/código | 925.170 | 98.7% |
| MORTEPARTO | texto/código | 925.170 | 98.7% |
| DTCONCASO | texto/código | 926.292 | 98.9% |
| ALTCAUSA | texto/código | 937.033 | 100.0% |
| CAUSABAS_O | texto/código | 1.567 | 0.2% |
| TPPOS | texto/código | 321.578 | 34.3% |
| TP_ALTERA | texto/código | 926.902 | 98.9% |
| CB_ALT | texto/código | 932.458 | 99.5% |

</details>

### Duplicidades e chaves

- `contador` repetido: 0 → `contador` identifica a linha.
- Linhas idênticas ignorando `contador`: 12
- Cada linha é uma declaração de óbito; não há identificador da pessoa (o que é coerente com a LGPD).

### Período

- `DTOBITO` (formato `ddmmaaaa`): 2025-01-01 a 2025-09-02; datas inválidas: 0
- Óbitos por mês:

| mês | óbitos |
|---|---|
| 2025-01 | 123.614 |
| 2025-02 | 110.983 |
| 2025-03 | 121.914 |
| 2025-04 | 121.365 |
| 2025-05 | 139.494 |
| 2025-06 | 137.783 |
| 2025-07 | 125.685 |
| 2025-08 | 56.140 |
| 2025-09 | 55 |

Base **preliminar**: a cobertura cai a partir de agosto e não há óbitos depois de setembro/2025, enquanto o Sinesp cobre janeiro a dezembro.

### Formatação e consistência

- `SEXO`: {'0': '288', '1': '509.979', '2': '426.766'} (1 = masculino, 2 = feminino, 0 = ignorado)
- `CAUSABAS` com `*`: 0; tamanhos: {3: '134.704', 4: '802.329'}
- Valores não numéricos em campos de código: {'CODMUNRES': 0, 'CODMUNOCOR': 0, 'SEXO': 0, 'RACACOR': 0}
- O arquivo contém apenas caracteres ASCII; não há texto acentuado e, portanto, não há risco de problema de encoding.

### Recorte do tema (AI02): mulheres, causa básica X85–Y09

- Registros no recorte: **1.842** (0.20% da base)
- Duplicidades no recorte (ignorando `contador`): 0
- Categorias CID mais frequentes: {'X95': 763, 'X99': 526, 'Y00': 133, 'X91': 103, 'X93': 98, 'Y09': 68, 'Y04': 67, 'X97': 29}

Nulos nos campos mapeados na AI02 (dentro do recorte):

| coluna | tipo aparente | nulos | % nulos |
|---|---|---|---|
| DTOBITO | texto/código | 0 | 0.0% |
| SEXO | texto/código | 0 | 0.0% |
| CAUSABAS | texto/código | 0 | 0.0% |
| CODMUNRES | texto/código | 0 | 0.0% |
| CODMUNOCOR | texto/código | 0 | 0.0% |
| RACACOR | texto/código | 16 | 0.9% |
| IDADE | texto/código | 0 | 0.0% |
| ESTCIV | texto/código | 80 | 4.3% |
| ESC2010 | texto/código | 122 | 6.6% |
| LOCOCOR | texto/código | 0 | 0.0% |
| CODESTAB | texto/código | 1.402 | 76.1% |
| NATURAL | texto/código | 37 | 2.0% |
| CODMUNNATU | texto/código | 47 | 2.6% |
| TIPOBITO | texto/código | 0 | 0.0% |

Distribuição das categorias interseccionais (dentro do recorte):

- `RACACOR`: 4=1089, 1=556, 2=146, 5=34, nulo=16, 3=1
- `ESC2010`: 2=586, 3=494, 1=255, 9=192, nulo=122, 5=82, 0=78, 4=33
- `ESTCIV`: 1=1179, 2=215, 5=114, 9=108, 4=91, nulo=80, 3=55
- `LOCOCOR`: 3=551, 4=480, 1=393, 5=366, 2=47, 9=3, 6=2
- `CIRCOBITO`: 3=1458, nulo=283, 9=70, 1=31
- `IDADE` — 1º dígito (unidade: 0/1 min/h, 2 dias, 3 meses, 4 anos, 5 anos+100, 9 ignorado): 0=6, 1=1, 2=1, 3=10, 4=1818, 9=6

### Códigos de município

- Tamanho de `CODMUNRES`: {6: 1842}; `CODMUNOCOR`: {6: 1842} → código IBGE de **6 dígitos** (sem dígito verificador).
- `CODMUNRES` terminado em `0000` (município ignorado, só UF): 6
- `CODMUNRES` fora da tabela IBGE: 6; `CODMUNOCOR` fora da tabela IBGE: 0
- Óbitos com município de residência ≠ município de ocorrência: 393 (21.3%)
