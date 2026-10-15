"""Scraper do portal EngeGov da Prefeitura de Blumenau (JSF/PrimeFaces).

O portal guarda o estado da página no campo oculto javax.faces.ViewState. Cada busca
é um POST AJAX que devolve XML com trechos de HTML dentro e um ViewState novo, que
precisa ser enviado na requisição seguinte.
"""

import re

import requests
import urllib3
from bs4 import BeautifulSoup

# O certificado do portal não passa na verificação do requests (veja o README)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SITE = "https://engegov.blumenau.sc.gov.br"
URL = f"{SITE}/portal-engegov/dashboard.xhtml?cidade=4898"
TEMPO_LIMITE = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

CABECALHOS_AJAX = {
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Origin": SITE,
    "Referer": URL,
    "User-Agent": USER_AGENT,
}

TABELA = "frmListaObras:tblListaObras"
PAINEIS_DETALHE = "frmAndamentoObra frmDadosContratoObra frmDadosMedicoesObra frmInfObraEmRevisao"


# --- Conversões --------------------------------------------------------------

def limpar_texto(valor):
    if not valor:
        return None
    valor = valor.strip()
    if valor in ("", "Não Cadastrado", "Não Cadastrado!"):
        return None
    return valor


def converter_valor(valor):
    """'R$ 1.234.567,89' -> 1234567.89. Sem valor, devolve 0."""
    if not valor:
        return 0
    valor = re.sub(r"\s", "", valor).replace("R$", "").replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return 0


def converter_data(valor):
    """'31/12/2025' -> '2025-12-31', o formato do MySQL.

    O portal tem algumas datas digitadas errado, como 16/05/0202. Essas viram None.
    """
    encontrada = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", (valor or "").strip())
    if not encontrada:
        return None
    dia, mes, ano = encontrada.groups()
    if not 1990 <= int(ano) <= 2100:
        return None
    return f"{ano}-{mes}-{dia}"


# --- Sessão e requisições ------------------------------------------------------

def iniciar_sessao():
    """Abre a página inicial e devolve a sessão e o primeiro ViewState."""
    sessao = requests.Session()
    resposta = sessao.get(URL, headers={"User-Agent": USER_AGENT}, verify=False, timeout=TEMPO_LIMITE)
    resposta.raise_for_status()

    campo = BeautifulSoup(resposta.text, "html.parser").find("input", {"name": "javax.faces.ViewState"})
    if not campo:
        raise RuntimeError("ViewState não encontrado na página inicial do portal")
    print("Sessão iniciada")
    return sessao, campo["value"]


def atualizar_viewstate(xml):
    for update in BeautifulSoup(xml, "xml").find_all("update"):
        if "ViewState" in update.get("id", ""):
            return update.text.strip()
    return None


def _post_ajax(sessao, viewstate, dados):
    """Envia o POST AJAX e devolve o XML da resposta e o ViewState atualizado."""
    dados = {**dados, "javax.faces.partial.ajax": "true", "frmListaObras": "frmListaObras",
             "javax.faces.ViewState": viewstate}
    resposta = sessao.post(URL, data=dados, headers=CABECALHOS_AJAX, verify=False, timeout=TEMPO_LIMITE)
    resposta.raise_for_status()
    return resposta.text, atualizar_viewstate(resposta.text) or viewstate


def _html_do_update(xml, id_parcial):
    """Devolve o HTML de dentro do <update> cujo id contém id_parcial."""
    for update in BeautifulSoup(xml, "xml").find_all("update"):
        if id_parcial in update.get("id", ""):
            return update.text
    return None


# --- Busca na tabela de obras --------------------------------------------------

def buscar_obra(sessao, viewstate, codigo):
    """Filtra a tabela do portal pelo código e lê a linha da obra."""
    dados = {
        "javax.faces.source": TABELA,
        "javax.faces.partial.execute": TABELA,
        "javax.faces.partial.render": TABELA,
        TABELA: TABELA,
        f"{TABELA}_filtering": "true",
        f"{TABELA}_encodeFeature": "true",
        f"{TABELA}_reflowDD": "0_0",
        f"{TABELA}:teste:filter": codigo,  # filtro da coluna Código
        f"{TABELA}:comboSecretarias_focus": "",
        f"{TABELA}:comboSecretarias_input": "",
        f"{TABELA}:j_idt122:filter": "",
        f"{TABELA}:j_idt124:filter": "",
        f"{TABELA}:j_idt126:filter": "",
        f"{TABELA}:j_idt128:filter": "",
        f"{TABELA}_selection": "",
    }
    xml, viewstate = _post_ajax(sessao, viewstate, dados)
    return ler_linha_da_tabela(xml, codigo), viewstate


