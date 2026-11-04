-- Schema "dw" (PostgreSQL / Aiven) em modelo estrela: dimensões, fatos do Sinesp, do SIM e da população do Censo 2022, e views de KPIs para o dashboard. Recriado do zero a cada carga (etl/load.py).

DROP SCHEMA IF EXISTS dw CASCADE;
CREATE SCHEMA dw;
SET search_path TO dw;

CREATE TABLE dim_uf (
    sigla_uf    CHAR(2)     PRIMARY KEY,
    codigo_uf   SMALLINT    NOT NULL UNIQUE,
    nome_uf     VARCHAR(30) NOT NULL,
    regiao      VARCHAR(12) NOT NULL
        CHECK (regiao IN ('Norte', 'Nordeste', 'Sudeste', 'Sul', 'Centro-Oeste'))
);

CREATE TABLE dim_municipio (
    codigo_ibge    CHAR(7)      PRIMARY KEY,
    codigo_ibge_6  CHAR(6)      NOT NULL UNIQUE,
    nome           VARCHAR(80)  NOT NULL,
    sigla_uf       CHAR(2)      NOT NULL REFERENCES dim_uf (sigla_uf),
    capital        BOOLEAN      NOT NULL DEFAULT FALSE,
    latitude       NUMERIC(8,5),
    longitude      NUMERIC(8,5),
    CHECK (codigo_ibge ~ '^[0-9]{7}$'),
    CHECK (codigo_ibge_6 = LEFT(codigo_ibge, 6))
);
CREATE INDEX ix_dim_municipio_uf ON dim_municipio (sigla_uf);

CREATE TABLE dim_tempo (
    id_tempo             INTEGER     PRIMARY KEY,
    ano                  SMALLINT    NOT NULL,
    mes                  SMALLINT    NOT NULL CHECK (mes BETWEEN 1 AND 12),
    nome_mes             VARCHAR(10) NOT NULL,
    trimestre            SMALLINT    NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    semestre             SMALLINT    NOT NULL CHECK (semestre IN (1, 2)),
    data_inicio          DATE        NOT NULL,
    sim_periodo_coberto  BOOLEAN     NOT NULL,
    UNIQUE (ano, mes),
    CHECK (id_tempo = ano * 100 + mes)
);

CREATE TABLE dim_evento (
    id_evento          SMALLINT    PRIMARY KEY,
    codigo             VARCHAR(30) NOT NULL UNIQUE,
    descricao          VARCHAR(60) NOT NULL,
    tipo               VARCHAR(10) NOT NULL CHECK (tipo IN ('consumado', 'tentativa')),
    violencia_genero   BOOLEAN     NOT NULL
);

CREATE TABLE dim_sexo (
    id_sexo    SMALLINT    PRIMARY KEY,
    codigo     VARCHAR(10) NOT NULL UNIQUE,
    descricao  VARCHAR(10) NOT NULL
);

CREATE TABLE dim_raca_cor (
    id_raca_cor   SMALLINT    PRIMARY KEY,
    codigo        VARCHAR(15) NOT NULL UNIQUE,
    descricao     VARCHAR(15) NOT NULL,
    grupo         VARCHAR(15) NOT NULL,
    ordem         SMALLINT    NOT NULL
);

CREATE TABLE dim_faixa_etaria (
    id_faixa_etaria  SMALLINT    PRIMARY KEY,
    codigo           VARCHAR(20) NOT NULL UNIQUE,
    descricao        VARCHAR(20) NOT NULL,
    idade_min        SMALLINT,
    idade_max        SMALLINT,
    ordem            SMALLINT    NOT NULL
);

CREATE TABLE dim_local_obito (
    id_local_obito  SMALLINT    PRIMARY KEY,
    codigo          VARCHAR(25) NOT NULL UNIQUE,
    descricao       VARCHAR(30) NOT NULL,
    ordem           SMALLINT    NOT NULL
);

CREATE TABLE dim_meio_agressao (
    id_meio_agressao  SMALLINT    PRIMARY KEY,
    codigo            VARCHAR(25) NOT NULL UNIQUE,
    descricao         VARCHAR(40) NOT NULL,
    cid10             VARCHAR(30) NOT NULL,
    ordem             SMALLINT    NOT NULL
);

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

