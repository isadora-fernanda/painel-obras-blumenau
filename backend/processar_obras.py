"""Lê os códigos da planilha, busca cada obra no portal e grava no MySQL.

Rode a partir da raiz do projeto:
    python backend/processar_obras.py                  # grava no MySQL
    python backend/processar_obras.py --limite 5       # só as 5 primeiras, para testar
    python backend/processar_obras.py --csv obras.csv  # grava num CSV, sem precisar de MySQL
"""

import argparse
import re
import time

import pandas as pd

from scraper import buscar_obra_completa, iniciar_sessao

ARQUIVO_CODIGOS = "obras_disponiveis.xls"
PAUSA_SEGUNDOS = 0.5  # para não sobrecarregar o portal da prefeitura


def carregar_codigos(arquivo=ARQUIVO_CODIGOS):
    """Pega da primeira coluna só o que parece código de obra (3849, C1002...)."""
    planilha = pd.read_excel(arquivo, header=None, dtype=str)
    codigos = []
    for valor in planilha.iloc[:, 0].dropna():
        codigo = valor.strip().upper()
        if re.fullmatch(r"C?\d+", codigo):
            codigos.append(codigo)
    return codigos


class DestinoCsv:
    """Junta as obras e regrava o CSV a cada 20, para não perder a coleta se ela parar no meio."""

    def __init__(self, caminho):
        self.caminho, self.obras = caminho, []

    def gravar(self, obra):
        self.obras.append(obra)
        if len(self.obras) % 20 == 0:
            self.salvar()

    def salvar(self):
        pd.DataFrame(self.obras).to_csv(self.caminho, index=False, encoding="utf-8-sig")

    def fechar(self):
        if self.obras:
            self.salvar()
            print(f"CSV salvo em {self.caminho}")


class DestinoMysql:
    def __init__(self):
        # importados aqui para o modo CSV funcionar sem o MySQL instalado
        from database import obter_conexao
        from inserir_banco import inserir_obra

        self.conexao, self.inserir = obter_conexao(), inserir_obra

    def gravar(self, obra):
        self.inserir(obra, self.conexao)

    def fechar(self):
        self.conexao.close()


def processar_obras(limite=None, csv=None):
    codigos = carregar_codigos()[:limite]
    if not codigos:
        print(f"Nenhum código encontrado em {ARQUIVO_CODIGOS}")
        return

    print(f"{len(codigos)} códigos para buscar")
    destino = DestinoCsv(csv) if csv else DestinoMysql()
    sessao, viewstate = iniciar_sessao()
    gravadas, nao_encontradas, erros = 0, [], []

    try:
        for indice, codigo in enumerate(codigos, start=1):
            try:
                obra, viewstate = buscar_obra_completa(sessao, viewstate, codigo)
                if obra:
                    destino.gravar(obra)
                    gravadas += 1
                    print(f"[{indice}/{len(codigos)}] {codigo} gravada")
                else:
                    nao_encontradas.append(codigo)
                    print(f"[{indice}/{len(codigos)}] {codigo} não encontrada no portal")
            except Exception as erro:
                # Uma falha costuma invalidar o ViewState, então a sessão é aberta de novo
                erros.append(codigo)
                print(f"[{indice}/{len(codigos)}] {codigo} erro: {erro}. Recriando a sessão.")
                sessao, viewstate = iniciar_sessao()
            time.sleep(PAUSA_SEGUNDOS)
    finally:
        destino.fechar()

    print(f"\nFim: {gravadas} gravadas, {len(nao_encontradas)} não encontradas, {len(erros)} com erro.")
    if erros:
        print("Com erro:", ", ".join(erros))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta as obras do portal EngeGov de Blumenau")
    parser.add_argument("--limite", type=int, help="busca só as primeiras N obras")
    parser.add_argument("--csv", help="grava neste arquivo CSV em vez do MySQL")
    argumentos = parser.parse_args()
    processar_obras(argumentos.limite, argumentos.csv)
