"""Scraper do portal EngeGov da Prefeitura de Blumenau (JSF/PrimeFaces).

O portal guarda o estado da página no campo javax.faces.ViewState. Cada busca
é um POST AJAX que devolve XML com trechos de HTML e um ViewState novo.
"""

import re
import requests
import urllib3

from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning


urllib3.disable_warnings(
    InsecureRequestWarning
)


URL = (
    "https://engegov.blumenau.sc.gov.br/"
    "portal-engegov/dashboard.xhtml?cidade=4898"
)


HEADERS = {

    "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",

    "Accept":
    "text/html,application/xhtml+xml,"
    "application/xml;q=0.9,*/*;q=0.8"

}



def iniciar_sessao():

    session = requests.Session()

    resposta = session.get(
        URL,
        headers=HEADERS,
        verify=False,
        timeout=10
    )

    resposta.raise_for_status()

    soup = BeautifulSoup(
        resposta.text,
        "html.parser"
    )

    viewstate = soup.find(
        "input",
        {
            "name":
            "javax.faces.ViewState"
        }
    )

    if not viewstate:

        raise Exception(
            "ViewState não encontrado"
        )

    print(
        "✓ Sessão iniciada"
    )

    return (
        session,
        viewstate["value"]
    )





def atualizar_viewstate(xml):

    soup = BeautifulSoup(
        xml,
        "xml"
    )

    for update in soup.find_all(
        "update"
    ):

        if "ViewState" in update.get(
            "id",
            ""
        ):

            return update.text.strip()

    return None





def limpar_texto(valor):

    if not valor:

        return None


    valor = valor.strip()


    if valor in [
        "",
        "Não Cadastrado",
        "Não Cadastrado!"
    ]:

        return None


    return valor





