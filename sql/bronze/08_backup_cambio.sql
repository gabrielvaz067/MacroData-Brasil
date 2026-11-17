
-- MacroData Brasil
-- Backup da Bronze do câmbio
-- Antes da primeira atualização incremental

CREATE TABLE IF NOT EXISTS
    `macrodata-brasil.bronze.bcb_cambio_backup_20261117`
AS
SELECT
    data,
    valor,
    data_extracao,
    fonte
FROM `macrodata-brasil.bronze.bcb_cambio_raw`;
