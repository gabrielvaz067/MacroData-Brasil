
import io
import logging
import re

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from google.cloud import bigquery

from config import (
    PROJECT_ID,
    BIGQUERY_LOCATION,
    TABELAS_BRONZE,
    TABELAS_STAGING,
    URL_SELIC,
    URL_CAMBIO,
    URL_IPCA,
    JANELA_REPROCESSAMENTO_DIAS,
    JANELA_REPROCESSAMENTO_IPCA_MESES,
    DATA_INICIAL_BCB,
    TIMEOUT_BCB,
    TIMEOUT_IBGE,
    TIMEZONE,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

CONFIG_CANDIDATAS = {
    "selic": {
        "arquivo": "04_consolidar_selic_incremental.sql",
        "tabela": (
            f"{PROJECT_ID}.bronze.bcb_selic_candidata"
        ),
        "chave": "data",
    },
    "cambio": {
        "arquivo": "07_consolidar_cambio_incremental.sql",
        "tabela": (
            f"{PROJECT_ID}.bronze.bcb_cambio_candidata"
        ),
        "chave": "data",
    },
    "ipca": {
        "arquivo": "10_consolidar_ipca_incremental.sql",
        "tabela": (
            f"{PROJECT_ID}.bronze.ibge_ipca_candidata"
        ),
        "chave": (
            "localidade, codigo_indicador, periodo"
        ),
    },
}


def criar_cliente_bigquery():
    client = bigquery.Client(
        project=PROJECT_ID,
        location=BIGQUERY_LOCATION,
    )

    logger.info("Conectado ao BigQuery: %s", PROJECT_ID)

    return client


def consultar_sql(client, sql):
    return client.query(
        sql,
        location=BIGQUERY_LOCATION,
    ).result()


def consultar_ultima_data(client, fonte):
    if fonte not in TABELAS_BRONZE:
        raise ValueError(f"Fonte inválida: {fonte}")

    tabela = TABELAS_BRONZE[fonte]

    if fonte == "ipca":
        expressao = "SAFE.PARSE_DATE('%Y%m', periodo)"
    else:
        expressao = "SAFE.PARSE_DATE('%d/%m/%Y', data)"

    sql = f"""
        SELECT MAX({expressao}) AS ultima_data
        FROM `{tabela}`
    """

    ultima_data = next(
        iter(consultar_sql(client, sql))
    ).ultima_data

    logger.info(
        "%s | Última data na Bronze: %s",
        fonte.upper(),
        ultima_data,
    )

    return ultima_data


def extrair_bcb(client, fonte):
    fontes = {
        "selic": (URL_SELIC, "BCB_SGS_432"),
        "cambio": (URL_CAMBIO, "BCB_SGS_1"),
    }

    if fonte not in fontes:
        raise ValueError(f"Fonte BCB inválida: {fonte}")

    url, codigo_fonte = fontes[fonte]

    ultima_data = consultar_ultima_data(
        client, fonte
    )

    hoje = datetime.now(
        ZoneInfo(TIMEZONE)
    ).date()

    inicio_historico = datetime.strptime(
        DATA_INICIAL_BCB,
        "%Y-%m-%d",
    ).date()

    inicio = (
        inicio_historico
        if ultima_data is None
        else max(
            inicio_historico,
            ultima_data - timedelta(
                days=JANELA_REPROCESSAMENTO_DIAS
            ),
        )
    )

    if inicio > hoje:
        raise ValueError(
            f"Data inicial futura para {fonte}"
        )

    parametros = {
        "formato": "json",
        "dataInicial": inicio.strftime("%d/%m/%Y"),
        "dataFinal": hoje.strftime("%d/%m/%Y"),
    }

    logger.info(
        "%s | Consultando %s até %s",
        fonte.upper(),
        inicio,
        hoje,
    )

    resposta = requests.get(
        url,
        params=parametros,
        timeout=TIMEOUT_BCB,
    )
    resposta.raise_for_status()

    dados = resposta.json()

    if not isinstance(dados, list):
        raise ValueError(
            f"Resposta inesperada para {fonte}"
        )

    df = pd.DataFrame(dados)

    if df.empty or not {"data", "valor"}.issubset(
        df.columns
    ):
        raise ValueError(
            f"Dados ausentes ou incompletos: {fonte}"
        )

    datas = pd.to_datetime(
        df["data"],
        format="%d/%m/%Y",
        errors="coerce",
    )

    valores = pd.to_numeric(
        df["valor"],
        errors="coerce",
    )

    if datas.isna().any() or valores.isna().any():
        raise ValueError(
            f"Datas ou valores inválidos: {fonte}"
        )

    if datas.duplicated().any():
        raise ValueError(
            f"Datas duplicadas: {fonte}"
        )

    if (valores <= 0).any():
        raise ValueError(
            f"Valores não positivos: {fonte}"
        )

    df["data_extracao"] = datetime.now(
        timezone.utc
    )
    df["fonte"] = codigo_fonte

    df = df[
        ["data", "valor", "data_extracao", "fonte"]
    ].copy()

    logger.info(
        "%s | %s registros extraídos",
        fonte.upper(),
        len(df),
    )

    return df


def extrair_ipca(client):
    ultima_data = consultar_ultima_data(
        client, "ipca"
    )

    if ultima_data is None:
        raise ValueError(
            "Histórico do IPCA ausente na Bronze"
        )

    hoje = datetime.now(
        ZoneInfo(TIMEZONE)
    ).date()

    meses_decorridos = (
        (hoje.year - ultima_data.year) * 12
        + hoje.month - ultima_data.month
    )

    quantidade_meses = (
        max(0, meses_decorridos)
        + JANELA_REPROCESSAMENTO_IPCA_MESES
        + 1
    )

    url = (
        f"{URL_IPCA}/p/last%20{quantidade_meses}"
    )

    resposta = requests.get(
        url,
        timeout=TIMEOUT_IBGE,
    )
    resposta.raise_for_status()

    dados = resposta.json()

    if not isinstance(dados, list) or len(dados) < 2:
        raise ValueError(
            "API do IBGE retornou dados vazios"
        )

    df_api = pd.DataFrame(dados[1:])

    mapeamento = {
        "D1N": "localidade",
        "D2C": "codigo_indicador",
        "D2N": "indicador",
        "D3C": "periodo",
        "D3N": "descricao_periodo",
        "V": "valor",
        "MN": "unidade",
    }

    if not set(mapeamento).issubset(df_api.columns):
        raise ValueError(
            "Colunas inesperadas na resposta do IBGE"
        )

    df = df_api[
        list(mapeamento)
    ].rename(columns=mapeamento).copy()

    for coluna in mapeamento.values():
        df[coluna] = df[coluna].astype(str)

    periodos = pd.to_datetime(
        df["periodo"],
        format="%Y%m",
        errors="coerce",
    )

    valores = pd.to_numeric(
        df["valor"],
        errors="coerce",
    )

    if periodos.isna().any() or valores.isna().any():
        raise ValueError(
            "IPCA contém competências ou valores inválidos"
        )

    if df["periodo"].duplicated().any():
        raise ValueError(
            "IPCA contém competências duplicadas"
        )

    if not (df["codigo_indicador"] == "63").all():
        raise ValueError(
            "Código de indicador inválido no IPCA"
        )

    if not (df["localidade"] == "Brasil").all():
        raise ValueError(
            "Localidade inválida no IPCA"
        )

    df["data_extracao"] = datetime.now(
        timezone.utc
    )
    df["fonte"] = "IBGE_SIDRA_1737_63"

    df = df.sort_values(
        "periodo"
    ).reset_index(drop=True)

    logger.info(
        "IPCA | %s registros extraídos",
        len(df),
    )

    return df


def carregar_staging(client, fonte, df):
    if fonte not in TABELAS_STAGING:
        raise ValueError(
            f"Staging não configurada: {fonte}"
        )

    if df.empty:
        raise ValueError(
            f"Sem dados para carregar: {fonte}"
        )

    tabela = TABELAS_STAGING[fonte]

    if fonte == "ipca":
        colunas = [
            "localidade",
            "codigo_indicador",
            "indicador",
            "periodo",
            "descricao_periodo",
            "valor",
            "unidade",
            "data_extracao",
            "fonte",
        ]
    else:
        colunas = [
            "data",
            "valor",
            "data_extracao",
            "fonte",
        ]

    if not set(colunas).issubset(df.columns):
        raise ValueError(
            f"Colunas ausentes para {fonte}"
        )

    schema = [
        bigquery.SchemaField(
            coluna,
            "TIMESTAMP"
            if coluna == "data_extracao"
            else "STRING",
        )
        for coluna in colunas
    ]

    jsonl = df[colunas].to_json(
        orient="records",
        lines=True,
        date_format="iso",
        date_unit="ms",
        force_ascii=False,
    )

    arquivo = io.BytesIO(
        jsonl.encode("utf-8")
    )

    job_config = bigquery.LoadJobConfig(
        source_format=(
            bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
        ),
        write_disposition=(
            bigquery.WriteDisposition.WRITE_TRUNCATE
        ),
        schema=schema,
    )

    job = client.load_table_from_file(
        arquivo,
        destination=tabela,
        job_config=job_config,
        location=BIGQUERY_LOCATION,
    )
    job.result()

    sql = f"""
        SELECT COUNT(*) AS total
        FROM `{tabela}`
    """

    total = next(
        iter(consultar_sql(client, sql))
    ).total

    if total != len(df):
        raise RuntimeError(
            f"{fonte}: extraídos={len(df)}, "
            f"gravados={total}"
        )

    logger.info(
        "%s | Staging validada: %s registros",
        fonte.upper(),
        total,
    )

    return total


def executar_sql_consolidacao(client, fonte):
    config = CONFIG_CANDIDATAS[fonte]

    caminho = (
        RAIZ_PROJETO
        / "sql"
        / "bronze"
        / config["arquivo"]
    )

    if not caminho.is_file():
        raise FileNotFoundError(
            f"SQL não encontrado: {caminho}"
        )

    sql = caminho.read_text(encoding="utf-8")

    # A consolidação só pode escrever na tabela candidata.
    sem_comentarios = re.sub(
        r"(?m)^\s*--[^\n]*\n?",
        "",
        sql,
    ).strip()

    destino = re.escape(config["tabela"])

    padrao = (
        rf"^CREATE\s+OR\s+REPLACE\s+TABLE\s+"
        rf"`{destino}`\s+AS\s+"
    )

    if not re.match(
        padrao,
        sem_comentarios,
        flags=re.IGNORECASE,
    ):
        raise ValueError(
            f"Revise o destino do SQL: {caminho.name}. "
            "Esperado: CREATE OR REPLACE TABLE "
            f"`{config['tabela']}` AS ..."
        )

    if sem_comentarios.count(";") > 1:
        raise ValueError(
            "O SQL de consolidação deve conter "
            "apenas uma instrução."
        )

    logger.info(
        "%s | Executando %s",
        fonte.upper(),
        caminho.name,
    )

    consultar_sql(client, sem_comentarios)

    logger.info(
        "%s | Tabela candidata atualizada",
        fonte.upper(),
    )


def validar_candidata(client, fonte):
    config = CONFIG_CANDIDATAS[fonte]

    tabela_raw = TABELAS_BRONZE[fonte]
    tabela_staging = TABELAS_STAGING[fonte]
    tabela_candidata = config["tabela"]
    chave = config["chave"]

    sql_contagem = f"""
        SELECT
            (SELECT COUNT(*)
             FROM `{tabela_raw}`) AS total_raw,

            (SELECT COUNT(*)
             FROM `{tabela_staging}`) AS total_staging,

            (SELECT COUNT(*)
             FROM `{tabela_candidata}`) AS total_candidata,

            (SELECT COUNT(*)
             FROM (
                 SELECT {chave}
                 FROM `{tabela_candidata}`
                 GROUP BY {chave}
                 HAVING COUNT(*) > 1
             )) AS chaves_duplicadas
    """

    resultado = next(
        iter(consultar_sql(client, sql_contagem))
    )

    if resultado.chaves_duplicadas > 0:
        raise RuntimeError(
            f"{fonte}: chaves duplicadas na candidata"
        )

    if resultado.total_candidata < resultado.total_raw:
        raise RuntimeError(
            f"{fonte}: a candidata possui menos "
            "registros que a Bronze oficial"
        )

    colunas_chave = [
        coluna.strip()
        for coluna in chave.split(",")
    ]

    condicao = " AND ".join(
        f"r.{coluna} = c.{coluna}"
        for coluna in colunas_chave
    )

    condicao_staging = " AND ".join(
        f"s.{coluna} = c.{coluna}"
        for coluna in colunas_chave
    )

    # Confere se todas as chaves históricas foram preservadas.
    sql_integridade = f"""
        SELECT COUNT(*) AS ausentes
        FROM `{tabela_raw}` r
        WHERE NOT EXISTS (
            SELECT 1
            FROM `{tabela_candidata}` c
            WHERE {condicao}
        )
    """

    ausentes_raw = next(
        iter(consultar_sql(client, sql_integridade))
    ).ausentes

    if ausentes_raw > 0:
        raise RuntimeError(
            f"{fonte}: {ausentes_raw} registros "
            "históricos ausentes na candidata"
        )

    # Confere se todas as chaves da staging foram incluídas.
    sql_staging = f"""
        SELECT COUNT(*) AS ausentes
        FROM `{tabela_staging}` s
        WHERE NOT EXISTS (
            SELECT 1
            FROM `{tabela_candidata}` c
            WHERE {condicao_staging}
        )
    """

    ausentes_staging = next(
        iter(consultar_sql(client, sql_staging))
    ).ausentes

    if ausentes_staging > 0:
        raise RuntimeError(
            f"{fonte}: {ausentes_staging} registros "
            "da staging ausentes na candidata"
        )

    logger.info(
        "%s | Raw: %s | Staging: %s | Candidata: %s",
        fonte.upper(),
        resultado.total_raw,
        resultado.total_staging,
        resultado.total_candidata,
    )

    logger.info(
        "%s | Validação de chaves aprovada",
        fonte.upper(),
    )

    return resultado.total_candidata


def main():
    logger.info("Iniciando MacroData Brasil")

    client = criar_cliente_bigquery()

    dados = {
        "selic": extrair_bcb(client, "selic"),
        "cambio": extrair_bcb(client, "cambio"),
        "ipca": extrair_ipca(client),
    }

    # Valida todas as extrações antes de gravar.
    for fonte, df in dados.items():
        carregar_staging(client, fonte, df)

    logger.info(
        "Stagings atualizadas. Iniciando consolidação."
    )

    # Executa somente os SQLs das tabelas candidatas.
    for fonte in ("selic", "cambio", "ipca"):
        executar_sql_consolidacao(client, fonte)
        validar_candidata(client, fonte)

    logger.info(
        "Consolidação concluída. "
        "Bronze oficial não foi modificada."
    )


if __name__ == "__main__":
    main()

