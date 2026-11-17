
-- MacroData Brasil
-- Consolidação incremental do IPCA (IBGE/SIDRA)
-- Prioriza a staging quando a competência já existe

CREATE OR REPLACE TABLE
  `macrodata-brasil.bronze.ibge_ipca_candidata`
AS

WITH dados_unificados AS (
    SELECT
        localidade,
        codigo_indicador,
        indicador,
        periodo,
        descricao_periodo,
        valor,
        unidade,
        data_extracao,
        fonte,
        0 AS prioridade
    FROM `macrodata-brasil.bronze.ibge_ipca_raw`

    UNION ALL

    SELECT
        localidade,
        codigo_indicador,
        indicador,
        periodo,
        descricao_periodo,
        valor,
        unidade,
        data_extracao,
        fonte,
        1 AS prioridade
    FROM `macrodata-brasil.bronze.ibge_ipca_staging`
)

SELECT
    localidade,
    codigo_indicador,
    indicador,
    periodo,
    descricao_periodo,
    valor,
    unidade,
    data_extracao,
    fonte
FROM dados_unificados

QUALIFY ROW_NUMBER() OVER (
    PARTITION BY localidade, codigo_indicador, periodo
    ORDER BY prioridade DESC, data_extracao DESC
) = 1;
