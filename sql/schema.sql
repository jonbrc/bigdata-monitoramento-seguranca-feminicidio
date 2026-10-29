-- =============================================================================
-- Monitoramento de Segurança Pública e Feminicídio Interseccional
-- Schema do banco (PostgreSQL / Aiven) — modelo estrela, com a hierarquia
-- geográfica normalizada (município → UF)
--
-- Origem dos dados: data/processed/violencia_feminicidio_municipio_mes_2025.csv
-- (formato largo, uma linha por município × mês) e data/reference/*.csv.
-- Na carga, as colunas do CSV viram linhas (formato longo) nas tabelas fato.
--
-- Granularidades:
--   fato_ocorrencia_sinesp  município × mês × evento    (Sinesp VDE 2025)
--   fato_obito_sim_raca     município × mês × raça/cor  (SIM 2025)
--   fato_obito_sim_faixa    município × mês × faixa     (SIM 2025)
--   fato_populacao          município × raça/cor        (Censo 2022)
--
-- Raça/cor e faixa etária do SIM ficam em fatos separados porque o CSV tratado
-- traz as duas contagens separadas (não cruzadas): não é possível filtrar por
-- raça E faixa ao mesmo tempo com os dados atuais.
--
-- Convenções:
--   * Fatos esparsos: só são gravadas combinações com pelo menos um caso.
--     Ausência de linha = 0 casos.
--   * Exceção: nos meses fora da cobertura do SIM (dim_tempo.sim_periodo_coberto
--     = FALSE), ausência de linha nos fatos do SIM significa "sem dado" (NULL no
--     CSV), não zero.
--   * Nenhum dado pessoal: o menor nível de detalhe é município × mês (LGPD).
--
-- Execução: psql "<URI do serviço>" -f sql/schema.sql   (recria o schema "dw")
-- =============================================================================

DROP SCHEMA IF EXISTS dw CASCADE;
CREATE SCHEMA dw;
SET search_path TO dw;

-- -----------------------------------------------------------------------------
-- DIMENSÕES
-- -----------------------------------------------------------------------------

-- Hierarquia geográfica: Região → UF → Município (drill-down do dashboard)
CREATE TABLE dim_uf (
    sigla_uf    CHAR(2)     PRIMARY KEY,                -- CSV: uf
    codigo_uf   SMALLINT    NOT NULL UNIQUE,            -- 2 primeiros dígitos do código IBGE
    nome_uf     VARCHAR(30) NOT NULL,
    regiao      VARCHAR(12) NOT NULL                    -- CSV: regiao
        CHECK (regiao IN ('Norte', 'Nordeste', 'Sudeste', 'Sul', 'Centro-Oeste'))
);

-- Carregada de data/reference/municipios_ibge.csv (todos os municípios)
CREATE TABLE dim_municipio (
    codigo_ibge    CHAR(7)      PRIMARY KEY,            -- CSV: codigo_ibge
    codigo_ibge_6  CHAR(6)      NOT NULL UNIQUE,        -- código usado pelo SIM (CODMUNRES)
    nome           VARCHAR(80)  NOT NULL,               -- CSV: municipio
    sigla_uf       CHAR(2)      NOT NULL REFERENCES dim_uf (sigla_uf),
    capital        BOOLEAN      NOT NULL DEFAULT FALSE,
    latitude       NUMERIC(8,5),                        -- para mapas no dashboard
    longitude      NUMERIC(8,5),
    CHECK (codigo_ibge ~ '^[0-9]{7}$'),
    CHECK (codigo_ibge_6 = LEFT(codigo_ibge, 6))
);
CREATE INDEX ix_dim_municipio_uf ON dim_municipio (sigla_uf);

CREATE TABLE dim_tempo (
    id_tempo             INTEGER     PRIMARY KEY,       -- AAAAMM, ex.: 202503
    ano                  SMALLINT    NOT NULL,          -- CSV: ano
    mes                  SMALLINT    NOT NULL CHECK (mes BETWEEN 1 AND 12),  -- CSV: mes
    nome_mes             VARCHAR(10) NOT NULL,
    trimestre            SMALLINT    NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    semestre             SMALLINT    NOT NULL CHECK (semestre IN (1, 2)),
    data_inicio          DATE        NOT NULL,
    sim_periodo_coberto  BOOLEAN     NOT NULL,          -- CSV: sim_periodo_coberto (jan–ago/2025)
    UNIQUE (ano, mes),
    CHECK (id_tempo = ano * 100 + mes)
);

-- Eventos do Sinesp (codigo = <evento> nas colunas sinesp_<evento>_fem/_total)
CREATE TABLE dim_evento (
    id_evento          SMALLINT    PRIMARY KEY,
    codigo             VARCHAR(30) NOT NULL UNIQUE,
    descricao          VARCHAR(60) NOT NULL,            -- nome original no Sinesp
    tipo               VARCHAR(10) NOT NULL CHECK (tipo IN ('consumado', 'tentativa')),
    violencia_genero   BOOLEAN     NOT NULL             -- TRUE para feminicídio e tentativa
);

-- codigo = <raça> nas colunas sim_obitos_fem_<raça> e pop_fem_<raça>
CREATE TABLE dim_raca_cor (
    id_raca_cor   SMALLINT    PRIMARY KEY,              -- mesmo código do SIM/IBGE (1–5); 9 = ignorada
    codigo        VARCHAR(15) NOT NULL UNIQUE,
    descricao     VARCHAR(15) NOT NULL,
    grupo         VARCHAR(15) NOT NULL,                 -- 'Negra' = preta + parda (IBGE / Estatuto da Igualdade Racial)
    ordem         SMALLINT    NOT NULL
);

-- codigo = <faixa> nas colunas sim_obitos_fem_<faixa>
CREATE TABLE dim_faixa_etaria (
    id_faixa_etaria  SMALLINT    PRIMARY KEY,
    codigo           VARCHAR(20) NOT NULL UNIQUE,
    descricao        VARCHAR(20) NOT NULL,
    idade_min        SMALLINT,                          -- NULL na faixa "ignorada"
    idade_max        SMALLINT,                          -- NULL = sem limite superior (60+) ou ignorada
    ordem            SMALLINT    NOT NULL
);

-- -----------------------------------------------------------------------------
-- FATOS
-- -----------------------------------------------------------------------------

-- Sinesp VDE: vítimas por município (local da ocorrência) × mês × evento.
-- CSV: sinesp_<evento>_fem → vitimas_fem; sinesp_<evento>_total → vitimas_total.
-- O Sinesp não informa raça/cor nem idade das vítimas no nível municipal.
CREATE TABLE fato_ocorrencia_sinesp (
    codigo_ibge    CHAR(7)   NOT NULL REFERENCES dim_municipio (codigo_ibge),
    id_tempo       INTEGER   NOT NULL REFERENCES dim_tempo (id_tempo),
    id_evento      SMALLINT  NOT NULL REFERENCES dim_evento (id_evento),
    vitimas_fem    INTEGER   NOT NULL CHECK (vitimas_fem >= 0),
    vitimas_total  INTEGER   NOT NULL CHECK (vitimas_total > 0),
    PRIMARY KEY (codigo_ibge, id_tempo, id_evento),
    CHECK (vitimas_fem <= vitimas_total)
);
CREATE INDEX ix_fato_sinesp_tempo  ON fato_ocorrencia_sinesp (id_tempo);
CREATE INDEX ix_fato_sinesp_evento ON fato_ocorrencia_sinesp (id_evento);

-- SIM: óbitos de mulheres por agressão (CID-10 X85–Y09), por município de
-- residência × mês × raça/cor. CSV: sim_obitos_fem_<raça>.
-- SUM(obitos) por município × mês = sim_obitos_fem_agressao.
CREATE TABLE fato_obito_sim_raca (
    codigo_ibge   CHAR(7)   NOT NULL REFERENCES dim_municipio (codigo_ibge),
    id_tempo      INTEGER   NOT NULL REFERENCES dim_tempo (id_tempo),
    id_raca_cor   SMALLINT  NOT NULL REFERENCES dim_raca_cor (id_raca_cor),
    obitos        INTEGER   NOT NULL CHECK (obitos > 0),
    PRIMARY KEY (codigo_ibge, id_tempo, id_raca_cor)
);
CREATE INDEX ix_fato_sim_raca_tempo ON fato_obito_sim_raca (id_tempo);

-- SIM: mesmos óbitos, por município de residência × mês × faixa etária.
-- CSV: sim_obitos_fem_idade_<faixa>. SUM(obitos) = sim_obitos_fem_agressao.
CREATE TABLE fato_obito_sim_faixa (
    codigo_ibge      CHAR(7)   NOT NULL REFERENCES dim_municipio (codigo_ibge),
    id_tempo         INTEGER   NOT NULL REFERENCES dim_tempo (id_tempo),
    id_faixa_etaria  SMALLINT  NOT NULL REFERENCES dim_faixa_etaria (id_faixa_etaria),
    obitos           INTEGER   NOT NULL CHECK (obitos > 0),
    PRIMARY KEY (codigo_ibge, id_tempo, id_faixa_etaria)
);
CREATE INDEX ix_fato_sim_faixa_tempo ON fato_obito_sim_faixa (id_tempo);

-- Censo 2022: população feminina por município × raça/cor (denominador das taxas).
-- Carregada de data/reference/populacao_feminina_censo2022.csv, com TODOS os
-- 5.570 municípios (o CSV tratado não tem os municípios sem ocorrência), para que
-- taxas por UF/região/Brasil usem o denominador completo. Raça "ignorada" =
-- pop_fem_total − soma das cinco categorias, então SUM(pop_fem) por município =
-- pop_fem_total. Por ser uma tabela própria, a população não se repete por mês.
CREATE TABLE fato_populacao (
    codigo_ibge   CHAR(7)   NOT NULL REFERENCES dim_municipio (codigo_ibge),
    id_raca_cor   SMALLINT  NOT NULL REFERENCES dim_raca_cor (id_raca_cor),
    ano_censo     SMALLINT  NOT NULL DEFAULT 2022,
    pop_fem       INTEGER   NOT NULL CHECK (pop_fem >= 0),
    PRIMARY KEY (codigo_ibge, id_raca_cor, ano_censo)
);

-- -----------------------------------------------------------------------------
-- DADOS FIXOS DAS DIMENSÕES PEQUENAS
-- (dim_municipio e dim_tempo são carregadas a partir dos arquivos)
-- -----------------------------------------------------------------------------

INSERT INTO dim_uf (sigla_uf, codigo_uf, nome_uf, regiao) VALUES
    ('RO', 11, 'Rondônia', 'Norte'),            ('AC', 12, 'Acre', 'Norte'),
    ('AM', 13, 'Amazonas', 'Norte'),            ('RR', 14, 'Roraima', 'Norte'),
    ('PA', 15, 'Pará', 'Norte'),                ('AP', 16, 'Amapá', 'Norte'),
    ('TO', 17, 'Tocantins', 'Norte'),
    ('MA', 21, 'Maranhão', 'Nordeste'),         ('PI', 22, 'Piauí', 'Nordeste'),
    ('CE', 23, 'Ceará', 'Nordeste'),            ('RN', 24, 'Rio Grande do Norte', 'Nordeste'),
    ('PB', 25, 'Paraíba', 'Nordeste'),          ('PE', 26, 'Pernambuco', 'Nordeste'),
    ('AL', 27, 'Alagoas', 'Nordeste'),          ('SE', 28, 'Sergipe', 'Nordeste'),
    ('BA', 29, 'Bahia', 'Nordeste'),
    ('MG', 31, 'Minas Gerais', 'Sudeste'),      ('ES', 32, 'Espírito Santo', 'Sudeste'),
    ('RJ', 33, 'Rio de Janeiro', 'Sudeste'),    ('SP', 35, 'São Paulo', 'Sudeste'),
    ('PR', 41, 'Paraná', 'Sul'),                ('SC', 42, 'Santa Catarina', 'Sul'),
    ('RS', 43, 'Rio Grande do Sul', 'Sul'),
    ('MS', 50, 'Mato Grosso do Sul', 'Centro-Oeste'), ('MT', 51, 'Mato Grosso', 'Centro-Oeste'),
    ('GO', 52, 'Goiás', 'Centro-Oeste'),        ('DF', 53, 'Distrito Federal', 'Centro-Oeste');

INSERT INTO dim_evento (id_evento, codigo, descricao, tipo, violencia_genero) VALUES
    (1, 'feminicidio',           'Feminicídio',                          'consumado', TRUE),
    (2, 'tentativa_feminicidio', 'Tentativa de feminicídio',             'tentativa', TRUE),
    (3, 'homicidio_doloso',      'Homicídio doloso',                     'consumado', FALSE),
    (4, 'tentativa_homicidio',   'Tentativa de homicídio',               'tentativa', FALSE),
    (5, 'lesao_corporal_morte',  'Lesão corporal seguida de morte',      'consumado', FALSE),
    (6, 'latrocinio',            'Roubo seguido de morte (latrocínio)',  'consumado', FALSE);

INSERT INTO dim_raca_cor (id_raca_cor, codigo, descricao, grupo, ordem) VALUES
    (1, 'branca',        'Branca',    'Branca',    1),
    (2, 'preta',         'Preta',     'Negra',     2),
    (3, 'amarela',       'Amarela',   'Amarela',   4),
    (4, 'parda',         'Parda',     'Negra',     3),
    (5, 'indigena',      'Indígena',  'Indígena',  5),
    (9, 'raca_ignorada', 'Ignorada',  'Ignorada',  9);

INSERT INTO dim_faixa_etaria (id_faixa_etaria, codigo, descricao, idade_min, idade_max, ordem) VALUES
    (1, 'idade_0_17',     '0 a 17 anos',  0,    17,   1),
    (2, 'idade_18_29',    '18 a 29 anos', 18,   29,   2),
    (3, 'idade_30_39',    '30 a 39 anos', 30,   39,   3),
    (4, 'idade_40_49',    '40 a 49 anos', 40,   49,   4),
    (5, 'idade_50_59',    '50 a 59 anos', 50,   59,   5),
    (6, 'idade_60_mais',  '60 anos ou +', 60,   NULL, 6),
    (9, 'idade_ignorada', 'Ignorada',     NULL, NULL, 9);

-- -----------------------------------------------------------------------------
-- VIEWS PARA O DASHBOARD
-- -----------------------------------------------------------------------------

-- Sinesp com todos os atributos de filtro resolvidos
CREATE VIEW vw_sinesp AS
SELECT u.regiao, u.sigla_uf, m.codigo_ibge, m.nome AS municipio,
       t.ano, t.mes, t.id_tempo, t.sim_periodo_coberto,
       e.codigo AS evento, e.descricao AS evento_descricao, e.tipo, e.violencia_genero,
       f.vitimas_fem, f.vitimas_total
FROM fato_ocorrencia_sinesp f
JOIN dim_municipio m USING (codigo_ibge)
JOIN dim_uf        u USING (sigla_uf)
JOIN dim_tempo     t USING (id_tempo)
JOIN dim_evento    e USING (id_evento);

-- SIM por raça/cor, com atributos de filtro
CREATE VIEW vw_sim_raca AS
SELECT u.regiao, u.sigla_uf, m.codigo_ibge, m.nome AS municipio,
       t.ano, t.mes, t.id_tempo,
       r.codigo AS raca_cor, r.descricao AS raca_cor_descricao, r.grupo AS grupo_racial,
       f.obitos
FROM fato_obito_sim_raca f
JOIN dim_municipio m USING (codigo_ibge)
JOIN dim_uf        u USING (sigla_uf)
JOIN dim_tempo     t USING (id_tempo)
JOIN dim_raca_cor  r USING (id_raca_cor);

-- SIM por faixa etária, com atributos de filtro
CREATE VIEW vw_sim_faixa AS
SELECT u.regiao, u.sigla_uf, m.codigo_ibge, m.nome AS municipio,
       t.ano, t.mes, t.id_tempo,
       fe.codigo AS faixa_etaria, fe.descricao AS faixa_etaria_descricao, fe.ordem AS faixa_ordem,
       f.obitos
FROM fato_obito_sim_faixa f
JOIN dim_municipio    m  USING (codigo_ibge)
JOIN dim_uf           u  USING (sigla_uf)
JOIN dim_tempo        t  USING (id_tempo)
JOIN dim_faixa_etaria fe USING (id_faixa_etaria);

-- Óbitos e população feminina por UF × raça/cor, no período coberto pelo SIM
-- (jan–ago/2025). Base das taxas por raça: para qualquer recorte (Brasil, região,
-- UF, grupo racial), some `obitos` e `pop_fem` e calcule
-- SUM(obitos) * 100000 / SUM(pop_fem). Nunca faça média de taxas.
-- Denominador completo: inclui os municípios sem nenhum óbito.
-- Raça ignorada entra nas somas, mas sua taxa fica NULL (no SIM é falta de
-- registro; no Censo é outra coisa; a razão entre as duas não tem significado).
CREATE VIEW vw_obitos_populacao_raca AS
WITH pop AS (
    SELECT m.sigla_uf, p.id_raca_cor, SUM(p.pop_fem) AS pop_fem
    FROM fato_populacao p JOIN dim_municipio m USING (codigo_ibge)
    GROUP BY m.sigla_uf, p.id_raca_cor
), obitos AS (
    SELECT m.sigla_uf, f.id_raca_cor, SUM(f.obitos) AS obitos
    FROM fato_obito_sim_raca f JOIN dim_municipio m USING (codigo_ibge)
    GROUP BY m.sigla_uf, f.id_raca_cor
)
SELECT u.regiao, u.sigla_uf,
       r.codigo AS raca_cor, r.descricao AS raca_cor_descricao, r.grupo AS grupo_racial,
       pop.pop_fem,
       COALESCE(o.obitos, 0) AS obitos,
       CASE WHEN r.codigo <> 'raca_ignorada'
            THEN ROUND(COALESCE(o.obitos, 0) * 100000.0 / NULLIF(pop.pop_fem, 0), 2)
       END AS taxa_100mil
FROM pop
JOIN dim_uf       u USING (sigla_uf)
JOIN dim_raca_cor r USING (id_raca_cor)
LEFT JOIN obitos  o ON o.sigla_uf = pop.sigla_uf AND o.id_raca_cor = pop.id_raca_cor;

-- Comparação Sinesp × SIM por município, só nos meses cobertos pelo SIM.
-- feminicidios_sinesp / obitos_fem_agressao_sim indica que parcela das mortes
-- violentas de mulheres foi registrada pela polícia como feminicídio.
CREATE VIEW vw_comparativo_sinesp_sim AS
WITH s AS (
    SELECT f.codigo_ibge,
           SUM(f.vitimas_fem) FILTER (WHERE e.codigo = 'feminicidio')           AS feminicidios,
           SUM(f.vitimas_fem) FILTER (WHERE e.codigo = 'tentativa_feminicidio') AS tentativas_feminicidio,
           SUM(f.vitimas_fem) FILTER (WHERE e.tipo = 'consumado')               AS mortes_violentas_fem
    FROM fato_ocorrencia_sinesp f
    JOIN dim_evento e USING (id_evento)
    JOIN dim_tempo  t USING (id_tempo)
    WHERE t.sim_periodo_coberto
    GROUP BY f.codigo_ibge
), o AS (
    SELECT codigo_ibge, SUM(obitos) AS obitos
    FROM fato_obito_sim_raca GROUP BY codigo_ibge
)
SELECT u.regiao, u.sigla_uf, m.codigo_ibge, m.nome AS municipio,
       COALESCE(s.feminicidios, 0)           AS feminicidios_sinesp,
       COALESCE(s.tentativas_feminicidio, 0) AS tentativas_feminicidio_sinesp,
       COALESCE(s.mortes_violentas_fem, 0)   AS mortes_violentas_fem_sinesp,
       COALESCE(o.obitos, 0)                 AS obitos_fem_agressao_sim
FROM dim_municipio m
JOIN dim_uf u USING (sigla_uf)
LEFT JOIN s ON s.codigo_ibge = m.codigo_ibge
LEFT JOIN o ON o.codigo_ibge = m.codigo_ibge
WHERE s.codigo_ibge IS NOT NULL OR o.codigo_ibge IS NOT NULL;