CREATE TABLE fato_obito_sim (
    codigo_ibge       CHAR(7)   NOT NULL REFERENCES dim_municipio (codigo_ibge),
    id_tempo          INTEGER   NOT NULL REFERENCES dim_tempo (id_tempo),
    id_sexo           SMALLINT  NOT NULL REFERENCES dim_sexo (id_sexo),
    id_raca_cor       SMALLINT  NOT NULL REFERENCES dim_raca_cor (id_raca_cor),
    id_faixa_etaria   SMALLINT  NOT NULL REFERENCES dim_faixa_etaria (id_faixa_etaria),
    id_local_obito    SMALLINT  NOT NULL REFERENCES dim_local_obito (id_local_obito),
    id_meio_agressao  SMALLINT  NOT NULL REFERENCES dim_meio_agressao (id_meio_agressao),
    obitos            INTEGER   NOT NULL CHECK (obitos > 0),
    PRIMARY KEY (codigo_ibge, id_tempo, id_sexo, id_raca_cor, id_faixa_etaria,
                 id_local_obito, id_meio_agressao)
);
CREATE INDEX ix_fato_sim_tempo ON fato_obito_sim (id_tempo);
CREATE INDEX ix_fato_sim_perfil ON fato_obito_sim (id_sexo, id_raca_cor, id_faixa_etaria);

CREATE TABLE fato_populacao (
    codigo_ibge      CHAR(7)   NOT NULL REFERENCES dim_municipio (codigo_ibge),
    id_sexo          SMALLINT  NOT NULL REFERENCES dim_sexo (id_sexo),
    id_raca_cor      SMALLINT  NOT NULL REFERENCES dim_raca_cor (id_raca_cor),
    id_faixa_etaria  SMALLINT  NOT NULL REFERENCES dim_faixa_etaria (id_faixa_etaria),
    ano_censo        SMALLINT  NOT NULL DEFAULT 2022,
    populacao        INTEGER   NOT NULL CHECK (populacao > 0),
    PRIMARY KEY (codigo_ibge, id_sexo, id_raca_cor, id_faixa_etaria, ano_censo)
);
CREATE INDEX ix_fato_pop_perfil ON fato_populacao (id_sexo, id_raca_cor, id_faixa_etaria);

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

INSERT INTO dim_sexo (id_sexo, codigo, descricao) VALUES
    (1, 'masculino', 'Masculino'),
    (2, 'feminino',  'Feminino');

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

INSERT INTO dim_local_obito (id_local_obito, codigo, descricao, ordem) VALUES
    (1, 'domicilio',             'Domicílio',                1),
    (2, 'via_publica',           'Via pública',              2),
    (3, 'estabelecimento_saude', 'Estabelecimento de saúde', 3),
    (4, 'aldeia_indigena',       'Aldeia indígena',          4),
    (5, 'outros',                'Outros',                   5),
    (9, 'local_ignorado',        'Ignorado',                 9);

INSERT INTO dim_meio_agressao (id_meio_agressao, codigo, descricao, cid10, ordem) VALUES
    (1, 'arma_fogo',              'Arma de fogo',                 'X93–X95',            1),
    (2, 'objeto_cortante',        'Objeto cortante/penetrante',   'X99',                2),
    (3, 'objeto_contundente',     'Objeto contundente',           'Y00',                3),
    (4, 'forca_corporal',         'Força corporal',               'Y04–Y05',            4),
    (5, 'enforcamento_sufocacao', 'Enforcamento/sufocação',       'X91',                5),
    (6, 'envenenamento',          'Envenenamento',                'X85–X90',            6),
    (7, 'maus_tratos',            'Negligência/maus-tratos',      'Y06–Y07',            7),
    (8, 'outros',                 'Outros meios',                 'X92, X96–X98, Y01–Y03, Y08', 8),
    (9, 'meio_nao_especificado',  'Não especificado',             'Y09',                9);

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

