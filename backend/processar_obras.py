"""Lê os códigos da planilha, busca cada obra no portal e grava no MySQL.

Rode a partir da raiz do projeto: python backend/processar_obras.py
"""

import re
import time
import pandas as pd


from scraper import (
    iniciar_sessao,
    buscar_obra_completa as buscar_obra
)


from inserir_banco import inserir_obra



ARQUIVO_CODIGOS = "obras_disponiveis.xls"

# Pausa entre consultas, para não sobrecarregar o portal da prefeitura
PAUSA_SEGUNDOS = 0.5





def carregar_codigos():

    try:

        df = pd.read_excel(
            ARQUIVO_CODIGOS,
            header=None,
            dtype=str
        )


        codigos = []


        for valor in df.iloc[:, 0]:


            if pd.isna(valor):

                continue



            codigo = str(valor).strip()



            if re.fullmatch(
                r"\d+|C\d+",
                codigo,
                re.IGNORECASE
            ):

                codigos.append(
                    codigo.upper()
                )



        return codigos



    except Exception as erro:


        print(
            "Erro lendo Excel:",
            erro
        )


        return []








def processar_obras():


    codigos = carregar_codigos()



    if not codigos:


        print(
            "Nenhum código encontrado"
        )

        return




    print(
        f"Total de códigos encontrados: {len(codigos)}"
    )



    session, viewstate = iniciar_sessao()





    for indice, codigo in enumerate(
        codigos,
        start=1
    ):


        print(
            "\n--------------------------------"
        )


        print(
            f"[{indice}/{len(codigos)}] Buscando código {codigo}"
        )



        try:


            obra, viewstate = buscar_obra(

                session,

                viewstate,

                codigo

            )



            if obra:


                print(
                    "Obra encontrada:"
                )


                print(
                    obra
                )



                inserir_obra(
                    obra
                )


                print(
                    f"✓ Obra {codigo} salva no banco"
                )



                time.sleep(PAUSA_SEGUNDOS)



            else:


                print(
                    f"✗ Obra {codigo} não encontrada"
                )


                # não reinicia sessão aqui
                # o ViewState continua válido


                time.sleep(PAUSA_SEGUNDOS)




        except Exception as erro:


            print(
                f"Erro na obra {codigo}: {erro}"
            )


            print(
                "Recriando sessão..."
            )



            session, viewstate = iniciar_sessao()



            time.sleep(PAUSA_SEGUNDOS)





    print(
        "\nProcessamento finalizado."
    )






if __name__ == "__main__":

    processar_obras()
