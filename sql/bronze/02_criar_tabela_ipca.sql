
-- MacroData Brasil
-- Camada Bronze: IPCA mensal
-- Fonte: IBGE/SIDRA - Tabela 1737, variável 63

CREATE TABLE IF NOT EXISTS `macrodata-brasil.bronze.ibge_ipca_raw` (
    localidade STRING,
    codigo_indicador STRING,
    indicador STRING,
    periodo STRING,
    descricao_periodo STRING,
    valor STRING,
    unidade STRING,
    data_extracao TIMESTAMP,
    fonte STRING
);
