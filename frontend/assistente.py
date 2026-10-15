"""Responde perguntas em português sobre as obras.

Com GROQ_API_KEY no .env, um modelo de linguagem (Llama 3.3, pela Groq) lê a pergunta e escolhe
uma das consultas abaixo, com os parâmetros. Sem a chave, ou se a Groq não responder, a escolha é
feita por palavras-chave, o que funciona sem internet. Nos dois casos os números saem do pandas,
calculados sobre os dados do banco: o modelo escolhe a consulta, não escreve os valores.
"""

import json
import os
import re
from dataclasses import dataclass

import pandas as pd

import formatar
from dados import CONCLUIDA, EM_ANDAMENTO, PARALISADA
from formatar import sem_acento
from prazos import avaliar_prazos, obras_em_atencao

EXEMPLOS = [
    "Quantas obras estão atrasadas?",
    "Quais obras estão paralisadas?",
    "Qual secretaria tem mais obras?",
    "Quanto já foi investido?",
    "De onde vem o dinheiro das obras?",
    "Quais empresas têm mais contratos?",
    "Me mostre a obra 3657",
]

# Trecho da palavra (sem acento) -> situação no portal
SITUACOES = {
    "paralisad": PARALISADA, "parad": PARALISADA,
    "andamento": EM_ANDAMENTO, "execucao": EM_ANDAMENTO,
    "conclu": CONCLUIDA, "termin": CONCLUIDA, "finaliz": CONCLUIDA, "entregue": CONCLUIDA,
}
NO_PLURAL = {PARALISADA: "paralisadas", EM_ANDAMENTO: "em andamento", CONCLUIDA: "concluídas"}


def contar(qtd, situacao):
    """'1 obra está paralisada', '7 obras estão paralisadas'."""
    if qtd == 1:
        return f"1 obra está {situacao.lower()}"
    return f"{qtd} obras estão {NO_PLURAL[situacao]}"


@dataclass
class Resposta:
    texto: str
    tabela: pd.DataFrame | None = None
    fonte: str = ""  # como a pergunta foi entendida, mostrado abaixo da resposta


# --- Consultas -------------------------------------------------------------

def resumo(df, _):
    contagem = df["situacao"].value_counts()
    partes = ", ".join(f"{qtd} {NO_PLURAL.get(sit, sit.lower())}" for sit, qtd in contagem.items())
    return Resposta(
        f"São {len(df)} obras: {partes}. O valor contratado soma "
        f"{formatar.moeda(df['valor_contratado'].sum())}."
    )


def por_situacao(df, params):
    situacao = params.get("situacao")
    obras = df[df["situacao"] == situacao]
    texto = contar(len(obras), situacao) + "."
    if params.get("so_contar") or obras.empty:
        return Resposta(texto)
    return Resposta(texto, _tabela(obras))


def atrasadas(df, _):
    avaliadas = avaliar_prazos(df)
    vencidas = obras_em_atencao(avaliadas[avaliadas["prazo_vencido"]])
    texto = f"{len(vencidas)} obras não concluídas já passaram do prazo do contrato."
    if vencidas.empty:
        return Resposta(texto)
    tabela = vencidas.assign(
        prazo_final=vencidas["prazo_final"].map(formatar.data),
        dias_vencido=vencidas["dias_vencido"].astype(int),
    )[["codigo", "descricao", "situacao", "prazo_final", "dias_vencido"]].rename(
        columns={"codigo": "Código", "descricao": "Descrição", "situacao": "Situação",
                 "prazo_final": "Prazo final", "dias_vencido": "Dias de atraso"})
    return Resposta(texto, tabela)


def ranking_secretarias(df, params):
    if params.get("metrica") == "valor":
        soma = df.groupby("secretaria")["valor_contratado"].sum().sort_values(ascending=False)
        primeira = soma.index[0]
        texto = f"{primeira} é a secretaria com mais valor contratado: {formatar.moeda(soma.iloc[0])}."
        tabela = soma.map(formatar.moeda).rename("Valor contratado")
    else:
        contagem = df["secretaria"].value_counts()
        texto = f"{contagem.index[0]} é a secretaria com mais obras: {contagem.iloc[0]}."
        tabela = contagem.rename("Obras")
    return Resposta(texto, tabela.rename_axis("Secretaria").reset_index())