def converter_valor(valor):

    if not valor:

        return 0


    valor = (
        valor
        .replace("R$", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )


    try:

        return float(valor)

    except:

        return 0





def converter_data(valor):

    if not valor:

        return None


    valor = valor.strip()


    if "/" in valor:

        try:

            dia, mes, ano = valor.split("/")

            return (
                f"{ano}-{mes}-{dia}"
            )

        except:

            return None


    return None





def buscar_obra(
    session,
    viewstate,
    codigo
):


    dados = {


        "javax.faces.partial.ajax":
        "true",


        "javax.faces.source":
        "frmListaObras:tblListaObras",


        "javax.faces.partial.execute":
        "frmListaObras:tblListaObras",


        "javax.faces.partial.render":
        "frmListaObras:tblListaObras",


        "frmListaObras":
        "frmListaObras",


        "frmListaObras:tblListaObras":
        "frmListaObras:tblListaObras",


        "frmListaObras:tblListaObras_filtering":
        "true",


        "frmListaObras:tblListaObras_encodeFeature":
        "true",


        "frmListaObras:tblListaObras_reflowDD":
        "0_0",


        "frmListaObras:tblListaObras:teste:filter":
        codigo,


        "frmListaObras:tblListaObras:comboSecretarias_focus":
        "",


        "frmListaObras:tblListaObras:comboSecretarias_input":
        "",


        "frmListaObras:tblListaObras:j_idt122:filter":
        "",


        "frmListaObras:tblListaObras:j_idt124:filter":
        "",


        "frmListaObras:tblListaObras:j_idt126:filter":
        "",


        "frmListaObras:tblListaObras:j_idt128:filter":
        "",


        "frmListaObras:tblListaObras_selection":
        "",


        "javax.faces.ViewState":
        viewstate

    }



    headers = {


        "Faces-Request":
        "partial/ajax",


        "X-Requested-With":
        "XMLHttpRequest",


        "Content-Type":
        "application/x-www-form-urlencoded; charset=UTF-8",


        "Accept":
        "application/xml, text/xml, */*; q=0.01",


        "Origin":
        "https://engegov.blumenau.sc.gov.br",


        "Referer":
        URL,


        "User-Agent":
        HEADERS["User-Agent"]

    }



    resposta = session.post(

        URL,

        data=dados,

        headers=headers,

        verify=False,

        timeout=10

    )


    resposta.raise_for_status()


    novo_viewstate = (

        atualizar_viewstate(
            resposta.text
        )

        or

        viewstate

    )


    xml = BeautifulSoup(
        resposta.text,
        "xml"
    )



    tabela = None


    for update in xml.find_all(
        "update"
    ):

        if "tblListaObras" in update.get(
            "id",
            ""
        ):

            tabela = update

            break



    if tabela is None:

        return (
            None,
            novo_viewstate
        )



    soup = BeautifulSoup(
        tabela.text,
        "html.parser"
    )



    for linha in soup.find_all(
        "tr"
    ):


        colunas = [

            td.get_text(
                strip=True
            )

            for td in linha.find_all(
                "td"
            )

        ]


        if len(colunas) < 6:

            continue



        print(
            "Linha encontrada:",
            colunas[:6]
        )



        if colunas[0] == codigo:


            obra = {

                "codigo":
                colunas[0],

                "secretaria":
                colunas[1],

                "descricao":
                colunas[2],

                "logradouro":
                colunas[3],

                "intervencao":
                colunas[4],

                "situacao":
                colunas[5]

            }


            return (
                obra,
                novo_viewstate
            )



    return (
        None,
        novo_viewstate
    )



def clicar_obra(
    session,
    viewstate,
    codigo
):


    dados = {


        "javax.faces.partial.ajax":
        "true",


        "javax.faces.source":
        "frmListaObras:tblListaObras",


        "javax.faces.partial.execute":
        "frmListaObras:tblListaObras",


        "javax.faces.partial.render":
        (
            "frmAndamentoObra "
            "frmDadosContratoObra "
            "frmDadosMedicoesObra "
            "frmInfObraEmRevisao"
        ),


        "javax.faces.behavior.event":
        "rowSelect",


        "javax.faces.partial.event":
        "rowSelect",


        "frmListaObras":
        "frmListaObras",


        "frmListaObras:tblListaObras_instantSelectedRowKey":
        codigo,


        "frmListaObras:tblListaObras_selection":
        codigo,


        "javax.faces.ViewState":
        viewstate

    }



    headers = {


        "Faces-Request":
        "partial/ajax",


        "X-Requested-With":
        "XMLHttpRequest",


        "Content-Type":
        "application/x-www-form-urlencoded; charset=UTF-8",


        "Accept":
        "application/xml, text/xml, */*; q=0.01",


        "Origin":
        "https://engegov.blumenau.sc.gov.br",


        "Referer":
        URL,


        "User-Agent":
        HEADERS["User-Agent"]

    }



    resposta = session.post(

        URL,

        data=dados,

        headers=headers,

        verify=False,

        timeout=10

    )


    resposta.raise_for_status()



    novo_viewstate = (

        atualizar_viewstate(
            resposta.text
        )

        or

        viewstate

    )


    return (
        resposta.text,
        novo_viewstate
    )







def extrair_contrato(xml):


    soup = BeautifulSoup(
        xml,
        "xml"
    )


    dados = {}



    update = soup.find(
        "update",
        {
            "id":
            "frmDadosContratoObra"
        }
    )



    if not update:

        return dados



    html = update.text



    soup_html = BeautifulSoup(
        html,
        "html.parser"
    )



    texto = soup_html.get_text(
        " ",
        strip=True
    )



    def pegar(padrao):

        resultado = re.search(
            padrao,
            texto,
            re.I
        )

        if resultado:

            return limpar_texto(
                resultado.group(1)
            )

        return None



    dados["empresa_executora"] = pegar(
        r"Empresa\s*(?:Executora)?\s*:?(.+?)\s+CNPJ"
    )


    dados["cnpj_empresa"] = pegar(
        r"CNPJ\s*:?\s*([\d\./-]+)"
    )


    dados["num_licitacao"] = pegar(
        r"Número da licitação\s*:?\s*(.*?)\s"
    )


    dados["num_contrato"] = pegar(
        r"Número do Contrato\s*:?\s*(.*?)\s"
    )


    data = pegar(
        r"Data do Contrato\s*:?\s*(\d{2}/\d{2}/\d{4})"
    )


    dados["data_contrato"] = converter_data(
        data
    )



    dados["num_ordem_servico"] = pegar(
        r"Ordem de Serviço\s*:?\s*(.*?)\s"
    )



    valor = re.search(
        r"Valor Total Contratado\s*R\$\s*([\d\.,]+)",
        texto
    )


    if valor:

        dados["valor_contratado"] = converter_valor(
            valor.group(1)
        )



    dados["inicio_obra"] = converter_data(
        pegar(
            r"Início da obra\s*:?\s*(\d{2}/\d{2}/\d{4})"
        )
    )



    dados["limite_execucao"] = converter_data(
        pegar(
            r"Data Limite Execução\s*:?\s*(\d{2}/\d{2}/\d{4})"
        )
    )



    dados["termino_contrato"] = converter_data(
        pegar(
            r"Término Contrato\s*:?\s*(\d{2}/\d{2}/\d{4})"
        )
    )



    dados["tipo_recurso"] = pegar(
        r"Tipo de Recurso\s*:?\s*(.*?)\s+(?:Valor|$)"
    )


    return dados







def extrair_andamento(xml):


    soup = BeautifulSoup(
        xml,
        "xml"
    )


    dados = {}



    update = soup.find(
        "update",
        {
            "id":
            "frmAndamentoObra"
        }
    )



    if not update:

        return dados



    html = update.text



    soup_html = BeautifulSoup(
        html,
        "html.parser"
    )



    texto = soup_html.get_text(
        " ",
        strip=True
    )



    valor = re.search(
        r"Valor Total Contratado\s*R\$\s*([\d\.,]+)",
        texto
    )


    if valor:

        dados["valor_contratado"] = converter_valor(
            valor.group(1)
        )



    valor = re.search(
        r"Valor Executado\s*\(Medido\)\s*R\$\s*([\d\.,]+)",
        texto
    )


    if valor:

        dados["valor_executado"] = converter_valor(
            valor.group(1)
        )


    else:

        dados["valor_executado"] = 0



    percentual = re.search(
        r"Percentual Executado.*?(\d+)",
        texto
    )


    if percentual:

        dados["pct_executado"] = float(
            percentual.group(1)
        )

    else:

        dados["pct_executado"] = 0



    if "valor_contratado" in dados:

        dados["saldo_contrato"] = (

            dados["valor_contratado"]

            -

            dados.get(
                "valor_executado",
                0
            )

        )


    return dados








# Busca a obra na tabela e, se encontrar, abre os detalhes de contrato e andamento

def buscar_obra_completa(
    session,
    viewstate,
    codigo
):


    obra, viewstate = buscar_obra(
        session,
        viewstate,
        codigo
    )



    if not obra:

        return (
            None,
            viewstate
        )



    detalhes, viewstate = clicar_obra(
        session,
        viewstate,
        codigo
    )



    obra.update(
        extrair_contrato(
            detalhes
        )
    )


    obra.update(
        extrair_andamento(
            detalhes
        )
    )



    obra.setdefault(
        "valor_executado",
        0
    )


    obra.setdefault(
        "pct_executado",
        0
    )


    obra.setdefault(
        "saldo_contrato",
        obra.get(
            "valor_contratado",
            0
        )
    )


    obra.setdefault(
        "fiscal_obra",
        None
    )


    return (
        obra,
        viewstate
    )
