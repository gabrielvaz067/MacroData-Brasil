
-- MacroData Brasil
-- Visão consolidada mensal dos indicadores econômicos
-- Fontes: BCB e IBGE

CREATE OR REPLACE VIEW
    `macrodata-brasil.gold.vw_macro_mensal` AS

WITH calendario AS (
    SELECT mes_referencia
    FROM `macrodata-brasil.gold.selic_mensal`

    UNION DISTINCT

    SELECT mes_referencia
    FROM `macrodata-brasil.gold.ipca_mensal`

    UNION DISTINCT

    SELECT mes_referencia
    FROM `macrodata-brasil.gold.cambio_mensal`
)

SELECT
    c.mes_referencia,

    s.taxa_selic,
    s.variacao_pontos_percentuais AS variacao_selic_pp,

    i.ipca_mensal,
    i.ipca_acumulado_12m,

    cb.cotacao_fechamento,
    cb.cotacao_media,
    cb.variacao_percentual AS variacao_cambio_pct

FROM calendario c

LEFT JOIN `macrodata-brasil.gold.selic_mensal` s
    ON c.mes_referencia = s.mes_referencia

LEFT JOIN `macrodata-brasil.gold.ipca_mensal` i
    ON c.mes_referencia = i.mes_referencia

LEFT JOIN `macrodata-brasil.gold.cambio_mensal` cb
    ON c.mes_referencia = cb.mes_referencia;