def ler_linha_da_tabela(xml, codigo):
    html = _html_do_update(xml, "tblListaObras")
    if html is None:
        return None

    for linha in BeautifulSoup(html, "html.parser").find_all("tr"):
        colunas = [td.get_text(strip=True) for td in linha.find_all("td")]
        if len(colunas) >= 6 and colunas[0] == codigo:
            return dict(zip(
                ["codigo", "secretaria", "descricao", "logradouro", "intervencao", "situacao"],
                colunas[:6],
            ))
    return None


def clicar_obra(sessao, viewstate, codigo):
    """Simula o clique na linha da obra, que abre os painéis de contrato e andamento."""
    dados = {
        "javax.faces.source": TABELA,
        "javax.faces.partial.execute": TABELA,
        "javax.faces.partial.render": PAINEIS_DETALHE,
        "javax.faces.behavior.event": "rowSelect",
        "javax.faces.partial.event": "rowSelect",
        f"{TABELA}_instantSelectedRowKey": codigo,
        f"{TABELA}_selection": codigo,
    }
    return _post_ajax(sessao, viewstate, dados)


# --- Leitura dos painéis de detalhe -------------------------------------------
#
# Painel de contrato: cada campo é um par de <label class="ui-outputlabel">, o rótulo
# ("Término Contrato:") seguido do valor ("06/09/2025").
# Painel de andamento: cada valor é um <span> logo depois de <span class="icon-label">,
# e o percentual executado fica no atributo value do <input> do gráfico circular (knob).
# Os rótulos do HTML têm quebras de linha no meio ("Valor\n\t\tExecutado"), por isso
# os espaços são normalizados antes da comparação.

CAMPOS_CONTRATO = {
    "Empresa": "empresa_executora",
    "CNPJ": "cnpj_empresa",
    "Nº Processo Licitatório": "num_licitacao",
    "Número do Contrato": "num_contrato",
    "Nº Ordem de Serviço": "num_ordem_servico",
    "Tipo de Recurso": "tipo_recurso",
}
DATAS_CONTRATO = {
    "Data do Contrato": "data_contrato",
    "Início da obra": "inicio_obra",
    "Data Limite Execução": "limite_execucao",
    "Término Contrato": "termino_contrato",
}


def _normalizar(texto):
    return re.sub(r"\s+", " ", texto).strip()


def _painel(xml, id_painel):
    html = _html_do_update(xml, id_painel)
    return BeautifulSoup(html, "html.parser") if html is not None else None


def extrair_contrato(xml):
    painel = _painel(xml, "frmDadosContratoObra")
    if painel is None:
        return {}

    textos = [_normalizar(label.get_text()) for label in painel.select("label.ui-outputlabel")]
    campos = {}
    for rotulo, valor in zip(textos, textos[1:]):
        if rotulo.endswith(":") and not valor.endswith(":"):
            campos[rotulo.rstrip(":").strip()] = valor

    dados = {coluna: limpar_texto(campos.get(rotulo)) for rotulo, coluna in CAMPOS_CONTRATO.items()}
    for rotulo, coluna in DATAS_CONTRATO.items():
        dados[coluna] = converter_data(limpar_texto(campos.get(rotulo)))
    if campos.get("Valor Total Contratado"):
        dados["valor_contratado"] = converter_valor(campos["Valor Total Contratado"])
    return dados


def extrair_andamento(xml):
    painel = _painel(xml, "frmAndamentoObra")
    if painel is None:
        return {}

    valores = {}
    for rotulo in painel.select("span.icon-label"):
        valor = rotulo.find_next_sibling("span")
        if valor is not None:
            valores[_normalizar(rotulo.get_text())] = valor.get_text()

    dados = {"valor_executado": converter_valor(valores.get("Valor Executado (Medido)"))}
    if valores.get("Valor Total Contratado"):
        dados["valor_contratado"] = converter_valor(valores["Valor Total Contratado"])
        dados["saldo_contrato"] = converter_valor(valores.get("Saldo do Contrato"))

    knob = painel.select_one(".knob-container input")
    try:
        dados["pct_executado"] = float(knob["value"])
    except (TypeError, KeyError, ValueError):
        dados["pct_executado"] = 0
    return dados


def buscar_obra_completa(sessao, viewstate, codigo):
    """Busca a obra na tabela e, se encontrar, abre os detalhes de contrato e andamento."""
    obra, viewstate = buscar_obra(sessao, viewstate, codigo)
    if not obra:
        return None, viewstate

    detalhes, viewstate = clicar_obra(sessao, viewstate, codigo)
    obra.update(extrair_contrato(detalhes))
    obra.update(extrair_andamento(detalhes))

    obra.setdefault("valor_executado", 0)
    obra.setdefault("pct_executado", 0)
    obra.setdefault("saldo_contrato", obra.get("valor_contratado", 0))
    obra.setdefault("fiscal_obra", None)
    return obra, viewstate
