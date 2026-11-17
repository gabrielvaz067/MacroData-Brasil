
import logging

from datetime import datetime, timezone

from google.cloud import bigquery

from config import (
    PROJECT_ID,
    BIGQUERY_LOCATION,
    TABELAS_BRONZE,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def criar_cliente():
    return bigquery.Client(
        project=PROJECT_ID,
        location=BIGQUERY_LOCATION,
    )


def contar_registros(client, tabela):
    consulta = f"""
        SELECT COUNT(*) AS total
        FROM `{tabela}`
    """

    resultado = client.query(
        consulta,
        location=BIGQUERY_LOCATION,
    ).result()

    return next(iter(resultado)).total


def criar_backup(client, fonte, identificador):
    tabela_origem = TABELAS_BRONZE[fonte]

    tabela_destino = (
        f"{PROJECT_ID}.bronze."
        f"backup_{fonte}_{identificador}"
    )

    total_origem = contar_registros(
        client,
        tabela_origem,
    )

    logger.info(
        "%s | Criando backup de %s registros",
        fonte.upper(),
        total_origem,
    )

    configuracao = bigquery.CopyJobConfig(
        write_disposition=(
            bigquery.WriteDisposition.WRITE_EMPTY
        )
    )

    job = client.copy_table(
        sources=tabela_origem,
        destination=tabela_destino,
        job_config=configuracao,
        location=BIGQUERY_LOCATION,
    )

    job.result()

    total_backup = contar_registros(
        client,
        tabela_destino,
    )

    if total_backup != total_origem:
        raise RuntimeError(
            f"Falha na validação do backup de {fonte}: "
            f"origem={total_origem}, "
            f"backup={total_backup}"
        )

    logger.info(
        "%s | Backup validado: %s",
        fonte.upper(),
        tabela_destino,
    )

    return tabela_destino


def main():
    logger.info("Iniciando backup da Bronze")

    client = criar_cliente()

    identificador = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S_%f")

    backups = {}

    for fonte in ("selic", "cambio", "ipca"):
        backups[fonte] = criar_backup(
            client,
            fonte,
            identificador,
        )

    logger.info("Backups concluídos com sucesso")

    for fonte, tabela in backups.items():
        logger.info(
            "%s | %s",
            fonte.upper(),
            tabela,
        )

    logger.info(
        "Nenhuma tabela Bronze oficial foi alterada"
    )


if __name__ == "__main__":
    main()
