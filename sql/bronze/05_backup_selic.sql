-- Backup da Bronze antes da primeira carga incremental
-- Data: 17/11/2026

CREATE TABLE IF NOT EXISTS
  `macrodata-brasil.bronze.bcb_selic_backup_20261117`
AS
SELECT
    data,
    valor,
    data_extracao,
    fonte
FROM `macrodata-brasil.bronze.bcb_selic_raw`;
