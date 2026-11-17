
"""
MacroData Brasil
Configurações centralizadas do pipeline de dados.
"""

import os

# Google Cloud / BigQuery
PROJECT_ID = os.getenv(
    "GCP_PROJECT_ID",
    "macrodata-brasil"
)

BIGQUERY_LOCATION = "southamerica-east1"

DATASET_BRONZE = "bronze"
DATASET_SILVER = "silver"
DATASET_GOLD = "gold"

# Tabelas Bronze oficiais
TABELAS_BRONZE = {
    "selic": f"{PROJECT_ID}.bronze.bcb_selic_raw",
    "cambio": f"{PROJECT_ID}.bronze.bcb_cambio_raw",
    "ipca": f"{PROJECT_ID}.bronze.ibge_ipca_raw",
}

# Tabelas intermediárias
TABELAS_STAGING = {
    "selic": f"{PROJECT_ID}.bronze.bcb_selic_staging",
    "cambio": f"{PROJECT_ID}.bronze.bcb_cambio_staging",
    "ipca": f"{PROJECT_ID}.bronze.ibge_ipca_staging",
}

# APIs oficiais
URL_SELIC = (
    "https://api.bcb.gov.br/dados/"
    "serie/bcdata.sgs.432/dados"
)

URL_CAMBIO = (
    "https://api.bcb.gov.br/dados/"
    "serie/bcdata.sgs.1/dados"
)

URL_IPCA = (
    "https://apisidra.ibge.gov.br/"
    "values/t/1737/n1/all/v/63"
)

# Parâmetros da carga incremental
JANELA_REPROCESSAMENTO_DIAS = 30
JANELA_REPROCESSAMENTO_IPCA_MESES = 3

# Início do histórico
DATA_INICIAL_BCB = "2024-01-01"
PERIODO_INICIAL_IPCA = "202311"

# Requisições HTTP
TIMEOUT_BCB = 30
TIMEOUT_IBGE = 60

# Fuso horário
TIMEZONE = "America/Sao_Paulo"
