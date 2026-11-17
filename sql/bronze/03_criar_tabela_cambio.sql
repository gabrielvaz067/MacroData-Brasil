
-- MacroData Brasil
-- Camada Bronze: câmbio USD/BRL
-- Fonte: Banco Central do Brasil - SGS 1

CREATE TABLE IF NOT EXISTS `macrodata-brasil.bronze.bcb_cambio_raw` (
    data STRING,
    valor STRING,
    data_extracao TIMESTAMP,
    fonte STRING
);