CREATE VIEW vw_sim AS
SELECT u.regiao, u.sigla_uf, m.codigo_ibge, m.nome AS municipio,
       t.ano, t.mes, t.id_tempo,
       s.codigo AS sexo, s.descricao AS sexo_descricao,
       r.codigo AS raca_cor, r.descricao AS raca_cor_descricao, r.grupo AS grupo_racial,
       fe.codigo AS faixa_etaria, fe.descricao AS faixa_etaria_descricao, fe.ordem AS faixa_ordem,
       l.codigo AS local_obito, l.descricao AS local_obito_descricao,
       mg.codigo AS meio_agressao, mg.descricao AS meio_agressao_descricao,
       f.obitos
FROM fato_obito_sim f
JOIN dim_municipio     m  USING (codigo_ibge)
JOIN dim_uf            u  USING (sigla_uf)
JOIN dim_tempo         t  USING (id_tempo)
JOIN dim_sexo          s  USING (id_sexo)
JOIN dim_raca_cor      r  USING (id_raca_cor)
JOIN dim_faixa_etaria  fe USING (id_faixa_etaria)
JOIN dim_local_obito   l  USING (id_local_obito)
JOIN dim_meio_agressao mg USING (id_meio_agressao);

CREATE VIEW vw_populacao AS
SELECT u.regiao, u.sigla_uf, m.codigo_ibge, m.nome AS municipio,
       s.codigo AS sexo, r.codigo AS raca_cor, r.grupo AS grupo_racial,
       fe.codigo AS faixa_etaria, fe.ordem AS faixa_ordem,
       p.ano_censo, p.populacao
FROM fato_populacao p
JOIN dim_municipio    m  USING (codigo_ibge)
JOIN dim_uf           u  USING (sigla_uf)
JOIN dim_sexo         s  USING (id_sexo)
JOIN dim_raca_cor     r  USING (id_raca_cor)
JOIN dim_faixa_etaria fe USING (id_faixa_etaria);

CREATE VIEW vw_taxa_sim_uf AS
WITH anos AS (
    SELECT ano, COUNT(*) AS meses_cobertos
    FROM dim_tempo WHERE sim_periodo_coberto GROUP BY ano
), pop AS (
    SELECT m.sigla_uf, p.id_sexo, p.id_raca_cor, p.id_faixa_etaria, SUM(p.populacao) AS populacao
    FROM fato_populacao p JOIN dim_municipio m USING (codigo_ibge)
    GROUP BY 1, 2, 3, 4
), obitos AS (
    SELECT t.ano, m.sigla_uf, f.id_sexo, f.id_raca_cor, f.id_faixa_etaria,
           SUM(f.obitos) AS obitos,
           SUM(f.obitos) FILTER (WHERE l.codigo = 'domicilio') AS obitos_domicilio,
           SUM(f.obitos) FILTER (WHERE mg.codigo = 'arma_fogo') AS obitos_arma_fogo
    FROM fato_obito_sim f
    JOIN dim_municipio     m  USING (codigo_ibge)
    JOIN dim_tempo         t  USING (id_tempo)
    JOIN dim_local_obito   l  USING (id_local_obito)
    JOIN dim_meio_agressao mg USING (id_meio_agressao)
    GROUP BY 1, 2, 3, 4, 5
), grade AS (
    SELECT a.ano, a.meses_cobertos, p.sigla_uf, p.id_sexo, p.id_raca_cor, p.id_faixa_etaria, p.populacao
    FROM anos a CROSS JOIN pop p
    UNION ALL
    SELECT o.ano, a.meses_cobertos, o.sigla_uf, o.id_sexo, o.id_raca_cor, o.id_faixa_etaria, 0
    FROM obitos o JOIN anos a USING (ano)
    WHERE NOT EXISTS (SELECT 1 FROM pop p
                      WHERE p.sigla_uf = o.sigla_uf AND p.id_sexo = o.id_sexo
                        AND p.id_raca_cor = o.id_raca_cor AND p.id_faixa_etaria = o.id_faixa_etaria)
)
SELECT g.ano, g.meses_cobertos, u.regiao, g.sigla_uf,
       s.codigo AS sexo, r.codigo AS raca_cor, r.grupo AS grupo_racial,
       fe.codigo AS faixa_etaria, fe.ordem AS faixa_ordem,
       g.populacao,
       COALESCE(o.obitos, 0)           AS obitos,
       COALESCE(o.obitos_domicilio, 0) AS obitos_domicilio,
       COALESCE(o.obitos_arma_fogo, 0) AS obitos_arma_fogo
