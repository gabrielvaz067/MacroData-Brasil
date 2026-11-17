
import logging

from google.cloud import bigquery

from config import (
    PROJECT_ID,
    BIGQUERY_LOCATION,
    TABELAS_BRONZE,
    TABELAS_STAGING,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def validar_fonte(client, fonte):
    nomes_candidatas = {
        "selic": "bcb_selic_candidata",
        "cambio": "bcb_cambio_candidata",
        "ipca": "ibge_ipca_candidata",
    }

    candidata = (
        f"{PROJECT_ID}.bronze."
        f"{nomes_candidatas[fonte]}"
    )

    bronze = TABELAS_BRONZE[fonte]
    staging = TABELAS_STAGING[fonte]

    if fonte == "ipca":
        chave = [
            "localidade",
            "codigo_indicador",
            "periodo",
        ]

        colunas = [
            "localidade",
            "codigo_indicador",
            "indicador",
            "periodo",
            "descricao_periodo",
            "valor",
            "unidade",
            "fonte",
        ]

        condicao_valida = """
            SAFE.PARSE_DATE('%Y%m', periodo) IS NOT NULL
            AND SAFE_CAST(valor AS NUMERIC) IS NOT NULL
            AND localidade = 'Brasil'
            AND codigo_indicador = '63'
        """
    else:
        chave = ["data"]

        colunas = [
            "data",
            "valor",
            "fonte",
        ]

        condicao_valida = """
            SAFE.PARSE_DATE('%d/%m/%Y', data) IS NOT NULL
            AND SAFE_CAST(valor AS NUMERIC) > 0
        """

    def executar(sql):
        resultado = client.query(
            sql,
            location=BIGQUERY_LOCATION,
        ).result()

        return next(iter(resultado))

    total_raw = executar(
        f"SELECT COUNT(*) AS total FROM `{bronze}`"
    ).total

    total_candidata = executar(
        f"SELECT COUNT(*) AS total FROM `{candidata}`"
    ).total

    chave_sql = ", ".join(chave)

    duplicados = executar(f"""
        SELECT COUNT(*) AS total
        FROM (
            SELECT {chave_sql}
            FROM `{candidata}`
            GROUP BY {chave_sql}
            HAVING COUNT(*) > 1
        )
    """).total

    invalidos = executar(f"""
        SELECT COUNT(*) AS total
        FROM `{candidata}`
        WHERE NOT ({condicao_valida})
    """).total

    # Compara os campos de negócio, ignorando a data
    # da extração, que muda a cada execução.
    campos = ", ".join(colunas)

    divergencias = executar(f"""
        SELECT COUNT(*) AS total
        FROM (
            SELECT {campos}
            FROM `{staging}`

            EXCEPT DISTINCT

            SELECT {campos}
            FROM `{candidata}`
        )
    """).total

    erros = []

    if total_candidata < total_raw:
        erros.append("Candidata menor que Bronze")

    if duplicados:
        erros.append(
            f"{duplicados} chaves duplicadas"
        )

    if invalidos:
        erros.append(
            f"{invalidos} registros inválidos"
        )

    if divergencias:
        erros.append(
            f"{divergencias} registros da staging "
            "não correspondem à candidata"
        )

    logger.info(
        "%s | Bronze: %s | Candidata: %s",
        fonte.upper(),
        total_raw,
        total_candidata,
    )

    if erros:
        for erro in erros:
            logger.error(
                "%s | %s",
                fonte.upper(),
                erro,
            )

        return False

    logger.info(
        "%s | Auditoria aprovada",
        fonte.upper(),
    )

    return True


def main():
    logger.info("Validando tabelas candidatas")

    client = bigquery.Client(
        project=PROJECT_ID,
        location=BIGQUERY_LOCATION,
    )

    resultados = {}

    for fonte in ("selic", "cambio", "ipca"):
        resultados[fonte] = validar_fonte(
            client,
            fonte,
        )

    if not all(resultados.values()):
        raise RuntimeError(
            "Existem divergências. "
            "Promoção não autorizada."
        )

    logger.info(
        "Todas as candidatas foram aprovadas."
    )
    logger.info(
        "Nenhuma tabela foi modificada."
    )


if __name__ == "__main__":
    main()
