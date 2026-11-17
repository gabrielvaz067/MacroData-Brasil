
import argparse
import logging

from datetime import datetime, timezone

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from config import (
    PROJECT_ID,
    BIGQUERY_LOCATION,
    TABELAS_BRONZE,
)
from pipeline import main as atualizar_candidatas
from validar_promocao import validar_fonte
from promover_bronze import (
    FONTES,
    preparar_sql,
    executar,
    verificar_promocao,
)
from atualizar_camadas import (
    preparar_transformacoes,
    atualizar_camadas,
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


def verificar_configuracao(client):
    sqls_promocao = {}

    for fonte, config in FONTES.items():
        sqls_promocao[fonte] = preparar_sql(
            fonte, config
        )

    preparar_transformacoes(client)

    logger.info("Configuração validada")

    return sqls_promocao


def contar_registros(client, tabela):
    sql = f"""
        SELECT COUNT(*) AS total
        FROM `{tabela}`
    """

    return next(iter(executar(client, sql))).total


def copiar_tabela(client, origem, destino, sobrescrever=False):
    modo = (
        bigquery.WriteDisposition.WRITE_TRUNCATE
        if sobrescrever
        else bigquery.WriteDisposition.WRITE_EMPTY
    )

    config = bigquery.CopyJobConfig(
        write_disposition=modo,
    )

    job = client.copy_table(
        sources=origem,
        destination=destino,
        job_config=config,
        location=BIGQUERY_LOCATION,
    )

    job.result()

    total_origem = contar_registros(client, origem)
    total_destino = contar_registros(client, destino)

    if total_origem != total_destino:
        raise RuntimeError(
            f"Backup inconsistente: {destino}. "
            f"Origem: {total_origem}, "
            f"destino: {total_destino}"
        )

    logger.info(
        "Backup validado: %s | %s registros",
        destino,
        total_destino,
    )


def criar_backups(client):
    agora = datetime.now(timezone.utc)
    ano, semana, _ = agora.isocalendar()

    backups = {}

    for fonte in FONTES:
        origem = TABELAS_BRONZE[fonte]

        recuperacao = (
            f"{PROJECT_ID}.bronze."
            f"backup_{fonte}_recuperacao"
        )

        semanal = (
            f"{PROJECT_ID}.bronze."
            f"backup_{fonte}_semanal_{ano}_w{semana:02d}"
        )

        copiar_tabela(
            client,
            origem,
            recuperacao,
            sobrescrever=True,
        )

        logger.info(
            "%s | Backup de recuperação atualizado",
            fonte.upper(),
        )

        try:
            tabela_semanal = client.get_table(semanal)
        except NotFound:
            tabela_semanal = None

        if tabela_semanal is None:
            copiar_tabela(
                client,
                origem,
                semanal,
            )

            logger.info(
                "%s | Backup semanal criado",
                fonte.upper(),
            )
        else:
            total = contar_registros(client, semanal)

            if total == 0:
                raise RuntimeError(
                    f"Backup semanal vazio: {semanal}"
                )

            logger.info(
                "%s | Backup semanal já existe",
                fonte.upper(),
            )

        backups[fonte] = {
            "recuperacao": recuperacao,
            "semanal": semanal,
        }

    return backups


def executar_pipeline():
    client = criar_cliente()

    logger.info("Iniciando MacroData Brasil")

    sqls_promocao = verificar_configuracao(client)

    atualizar_candidatas()

    logger.info("Validando tabelas candidatas")

    for fonte in FONTES:
        if not validar_fonte(client, fonte):
            raise RuntimeError(
                f"Auditoria reprovada: {fonte}"
            )

    logger.info("Criando pontos de recuperação")

    backups = criar_backups(client)

    logger.info("Promovendo dados para a Bronze")

    for fonte, config in FONTES.items():
        executar(
            client,
            sqls_promocao[fonte],
        )

        verificar_promocao(
            client,
            fonte,
            config,
        )

        logger.info(
            "%s | Promoção concluída",
            fonte.upper(),
        )

    atualizar_camadas()

    logger.info("Pipeline completo executado com sucesso")

    for fonte, tabelas in backups.items():
        logger.info(
            "%s | Recuperação: %s",
            fonte.upper(),
            tabelas["recuperacao"],
        )

        logger.info(
            "%s | Semanal: %s",
            fonte.upper(),
            tabelas["semanal"],
        )


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline MacroData Brasil"
    )

    parser.add_argument(
        "--verificar",
        action="store_true",
        help="Verifica os SQLs sem modificar dados",
    )

    argumentos = parser.parse_args()

    if argumentos.verificar:
        client = criar_cliente()

        verificar_configuracao(client)

        logger.info(
            "Verificação concluída sem modificar tabelas"
        )
        return

    executar_pipeline()


if __name__ == "__main__":
    main()