FROM grade g
JOIN dim_uf           u  USING (sigla_uf)
JOIN dim_sexo         s  USING (id_sexo)
JOIN dim_raca_cor     r  USING (id_raca_cor)
JOIN dim_faixa_etaria fe USING (id_faixa_etaria)
LEFT JOIN obitos o ON o.ano = g.ano AND o.sigla_uf = g.sigla_uf AND o.id_sexo = g.id_sexo
                  AND o.id_raca_cor = g.id_raca_cor AND o.id_faixa_etaria = g.id_faixa_etaria;

CREATE VIEW vw_kpi_interseccional AS
WITH base AS (
    SELECT ano, meses_cobertos, sexo, grupo_racial,
           SUM(obitos) AS obitos, SUM(populacao) AS populacao,
           SUM(obitos_domicilio) AS obitos_domicilio
    FROM vw_taxa_sim_uf
    WHERE grupo_racial <> 'Ignorada'
    GROUP BY 1, 2, 3, 4
), taxas AS (
    SELECT *, obitos * 100000.0 / NULLIF(populacao, 0) * 12 / meses_cobertos AS taxa_anualizada
    FROM base
)
SELECT t.ano, t.meses_cobertos, t.sexo, t.grupo_racial, t.obitos, t.populacao,
       ROUND(t.obitos * 100000.0 / NULLIF(t.populacao, 0), 2) AS taxa_100mil,
       ROUND(t.taxa_anualizada, 2) AS taxa_100mil_anualizada,
       ROUND(t.taxa_anualizada / NULLIF(b.taxa_anualizada, 0), 2) AS razao_vs_branca,
       ROUND(100.0 * t.obitos_domicilio / NULLIF(t.obitos, 0), 1) AS pct_domicilio
FROM taxas t
LEFT JOIN taxas b ON b.ano = t.ano AND b.sexo = t.sexo AND b.grupo_racial = 'Branca';

CREATE VIEW vw_kpi_uf AS
WITH anos AS (
    SELECT ano, COUNT(*) FILTER (WHERE sim_periodo_coberto) AS meses_sim FROM dim_tempo GROUP BY ano
), sinesp AS (
    SELECT t.ano, m.sigla_uf,
           SUM(f.vitimas_fem) FILTER (WHERE e.codigo = 'feminicidio')           AS feminicidios,
           SUM(f.vitimas_fem) FILTER (WHERE e.codigo = 'tentativa_feminicidio') AS tentativas_feminicidio,
           SUM(f.vitimas_fem) FILTER (WHERE e.tipo = 'consumado')               AS mortes_violentas_fem
    FROM fato_ocorrencia_sinesp f
    JOIN dim_municipio m USING (codigo_ibge)
    JOIN dim_tempo     t USING (id_tempo)
    JOIN dim_evento    e USING (id_evento)
    GROUP BY 1, 2
), sim AS (
    SELECT t.ano, m.sigla_uf,
           SUM(f.obitos) AS obitos_fem,
           SUM(f.obitos) FILTER (WHERE l.codigo = 'domicilio') AS obitos_fem_domicilio,
           SUM(f.obitos) FILTER (WHERE r.grupo = 'Negra')      AS obitos_fem_negras
    FROM fato_obito_sim f
    JOIN dim_municipio   m USING (codigo_ibge)
    JOIN dim_tempo       t USING (id_tempo)
    JOIN dim_sexo        s USING (id_sexo)
    JOIN dim_raca_cor    r USING (id_raca_cor)
    JOIN dim_local_obito l USING (id_local_obito)
    WHERE s.codigo = 'feminino'
    GROUP BY 1, 2
), pop AS (
    SELECT m.sigla_uf, SUM(p.populacao) AS pop_fem
    FROM fato_populacao p
    JOIN dim_municipio m USING (codigo_ibge)
    JOIN dim_sexo      s USING (id_sexo)
    WHERE s.codigo = 'feminino'
    GROUP BY 1
)
SELECT a.ano, a.meses_sim, u.regiao, u.sigla_uf, u.nome_uf, p.pop_fem,
       COALESCE(si.feminicidios, 0)           AS feminicidios,
       COALESCE(si.tentativas_feminicidio, 0) AS tentativas_feminicidio,
       COALESCE(si.mortes_violentas_fem, 0)   AS mortes_violentas_fem,
       COALESCE(sm.obitos_fem, 0)             AS obitos_fem_sim,
       COALESCE(sm.obitos_fem_domicilio, 0)   AS obitos_fem_domicilio_sim,
       COALESCE(sm.obitos_fem_negras, 0)      AS obitos_fem_negras_sim,
       ROUND(COALESCE(si.feminicidios, 0) * 100000.0 / p.pop_fem, 2) AS taxa_feminicidio_100mil,
       ROUND(100.0 * si.feminicidios / NULLIF(si.mortes_violentas_fem, 0), 1) AS pct_feminicidio_mortes_violentas,
       CASE WHEN si.tentativas_feminicidio > 0
            THEN ROUND(100.0 * si.feminicidios / (si.feminicidios + si.tentativas_feminicidio), 1)
       END AS pct_letalidade_feminicidio,
       ROUND(100.0 * sm.obitos_fem_domicilio / NULLIF(sm.obitos_fem, 0), 1) AS pct_obitos_fem_domicilio