def ranking_empresas(df, _):
    agrupado = (
        df.dropna(subset=["empresa_executora"])
        .groupby("empresa_executora")
        .agg(Obras=("codigo", "count"), Valor=("valor_contratado", "sum"))
        .sort_values(["Obras", "Valor"], ascending=False)
        .head(10)
    )
    if agrupado.empty:
        return Resposta("Nenhuma obra tem a empresa executora cadastrada.")
    primeira = agrupado.index[0]
    texto = f"{primeira} é a empresa com mais obras: {agrupado['Obras'].iloc[0]}."
    agrupado["Valor"] = agrupado["Valor"].map(formatar.moeda)
    return Resposta(texto, agrupado.rename_axis("Empresa").reset_index())


def investimento(df, _):
    contratado = df["valor_contratado"].sum()
    executado = df["valor_executado"].sum()
    pct = executado / contratado * 100 if contratado else 0
    return Resposta(
        f"O valor contratado soma {formatar.moeda(contratado)}. Já foram executados "
        f"{formatar.moeda(executado)} ({pct:.0f}%), e o saldo a executar é "
        f"{formatar.moeda(contratado - executado)}."
    )


def por_recurso(df, _):
    origem = df["tipo_recurso"].fillna("Não informado").str.split(" / ").str[0]
    soma = df.groupby(origem)["valor_contratado"].sum().sort_values(ascending=False)
    total = soma.sum()
    primeira = soma.index[0]
    texto = (f"A maior parte do valor contratado vem de {primeira.lower()}: "
             f"{formatar.moeda(soma.iloc[0])} ({soma.iloc[0] / total * 100:.0f}% do total).")
    tabela = pd.DataFrame({"Origem do recurso": soma.index, "Valor contratado": soma.map(formatar.moeda).values,
                           "% do total": (soma / total * 100).round(0).astype(int).values})
    return Resposta(texto, tabela)


def detalhe_obra(df, params):
    codigo = params.get("codigo", "").upper()
    obra = df[df["codigo"].str.upper() == codigo]
    if obra.empty:
        return Resposta(f"Não encontrei a obra {codigo} entre as obras filtradas.")
    o = obra.iloc[0]
    local = o["logradouro"] if pd.notna(o["logradouro"]) else "local não informado"
    return Resposta(
        f"Obra {o['codigo']}: {o['descricao']} ({local}). "
        f"Situação: {o['situacao'].lower()}, {formatar.percentual(o['pct_executado'])} executado. "
        f"Contratado: {formatar.moeda(o['valor_contratado'])}. "
        f"Prazo final: {formatar.data(o['prazo_final'])}."
    )


CONSULTAS = {
    "resumo": resumo,
    "por_situacao": por_situacao,
    "atrasadas": atrasadas,
    "ranking_secretarias": ranking_secretarias,
    "ranking_empresas": ranking_empresas,
    "investimento": investimento,
    "por_recurso": por_recurso,
    "detalhe_obra": detalhe_obra,
}


def _tabela(obras):
    return obras[["codigo", "secretaria", "descricao", "pct_executado"]].rename(
        columns={"codigo": "Código", "secretaria": "Secretaria",
                 "descricao": "Descrição", "pct_executado": "% executado"})


# --- Escolha da consulta ---------------------------------------------------

def por_palavras_chave(pergunta):
    """Devolve (consulta, parâmetros) ou None se nenhuma regra servir."""
    p = sem_acento(pergunta)

    codigo = re.search(r"\b(c?\d{3,5})\b", p)
    if codigo and "obra" in p:
        return "detalhe_obra", {"codigo": codigo.group(1)}
    if "atrasad" in p or "vencid" in p or "fora do prazo" in p:
        return "atrasadas", {}
    for trecho, situacao in SITUACOES.items():
        if trecho in p:
            return "por_situacao", {"situacao": situacao, "so_contar": p.startswith("quant")}
    if re.search(r"de onde vem|origem|fonte|tipo de recurso|recursos? ", p + " "):
        return "por_recurso", {}
    if "empresa" in p or "construtora" in p:
        return "ranking_empresas", {}
    if "secretaria" in p:
        metrica = "valor" if re.search(r"valor|invest|dinheiro|gast", p) else "quantidade"
        return "ranking_secretarias", {"metrica": metrica}
    if re.search(r"invest|gast|valor|dinheiro|executad", p):
        return "investimento", {}
    if re.search(r"resumo|geral|quantas obras|total de obras", p):
        return "resumo", {}
    return None


