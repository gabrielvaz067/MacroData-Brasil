
-- MacroData Brasil
-- Tratamento e deduplicação da Meta Selic

CREATE OR REPLACE TABLE `macrodata-brasil.silver.bcb_selic` AS

WITH dados_tratados AS (
    SELECT
        SAFE.PARSE_DATE('%d/%m/%Y', data) AS data_referencia,
        SAFE_CAST(valor AS NUMERIC) AS taxa_selic,
        data_extracao,
        fonte
    FROM `macrodata-brasil.bronze.bcb_selic_raw`
),

dados_validados AS (
    SELECT *
    FROM dados_tratados
    WHERE data_referencia IS NOT NULL
      AND taxa_selic IS NOT NULL
),

dados_deduplicados AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY data_referencia
            ORDER BY data_extracao DESC
        ) AS rn
    FROM dados_validados
)

SELECT
    data_referencia,
    taxa_selic,
    data_extracao,
    fonte
FROM dados_deduplicados
WHERE rn = 1;
