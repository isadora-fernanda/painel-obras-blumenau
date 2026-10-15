"""Grava ou atualiza uma obra na tabela obras."""

from database import obter_conexao

CAMPOS = [
    "codigo", "secretaria", "descricao", "logradouro", "intervencao", "situacao",
    "valor_contratado", "valor_executado", "saldo_contrato", "pct_executado",
    "num_licitacao", "num_contrato", "num_ordem_servico", "tipo_recurso",
    "data_contrato", "inicio_obra", "limite_execucao", "termino_contrato",
    "empresa_executora", "cnpj_empresa", "fiscal_obra",
]

# A chave única em "codigo" faz o ON DUPLICATE KEY UPDATE atualizar a obra em vez de duplicar
SQL = (
    f"INSERT INTO obras ({', '.join(CAMPOS)}) "
    f"VALUES ({', '.join(['%s'] * len(CAMPOS))}) "
    "ON DUPLICATE KEY UPDATE "
    + ", ".join(f"{campo} = VALUES({campo})" for campo in CAMPOS[1:])
)


def inserir_obra(obra, conexao=None):
    """Grava a obra. Se nenhuma conexão for passada, abre e fecha uma só para esta obra."""
    propria = conexao is None
    conexao = conexao or obter_conexao()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(SQL, [obra.get(campo) for campo in CAMPOS])
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        if propria:
            conexao.close()
