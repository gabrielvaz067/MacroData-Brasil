
-- MacroData Brasil
-- Backup da Bronze do IPCA
-- Antes da primeira atualização incremental

CREATE TABLE IF NOT EXISTS
    `macrodata-brasil.bronze.ibge_ipca_backup_20261117`
AS
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
FROM `macrodata-brasil.bronze.ibge_ipca_raw`;