PROMPT_GROQ = """Você recebe perguntas sobre as obras públicas de Blumenau e escolhe UMA consulta.
Responda só com JSON no formato {"consulta": "...", "params": {...}}.

Consultas:
- resumo: visão geral das obras
- por_situacao: lista ou conta obras de uma situação.
  params {"situacao": "EM ANDAMENTO" | "PARALISADA" | "CONCLUÍDA", "so_contar": true | false}
- atrasadas: obras não concluídas com o prazo do contrato vencido
- ranking_secretarias: params {"metrica": "quantidade" | "valor"}
- ranking_empresas: empresas com mais obras
- investimento: valores contratado, executado e saldo
- por_recurso: de onde vem o dinheiro (recurso próprio, empréstimo, transferência...)
- detalhe_obra: params {"codigo": "código da obra, como 3657 ou C1002"}
- nenhuma: a pergunta não tem relação com as consultas acima

Exemplos:
"tem alguma obra parada?" -> {"consulta": "por_situacao", "params": {"situacao": "PARALISADA", "so_contar": false}}
"quantas já terminaram?" -> {"consulta": "por_situacao", "params": {"situacao": "CONCLUÍDA", "so_contar": true}}
"qual secretaria gastou mais?" -> {"consulta": "ranking_secretarias", "params": {"metrica": "valor"}}
"quanto a prefeitura pegou emprestado?" -> {"consulta": "por_recurso", "params": {}}
"qual a previsão do tempo?" -> {"consulta": "nenhuma", "params": {}}"""

MODELO_GROQ = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def pela_groq(pergunta):
    """Devolve (consulta, parâmetros) escolhidos pelo modelo, ou None para "nenhuma"."""
    from groq import Groq  # só é importado se a chave estiver configurada

    cliente = Groq(api_key=os.environ["GROQ_API_KEY"])
    resposta = cliente.chat.completions.create(
        model=MODELO_GROQ,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": PROMPT_GROQ},
                  {"role": "user", "content": pergunta}],
    )
    escolha = json.loads(resposta.choices[0].message.content)
    if escolha.get("consulta") not in CONSULTAS:
        return None
    return escolha["consulta"], escolha.get("params") or {}


def tem_chave_groq():
    # o .env.example antigo trazia um texto de exemplo no lugar da chave
    return os.getenv("GROQ_API_KEY", "") not in ("", "sua-chave-groq-aqui")


def _ajustar_parametros(consulta, params):
    """O modelo pode devolver 'paralisada' ou o código como número; aqui tudo vira o formato esperado."""
    params = dict(params)
    if consulta == "por_situacao":
        texto = sem_acento(params.get("situacao") or "")
        params["situacao"] = next((s for trecho, s in SITUACOES.items() if trecho in texto), None)
        params["so_contar"] = bool(params.get("so_contar"))
    if consulta == "detalhe_obra":
        params["codigo"] = str(params.get("codigo", "")).strip()
    return params


def responder(pergunta, df):
    escolha, fonte = None, ""

    if tem_chave_groq():
        try:
            escolha = pela_groq(pergunta)
            fonte = f"Pergunta interpretada por IA ({MODELO_GROQ}, pela Groq)."
        except Exception as erro:  # sem internet, chave inválida, modelo fora do ar...
            fonte = f"A Groq não respondeu ({type(erro).__name__}), então usei as palavras-chave."

    if escolha is None:
        escolha = por_palavras_chave(pergunta)
        if escolha is not None:
            if not tem_chave_groq():
                fonte = "Pergunta interpretada por palavras-chave (sem chave da Groq no .env)."
            elif fonte.startswith("Pergunta interpretada por IA"):
                fonte = "A IA não reconheceu a pergunta, então usei as palavras-chave."

    if escolha is None:
        return Resposta("Não entendi a pergunta. Tente algo como: " + "; ".join(EXEMPLOS) + ".",
                        fonte=fonte)

    consulta, params = escolha
    params = _ajustar_parametros(consulta, params)
    if consulta == "por_situacao" and params["situacao"] is None:
        consulta = "resumo"
    resposta = CONSULTAS[consulta](df, params)
    resposta.fonte = fonte
    return resposta
