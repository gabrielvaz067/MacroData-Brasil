
CREATE OR REPLACE TABLE `macrodata-brasil.gold.selic_mensal` AS

WITH ultimo_registro_mes AS (
    SELECT
        DATE_TRUNC(data_referencia, MONTH) AS mes_referencia,
        data_referencia,
        taxa_selic
    FROM `macrodata-brasil.silver.bcb_selic`

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY DATE_TRUNC(data_referencia, MONTH)
        ORDER BY data_referencia DESC
    ) = 1
),

calculo_variacao AS (
    SELECT
        mes_referencia,
        data_referencia AS data_ultima_observacao,
        taxa_selic,
        LAG(taxa_selic) OVER (
            ORDER BY mes_referencia
        ) AS taxa_mes_anterior
    FROM ultimo_registro_mes
)

SELECT
    mes_referencia,
    data_ultima_observacao,
    taxa_selic,
    taxa_mes_anterior,
    ROUND(
        taxa_selic - taxa_mes_anterior,
        2
    ) AS variacao_pontos_percentuais
FROM calculo_variacao;
