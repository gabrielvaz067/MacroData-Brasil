
-- MacroData Brasil
-- Camada Silver: tratamento do câmbio USD/BRL
-- Fonte: Banco Central do Brasil - SGS 1

CREATE OR REPLACE TABLE `macrodata-brasil.silver.bcb_cambio` AS

WITH dados_tratados AS (
    SELECT
        SAFE.PARSE_DATE('%d/%m/%Y', data) AS data_referencia,
        SAFE_CAST(valor AS NUMERIC) AS cotacao_venda,
        data_extracao,
        fonte
    FROM `macrodata-brasil.bronze.bcb_cambio_raw`
),

dados_validados AS (
    SELECT *
    FROM dados_tratados
    WHERE data_referencia IS NOT NULL
      AND cotacao_venda IS NOT NULL
      AND cotacao_venda > 0
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
    cotacao_venda,
    data_extracao,
    fonte
FROM dados_deduplicados
WHERE rn = 1;
