"""Grava (ou atualiza) uma obra na tabela obras."""

from database import obter_conexao


def inserir_obra(obra):

    conexao = obter_conexao()

    try:

        cursor = conexao.cursor()


        sql = """
        INSERT INTO obras (

            codigo,

            secretaria,
            descricao,
            logradouro,
            intervencao,
            situacao,

            valor_contratado,
            valor_executado,
            saldo_contrato,
            pct_executado,

            num_licitacao,
            num_contrato,
            num_ordem_servico,

            tipo_recurso,

            data_contrato,
            inicio_obra,
            limite_execucao,
            termino_contrato,

            empresa_executora,
            cnpj_empresa,
            fiscal_obra

        )

        VALUES (

            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,
            %s,%s,%s,
            %s,
            %s,%s,%s,%s,
            %s,%s,%s

        )


        ON DUPLICATE KEY UPDATE


            secretaria = VALUES(secretaria),
            descricao = VALUES(descricao),
            logradouro = VALUES(logradouro),
            intervencao = VALUES(intervencao),
            situacao = VALUES(situacao),

            valor_contratado = VALUES(valor_contratado),
            valor_executado = VALUES(valor_executado),
            saldo_contrato = VALUES(saldo_contrato),
            pct_executado = VALUES(pct_executado),

            num_licitacao = VALUES(num_licitacao),
            num_contrato = VALUES(num_contrato),
            num_ordem_servico = VALUES(num_ordem_servico),

            tipo_recurso = VALUES(tipo_recurso),

            data_contrato = VALUES(data_contrato),
            inicio_obra = VALUES(inicio_obra),
            limite_execucao = VALUES(limite_execucao),
            termino_contrato = VALUES(termino_contrato),

            empresa_executora = VALUES(empresa_executora),
            cnpj_empresa = VALUES(cnpj_empresa),
            fiscal_obra = VALUES(fiscal_obra)

        """



        valores = (

            obra.get("codigo"),

            obra.get("secretaria"),
            obra.get("descricao"),
            obra.get("logradouro"),
            obra.get("intervencao"),
            obra.get("situacao"),

            obra.get("valor_contratado"),
            obra.get("valor_executado"),
            obra.get("saldo_contrato"),
            obra.get("pct_executado"),

            obra.get("num_licitacao"),
            obra.get("num_contrato"),
            obra.get("num_ordem_servico"),

            obra.get("tipo_recurso"),

            obra.get("data_contrato"),
            obra.get("inicio_obra"),
            obra.get("limite_execucao"),
            obra.get("termino_contrato"),

            obra.get("empresa_executora"),
            obra.get("cnpj_empresa"),
            obra.get("fiscal_obra")

        )



        cursor.execute(
            sql,
            valores
        )


        conexao.commit()


        print(
            f"Obra {obra['codigo']} inserida com sucesso"
        )



    except Exception as erro:


        conexao.rollback()


        print(
            "Erro ao inserir:",
            erro
        )



    finally:

        conexao.close()




if __name__ == "__main__":


    teste = {

        "codigo": "9999",
        "secretaria": "TESTE",
        "descricao": "Teste",
        "logradouro": "Rua Teste",
        "intervencao": "Projeto",
        "situacao": "EM ANDAMENTO"

    }


    inserir_obra(teste)
