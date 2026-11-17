
-- MacroData Brasil
-- Promover os dados consolidados do câmbio
-- para a Bronze oficial

CREATE OR REPLACE TABLE
    `macrodata-brasil.bronze.bcb_cambio_raw`
AS
SELECT
    CAST(data AS STRING) AS data,
    CAST(valor AS STRING) AS valor,
    CAST(data_extracao AS TIMESTAMP) AS data_extracao,
    CAST(fonte AS STRING) AS fonte
FROM `macrodata-brasil.bronze.bcb_cambio_candidata`;
