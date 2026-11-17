
import logging
import re

from pathlib import Path

from google.cloud import bigquery

from config import PROJECT_ID, BIGQUERY_LOCATION


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

TRANSFORMACOES = [
    ("silver/01_tratar_selic.sql", "silver.bcb_selic", "TABLE"),
    ("silver/02_tratar_ipca.sql", "silver.ibge_ipca", "TABLE"),
    ("silver/03_tratar_cambio.sql", "silver.bcb_cambio", "TABLE"),
    ("gold/01_selic_mensal.sql", "gold.selic_mensal", "TABLE"),
    ("gold/02_ipca_mensal.sql", "gold.ipca_mensal", "TABLE"),
    ("gold/03_cambio_mensal.sql", "gold.cambio_mensal", "TABLE"),
    ("gold/04_visao_macro_mensal.sql", "gold.vw_macro_mensal", "VIEW"),
]

VALIDACOES = {
    "silver.bcb_selic": {
        "origem": """
            SELECT COUNT(DISTINCT SAFE.PARSE_DATE('%d/%m/%Y', data))
            FROM `macrodata-brasil.bronze.bcb_selic_raw`
            WHERE SAFE_CAST(valor AS NUMERIC) IS NOT NULL
        """,
        "chave": "data_referencia",
        "valor": "taxa_selic",
    },
    "silver.ibge_ipca": {
        "origem": """
            SELECT COUNT(DISTINCT SAFE.PARSE_DATE('%Y%m', periodo))
            FROM `macrodata-brasil.bronze.ibge_ipca_raw`
            WHERE SAFE_CAST(valor AS NUMERIC) IS NOT NULL
              AND codigo_indicador = '63'
              AND localidade = 'Brasil'
        """,
        "chave": "mes_referencia",
        "valor": "ipca_mensal",
    },
    "silver.bcb_cambio": {
        "origem": """
            SELECT COUNT(DISTINCT SAFE.PARSE_DATE('%d/%m/%Y', data))
            FROM `macrodata-brasil.bronze.bcb_cambio_raw`
            WHERE SAFE_CAST(valor AS NUMERIC) > 0
        """,
        "chave": "data_referencia",
        "valor": "cotacao_venda",
    },
    "gold.selic_mensal": {
        "origem": """
            SELECT COUNT(DISTINCT DATE_TRUNC(data_referencia, MONTH))
            FROM `macrodata-brasil.silver.bcb_selic`
        """,
        "chave": "mes_referencia",
        "valor": "taxa_selic",
    },
    "gold.ipca_mensal": {
        "origem": """
            SELECT COUNT(*)
            FROM `macrodata-brasil.silver.ibge_ipca`
        """,
        "chave": "mes_referencia",
        "valor": "ipca_mensal",
    },
    "gold.cambio_mensal": {
        "origem": """
            SELECT COUNT(DISTINCT DATE_TRUNC(data_referencia, MONTH))
            FROM `macrodata-brasil.silver.bcb_cambio`
        """,
        "chave": "mes_referencia",
        "valor": "cotacao_fechamento",
    },
    "gold.vw_macro_mensal": {
        "origem": """
            SELECT COUNT(DISTINCT mes_referencia)
            FROM (
                SELECT mes_referencia
                FROM `macrodata-brasil.gold.selic_mensal`
                UNION ALL
                SELECT mes_referencia
                FROM `macrodata-brasil.gold.ipca_mensal`
                UNION ALL
                SELECT mes_referencia
                FROM `macrodata-brasil.gold.cambio_mensal`
            )
        """,
        "chave": "mes_referencia",
        "valor": None,
    },
}


def executar_consulta(client, sql):
    job = client.query(
        sql,
        location=BIGQUERY_LOCATION,
    )

    return job.result()


def consultar_numero(client, sql):
    return next(iter(executar_consulta(client, sql)))[0]


def preparar_transformacoes(client):
    consultas = []

    for arquivo, destino, tipo in TRANSFORMACOES:
        caminho = RAIZ_PROJETO / "sql" / arquivo

        if not caminho.is_file():
            raise FileNotFoundError(
                f"Arquivo não encontrado: {caminho}"
            )

        conteudo = caminho.read_text(
            encoding="utf-8-sig"
        )

        sql = re.sub(
            r"--[^\n]*",
            "",
            conteudo,
        ).strip()

        sql = sql.removesuffix(";").strip()

        nome_completo = f"{PROJECT_ID}.{destino}"
        destino_esperado = re.escape(nome_completo)

        padrao = (
            rf"^CREATE\s+OR\s+REPLACE\s+{tipo}\s+"
            rf"`{destino_esperado}`\s+AS\s+"
        )

        if not re.match(
            padrao,
            sql,
            flags=re.IGNORECASE,
        ):
            raise ValueError(
                f"Destino ou tipo inesperado: {arquivo}"
            )

        if ";" in sql:
            raise ValueError(
                f"Mais de uma instrução em {arquivo}"
            )

        # Confere a sintaxe e as referências sem executar a alteração.
        config_teste = bigquery.QueryJobConfig(
            dry_run=True,
            use_query_cache=False,
        )

        client.query(
            sql,
            job_config=config_teste,
            location=BIGQUERY_LOCATION,
        )

        logger.info(
            "SQL conferido: %s",
            arquivo,
        )

        consultas.append((arquivo, destino, sql))

    return consultas


def validar_tabela(client, destino):
    config = VALIDACOES[destino]

    tabela = f"{PROJECT_ID}.{destino}"
    chave = config["chave"]
    valor = config["valor"]

    esperados = consultar_numero(
        client,
        config["origem"],
    )

    condicao_invalida = f"{chave} IS NULL"

    if valor:
        condicao_invalida += f" OR {valor} IS NULL"

    consulta = f"""
        SELECT
            COUNT(*) AS total,
            COUNT(DISTINCT {chave}) AS chaves_unicas,
            COUNTIF({condicao_invalida}) AS invalidos,
            MIN({chave}) AS primeira_data,
            MAX({chave}) AS ultima_data
        FROM `{tabela}`
    """

    resultado = next(
        iter(executar_consulta(client, consulta))
    )

    if (
        resultado.total != esperados
        or resultado.chaves_unicas != resultado.total
        or resultado.invalidos > 0
        or resultado.total == 0
    ):
        raise RuntimeError(
            f"Validação falhou em {destino}. "
            f"Esperados: {esperados}, "
            f"encontrados: {resultado.total}, "
            f"chaves únicas: {resultado.chaves_unicas}, "
            f"inválidos: {resultado.invalidos}"
        )

    logger.info(
        "%s | %s registros | %s até %s",
        destino,
        resultado.total,
        resultado.primeira_data,
        resultado.ultima_data,
    )


def atualizar_camadas():
    logger.info("Iniciando atualização da Silver e Gold")

    client = bigquery.Client(
        project=PROJECT_ID,
        location=BIGQUERY_LOCATION,
    )

    consultas = preparar_transformacoes(client)

    logger.info(
        "Pré-validação concluída: %s SQLs",
        len(consultas),
    )

    for arquivo, destino, sql in consultas:
        logger.info("Executando %s", arquivo)

        executar_consulta(client, sql)

        validar_tabela(client, destino)

        logger.info("%s | Atualização validada", destino)

    logger.info("Silver e Gold atualizadas com sucesso")


if __name__ == "__main__":
    atualizar_camadas()
