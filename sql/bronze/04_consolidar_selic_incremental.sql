
CREATE OR REPLACE TABLE
  `macrodata-brasil.bronze.bcb_selic_candidata`
AS

WITH dados_unificados AS (

  -- Histórico existente
  SELECT
    data,
    valor,
    data_extracao,
    fonte,
    0 AS prioridade
  FROM `macrodata-brasil.bronze.bcb_selic_raw`

  UNION ALL

  -- Dados mais recentes
  SELECT
    data,
    valor,
    data_extracao,
    fonte,
    1 AS prioridade
  FROM `macrodata-brasil.bronze.bcb_selic_staging`

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