FROM anos a
CROSS JOIN dim_uf u
JOIN pop p ON p.sigla_uf = u.sigla_uf
LEFT JOIN sinesp si ON si.ano = a.ano AND si.sigla_uf = u.sigla_uf
LEFT JOIN sim    sm ON sm.ano = a.ano AND sm.sigla_uf = u.sigla_uf;

CREATE VIEW vw_comparativo_sinesp_sim AS
WITH s AS (
    SELECT t.ano, f.codigo_ibge,
           SUM(f.vitimas_fem) FILTER (WHERE e.codigo = 'feminicidio')           AS feminicidios,
           SUM(f.vitimas_fem) FILTER (WHERE e.codigo = 'tentativa_feminicidio') AS tentativas_feminicidio,
           SUM(f.vitimas_fem) FILTER (WHERE e.tipo = 'consumado')               AS mortes_violentas_fem
    FROM fato_ocorrencia_sinesp f
    JOIN dim_evento e USING (id_evento)
    JOIN dim_tempo  t USING (id_tempo)
    WHERE t.sim_periodo_coberto
    GROUP BY t.ano, f.codigo_ibge
), o AS (
    SELECT t.ano, f.codigo_ibge, SUM(f.obitos) AS obitos
    FROM fato_obito_sim f
    JOIN dim_tempo t USING (id_tempo)
    JOIN dim_sexo  x USING (id_sexo)
    WHERE x.codigo = 'feminino'
    GROUP BY t.ano, f.codigo_ibge
), chaves AS (
    SELECT ano, codigo_ibge FROM s UNION SELECT ano, codigo_ibge FROM o
)
SELECT k.ano, u.regiao, u.sigla_uf, m.codigo_ibge, m.nome AS municipio,
       COALESCE(s.feminicidios, 0)           AS feminicidios_sinesp,
       COALESCE(s.tentativas_feminicidio, 0) AS tentativas_feminicidio_sinesp,
       COALESCE(s.mortes_violentas_fem, 0)   AS mortes_violentas_fem_sinesp,
       COALESCE(o.obitos, 0)                 AS obitos_fem_agressao_sim
FROM chaves k
JOIN dim_municipio m ON m.codigo_ibge = k.codigo_ibge
JOIN dim_uf u USING (sigla_uf)
LEFT JOIN s ON s.ano = k.ano AND s.codigo_ibge = k.codigo_ibge
LEFT JOIN o ON o.ano = k.ano AND o.codigo_ibge = k.codigo_ibge;
