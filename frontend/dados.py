"""Leitura das obras no MySQL, preparo das colunas e filtros do painel."""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from formatar import sem_acento

# O painel usa a mesma conexão do backend (credenciais no .env)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from database import obter_conexao  # noqa: E402

COLUNAS_DATA = ["data_contrato", "inicio_obra", "limite_execucao", "termino_contrato"]
COLUNAS_NUMERO = ["valor_contratado", "valor_executado", "saldo_contrato", "pct_executado"]
COLUNAS_TEXTO = [
    "codigo", "secretaria", "descricao", "logradouro", "intervencao", "situacao",
    "empresa_executora", "cnpj_empresa", "num_licitacao", "num_contrato",
    "num_ordem_servico", "tipo_recurso",
]

CONCLUIDA = "CONCLUÍDA"
EM_ANDAMENTO = "EM ANDAMENTO"
PARALISADA = "PARALISADA"


def carregar_obras():
    """Lê do MySQL ou, se OBRAS_CSV estiver no .env, do CSV gerado com --csv na coleta."""
    arquivo = os.getenv("OBRAS_CSV")
    if arquivo:
        return preparar(pd.read_csv(arquivo, dtype=str, encoding="utf-8-sig"))
    return ler_banco()


def ler_banco():
    conexao = obter_conexao()
    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT * FROM obras")
            linhas = cursor.fetchall()
    finally:
        conexao.close()
    return preparar(pd.DataFrame(linhas))


def preparar(df):
    """Converte os tipos que vêm do MySQL (Decimal, date, texto com espaços)."""
    df = df.copy()
    # Uma coluna que nenhuma obra tem preenchida pode nem vir no CSV
    for coluna in COLUNAS_NUMERO + COLUNAS_DATA + COLUNAS_TEXTO:
        if coluna not in df:
            df[coluna] = pd.NA
    for coluna in COLUNAS_NUMERO:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    for coluna in COLUNAS_DATA:
        df[coluna] = pd.to_datetime(df[coluna], errors="coerce")
    for coluna in COLUNAS_TEXTO:
        df[coluna] = df[coluna].astype("string").str.strip().replace("", pd.NA)

    df["situacao"] = df["situacao"].str.upper()
    # O prazo final é o término do contrato ou, se ele não estiver cadastrado, a data limite de execução
    df["prazo_final"] = df["termino_contrato"].fillna(df["limite_execucao"])
    df["ano_contrato"] = df["data_contrato"].dt.year.astype("Int64")
    return df.sort_values("codigo").reset_index(drop=True)


@dataclass
class Filtros:
    busca: str = ""
    secretarias: list = field(default_factory=list)
    situacoes: list = field(default_factory=list)
    intervencoes: list = field(default_factory=list)
    anos: tuple | None = None  # (primeiro, último) ano do contrato


def aplicar_filtros(df, filtros):
    manter = pd.Series(True, index=df.index)

    if filtros.busca.strip():
        termo = sem_acento(filtros.busca.strip())
        texto = (
            df[["codigo", "descricao", "logradouro", "empresa_executora"]]
            .fillna("").astype(str).agg(" ".join, axis=1).map(sem_acento)
        )
        manter &= texto.str.contains(termo, regex=False)

    if filtros.secretarias:
        manter &= df["secretaria"].isin(filtros.secretarias)
    if filtros.situacoes:
        manter &= df["situacao"].isin(filtros.situacoes)
    if filtros.intervencoes:
        manter &= df["intervencao"].fillna("Não informada").isin(filtros.intervencoes)
    if filtros.anos:
        primeiro, ultimo = filtros.anos
        manter &= df["ano_contrato"].between(primeiro, ultimo).fillna(False)

    return df[manter]
