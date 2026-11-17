
-- MacroData Brasil
-- Camada Silver: tratamento do IPCA mensal
-- Fonte: IBGE/SIDRA - Tabela 1737, variável 63

CREATE OR REPLACE TABLE `macrodata-brasil.silver.ibge_ipca` AS

WITH dados_tratados AS (
    SELECT
        SAFE.PARSE_DATE('%Y%m', periodo) AS mes_referencia,
        SAFE_CAST(valor AS NUMERIC) AS ipca_mensal,
        localidade,
        codigo_indicador,
        unidade,
        data_extracao,
        fonte
    FROM `macrodata-brasil.bronze.ibge_ipca_raw`
),

dados_validados AS (
    SELECT *
    FROM dados_tratados
    WHERE mes_referencia IS NOT NULL
      AND ipca_mensal IS NOT NULL
      AND codigo_indicador = '63'
      AND localidade = 'Brasil'
),

dados_deduplicados AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY mes_referencia
            ORDER BY data_extracao DESC
        ) AS rn
    FROM dados_validados
)

SELECT
    mes_referencia,
    ipca_mensal,
    unidade,
    data_extracao,
    fonte
FROM dados_deduplicados
WHERE rn = 1;