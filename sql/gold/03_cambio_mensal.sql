
-- MacroData Brasil
-- Camada Gold: indicadores mensais de câmbio USD/BRL
-- Fonte: BCB - SGS 1

CREATE OR REPLACE TABLE
    `macrodata-brasil.gold.cambio_mensal` AS

WITH base_mensal AS (
    SELECT
        DATE_TRUNC(data_referencia, MONTH) AS mes_referencia,

        MAX(data_referencia) AS data_ultima_observacao,

        ROUND(
            AVG(cotacao_venda), 4
        ) AS cotacao_media,

        COUNT(*) AS dias_com_cotacao

    FROM `macrodata-brasil.silver.bcb_cambio`

    GROUP BY 1
),

fechamento_mensal AS (
    SELECT
        b.mes_referencia,
        b.data_ultima_observacao,
        s.cotacao_venda AS cotacao_fechamento,
        b.cotacao_media,
        b.dias_com_cotacao

    FROM base_mensal b

    INNER JOIN `macrodata-brasil.silver.bcb_cambio` s
        ON s.data_referencia = b.data_ultima_observacao
),

comparacao_mensal AS (
    SELECT
        *,
        LAG(cotacao_fechamento) OVER (
            ORDER BY mes_referencia
        ) AS cotacao_mes_anterior,

        LAG(mes_referencia) OVER (
            ORDER BY mes_referencia
        ) AS mes_anterior

    FROM fechamento_mensal
)

SELECT
    mes_referencia,
    data_ultima_observacao,
    cotacao_fechamento,
    cotacao_media,
    dias_com_cotacao,
    cotacao_mes_anterior,

    CASE
        WHEN mes_anterior = DATE_SUB(
            mes_referencia, INTERVAL 1 MONTH
        )
        AND cotacao_mes_anterior > 0

        THEN ROUND(
            (
                cotacao_fechamento
                / cotacao_mes_anterior - 1
            ) * 100,
            2
        )

        ELSE NULL
    END AS variacao_percentual

FROM comparacao_mensal;
