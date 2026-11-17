
-- MacroData Brasil
-- Consolidação incremental do câmbio
-- Prioriza registros da staging para datas existentes

CREATE OR REPLACE TABLE
    `macrodata-brasil.bronze.bcb_cambio_candidata`
AS

WITH dados_unificados AS (

    -- Histórico da Bronze
    SELECT
        data,
        valor,
        data_extracao,
        fonte,
        0 AS prioridade
    FROM `macrodata-brasil.bronze.bcb_cambio_raw`

    UNION ALL

    -- Dados da extração incremental
    SELECT
        data,
        valor,
        data_extracao,
        fonte,
        1 AS prioridade
    FROM `macrodata-brasil.bronze.bcb_cambio_staging`

)

SELECT
    data,
    valor,
    data_extracao,
    fonte
FROM dados_unificados

QUALIFY ROW_NUMBER() OVER (
    PARTITION BY data
    ORDER BY prioridade DESC, data_extracao DESC
) = 1;
