
-- MacroData Brasil
-- Promoção da tabela candidata do IPCA
-- para a Bronze oficial

CREATE OR REPLACE TABLE
    `macrodata-brasil.bronze.ibge_ipca_raw`
AS
SELECT
    CAST(localidade AS STRING) AS localidade,
    CAST(codigo_indicador AS STRING) AS codigo_indicador,
    CAST(indicador AS STRING) AS indicador,
    CAST(periodo AS STRING) AS periodo,
    CAST(descricao_periodo AS STRING) AS descricao_periodo,
    CAST(valor AS STRING) AS valor,
    CAST(unidade AS STRING) AS unidade,
    CAST(data_extracao AS TIMESTAMP) AS data_extracao,
    CAST(fonte AS STRING) AS fonte
FROM `macrodata-brasil.bronze.ibge_ipca_candidata`;
