
-- MacroData Brasil
-- Camada Gold: IPCA mensal e acumulado em 12 meses
-- Fonte: IBGE/SIDRA - Tabela 1737, variável 63

CREATE OR REPLACE TABLE `macrodata-brasil.gold.ipca_mensal` AS

WITH base AS (
    SELECT
        mes_referencia,
        ipca_mensal
    FROM `macrodata-brasil.silver.ibge_ipca`
),

calculos AS (
    SELECT
        mes_referencia,
        ipca_mensal,

        COUNT(*) OVER (
            ORDER BY mes_referencia
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS quantidade_meses,

        LAG(mes_referencia, 11) OVER (
            ORDER BY mes_referencia
        ) AS inicio_janela,

        EXP(
            SUM(
                LN(1 + CAST(ipca_mensal AS FLOAT64) / 100)
            ) OVER (
                ORDER BY mes_referencia
                ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
            )
        ) AS fator_acumulado

    FROM base
)

SELECT
    mes_referencia,
    ipca_mensal,

    CASE
        WHEN quantidade_meses = 12
         AND DATE_DIFF(
             mes_referencia,
             inicio_janela,
             MONTH
         ) = 11

        THEN ROUND(
            (fator_acumulado - 1) * 100,
            2
        )

        ELSE NULL
    END AS ipca_acumulado_12m

FROM calculos;
