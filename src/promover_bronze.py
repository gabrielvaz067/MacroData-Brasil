
import logging
import re

from pathlib import Path

from google.cloud import bigquery

from config import PROJECT_ID, BIGQUERY_LOCATION
from validar_promocao import validar_fonte


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

ID_BACKUP = "20261117_141052_969569"

FONTES = {
    "selic": {
        "arquivo": "06_promover_selic_bronze.sql",
        "raw": "bcb_selic_raw",
        "candidata": "bcb_selic_candidata",
        "campos": [
            "data", "valor", "data_extracao", "fonte"
        ],
    },
    "cambio": {
        "arquivo": "09_promover_cambio_bronze.sql",
        "raw": "bcb_cambio_raw",
        "candidata": "bcb_cambio_candidata",
        "campos": [
            "data", "valor", "data_extracao", "fonte"
        ],
    },
    "ipca": {
        "arquivo": "12_promover_ipca_bronze.sql",
        "raw": "ibge_ipca_raw",
        "candidata": "ibge_ipca_candidata",
        "campos": [
            "localidade",
            "codigo_indicador",
            "indicador",
            "periodo",
            "descricao_periodo",
            "valor",
            "unidade",
            "data_extracao",
            "fonte",
        ],
    },
}


def tabela(nome):
    return f"{PROJECT_ID}.bronze.{nome}"


def executar(client, sql):
    return client.query(
        sql,
        location=BIGQUERY_LOCATION,
    ).result()


def contar_registros(client, nome):
    sql = f"""
        SELECT COUNT(*) AS total
        FROM `{tabela(nome)}`
    """
    return next(iter(executar(client, sql))).total


def preparar_sql(fonte, config):
    caminho = (
        RAIZ_PROJETO
        / "sql"
        / "bronze"
        / config["arquivo"]
    )

    conteudo = caminho.read_text(encoding="utf-8-sig")

    sql = re.sub(
        r"--[^\n]*",
        "",
        conteudo,
    ).strip().rstrip(";").strip()

    campos = config["campos"]

    projecao = ", ".join(
        f"CAST({campo} AS "
        f"{'TIMESTAMP' if campo == 'data_extracao' else 'STRING'}) "
        f"AS {campo}"
        for campo in campos
    )

    esperado = (
        f"CREATE OR REPLACE TABLE `{tabela(config['raw'])}` "
        f"AS SELECT {projecao} "
        f"FROM `{tabela(config['candidata'])}`"
    )

    def normalizar(texto):
        return re.sub(
            r"\s+",
            " ",
            texto,
        ).strip().lower()

    if normalizar(sql) != normalizar(esperado):
        raise ValueError(
            f"SQL inesperado para {fonte}: "
            f"{config['arquivo']}. "
            "Nenhuma promoção deve ser executada."
        )

    return sql


def verificar_backup(client, fonte, config):
    nome_backup = f"backup_{fonte}_{ID_BACKUP}"

    total_backup = contar_registros(
        client,
        nome_backup,
    )

    total_raw = contar_registros(
        client,
        config["raw"],
    )

    if total_backup != total_raw:
        raise RuntimeError(
            f"Backup de {fonte} não corresponde "
            "à quantidade atual da Bronze."
        )

    logger.info(
        "%s | Backup conferido: %s registros",
        fonte.upper(),
        total_backup,
    )


def verificar_promocao(client, fonte, config):
    campos = ", ".join(config["campos"])

    raw = tabela(config["raw"])
    candidata = tabela(config["candidata"])

    sql = f"""
        WITH diferencas AS (
            SELECT {campos}
            FROM `{raw}`

            EXCEPT DISTINCT

            SELECT {campos}
            FROM `{candidata}`
        ),
        diferencas_inversas AS (
            SELECT {campos}
            FROM `{candidata}`

            EXCEPT DISTINCT

            SELECT {campos}
            FROM `{raw}`
        )
        SELECT
            (SELECT COUNT(*) FROM diferencas)
                AS divergencias_raw,
            (SELECT COUNT(*) FROM diferencas_inversas)
                AS divergencias_candidata
    """

    resultado = next(
        iter(executar(client, sql))
    )

    total_raw = contar_registros(
        client,
        config["raw"],
    )

    total_candidata = contar_registros(
        client,
        config["candidata"],
    )

    if (
        total_raw != total_candidata
        or resultado.divergencias_raw > 0
        or resultado.divergencias_candidata > 0
    ):
        raise RuntimeError(
            f"Falha na conferência da promoção: {fonte}"
        )

    logger.info(
        "%s | Promoção validada: %s registros",
        fonte.upper(),
        total_raw,
    )


def main():
    logger.info("Iniciando validação para promoção")

    client = bigquery.Client(
        project=PROJECT_ID,
        location=BIGQUERY_LOCATION,
    )

    sqls = {}

    # Todas as verificações iniciais acontecem
    # antes de modificar qualquer tabela oficial.
    for fonte, config in FONTES.items():
        sqls[fonte] = preparar_sql(fonte, config)

        if not validar_fonte(client, fonte):
            raise RuntimeError(
                f"Auditoria reprovada: {fonte}"
            )

        verificar_backup(client, fonte, config)

    logger.info(
        "Verificações iniciais aprovadas"
    )

    for fonte, config in FONTES.items():
        logger.info(
            "%s | Promovendo tabela candidata",
            fonte.upper(),
        )

        executar(client, sqls[fonte])

        verificar_promocao(
            client,
            fonte,
            config,
        )

    logger.info(
        "Todas as tabelas Bronze foram atualizadas"
    )


if __name__ == "__main__":
    main()
