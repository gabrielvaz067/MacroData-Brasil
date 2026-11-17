
-- MacroData Brasil
-- Criação da tabela Bronze para Meta Selic
-- Fonte: BCB - SGS 432

CREATE TABLE IF NOT EXISTS `macrodata-brasil.bronze.bcb_selic_raw` (
    data STRING,
    valor STRING,
    data_extracao TIMESTAMP,
    fonte STRING
);
