"""Salva as respostas do portal para uma ou mais obras, para conferir o HTML e montar testes.

Uso (a partir da raiz do projeto):
    python backend/salvar_resposta.py 3693 3657

Cria, para cada código, o arquivo resposta_<codigo>_detalhe.xml com a resposta do clique na obra.
"""

import sys

from scraper import buscar_obra, clicar_obra, iniciar_sessao

if __name__ == "__main__":
    sessao, viewstate = iniciar_sessao()
    for codigo in sys.argv[1:]:
        obra, viewstate = buscar_obra(sessao, viewstate, codigo)
        if not obra:
            print(f"{codigo}: não encontrada no portal")
            continue
        detalhes, viewstate = clicar_obra(sessao, viewstate, codigo)
        with open(f"resposta_{codigo}_detalhe.xml", "w", encoding="utf-8") as arquivo:
            arquivo.write(detalhes)
        print(f"{codigo}: salvo resposta_{codigo}_detalhe.xml ({len(detalhes)} caracteres)")
