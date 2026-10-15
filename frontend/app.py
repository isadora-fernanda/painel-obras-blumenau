"""Painel das obras públicas de Blumenau (Streamlit).

Rode a partir da raiz do projeto: streamlit run frontend/app.py
"""

import pandas as pd
import streamlit as st

import formatar
import graficos
from assistente import EXEMPLOS, responder
from dados import CONCLUIDA, EM_ANDAMENTO, PARALISADA, Filtros, aplicar_filtros, carregar_obras
from prazos import DIFERENCA_MINIMA, avaliar_prazos, obras_em_atencao

st.set_page_config(page_title="Obras de Blumenau", page_icon=":material/construction:", layout="wide")

SEM_BARRA = {"displayModeBar": False}


@st.cache_data(ttl=300, show_spinner="Carregando as obras...")
def carregar():
    return carregar_obras()


def csv_para_excel(df):
    """CSV com ponto e vírgula e vírgula decimal, que o Excel em português abre direto."""
    return df.to_csv(index=False, sep=";", decimal=",", date_format="%d/%m/%Y").encode("utf-8-sig")


def filtros_da_barra_lateral(df):
    st.sidebar.header("Filtros")
    busca = st.sidebar.text_input("Buscar", placeholder="Código, descrição, rua ou empresa")
    secretarias = st.sidebar.multiselect("Secretaria", sorted(df["secretaria"].dropna().unique()),
                                         placeholder="Todas")
    situacoes = st.sidebar.multiselect("Situação", [EM_ANDAMENTO, PARALISADA, CONCLUIDA],
                                       placeholder="Todas")
    intervencoes = st.sidebar.multiselect(
        "Tipo de intervenção", sorted(df["intervencao"].fillna("Não informada").unique()),
        placeholder="Todos",
    )

    anos = None
    anos_validos = df["ano_contrato"].dropna()
    if anos_validos.nunique() > 1:
        menor, maior = int(anos_validos.min()), int(anos_validos.max())
        escolhido = st.sidebar.slider("Ano do contrato", menor, maior, (menor, maior))
        if escolhido != (menor, maior):  # sem mexer, as obras sem data continuam aparecendo
            anos = escolhido

    filtrado = aplicar_filtros(df, Filtros(busca, secretarias, situacoes, intervencoes, anos))
    st.sidebar.caption(f"{len(filtrado)} de {len(df)} obras")
    return filtrado


def aba_visao_geral(df):
    contratado = df["valor_contratado"].sum()
    executado = df["valor_executado"].sum()

    c = st.columns(5)
    c[0].metric("Obras", formatar.inteiro(len(df)))
    c[1].metric("Em andamento", formatar.inteiro((df["situacao"] == EM_ANDAMENTO).sum()))
    c[2].metric("Paralisadas", formatar.inteiro((df["situacao"] == PARALISADA).sum()))
    c[3].metric("Valor contratado", formatar.moeda_curta(contratado))
    c[4].metric("Valor executado", formatar.moeda_curta(executado),
                help=f"{executado / contratado * 100:.0f}% do contratado" if contratado else None)

    esquerda, direita = st.columns(2)
    with esquerda:
        st.subheader("Obras por secretaria")
        st.plotly_chart(graficos.obras_por_secretaria(df), config=SEM_BARRA)
    with direita:
        st.subheader("Valor contratado por secretaria")
        st.plotly_chart(graficos.valor_por_secretaria(df), config=SEM_BARRA)

    esquerda, direita = st.columns(2)
    with esquerda:
        st.subheader("Contratos assinados por ano")
        sem_data = df["ano_contrato"].isna().sum()
        if sem_data:
            st.caption(f"{sem_data} obras sem data do contrato ficaram de fora.")
        st.plotly_chart(graficos.contratos_por_ano(df), config=SEM_BARRA)
    with direita:
        st.subheader("De onde vem o dinheiro")
        st.plotly_chart(graficos.valor_por_recurso(df), config=SEM_BARRA)


COLUNAS_TABELA = {
    "codigo": st.column_config.TextColumn("Código", width="small"),
    "secretaria": st.column_config.TextColumn("Secretaria", width="small"),
    "descricao": st.column_config.TextColumn("Descrição", width="large"),
    "situacao": st.column_config.TextColumn("Situação"),
    "contratado": st.column_config.TextColumn("Contratado"),
    "pct_executado": st.column_config.ProgressColumn("Executado", format="%.0f%%",
                                                     min_value=0, max_value=100),
}


def aba_consulta(df):
    st.caption("Clique numa linha para ver os dados completos da obra.")
    # O valor vai como texto formatado (R$ 1.234,56), já que a tabela não tem o padrão brasileiro
    tabela = df.assign(contratado=df["valor_contratado"].map(formatar.moeda))
    tabela = tabela[list(COLUNAS_TABELA)].reset_index(drop=True)
    altura = min(400, 35 * (len(tabela) + 1) + 3)  # sem linhas vazias quando o filtro traz poucas obras
    selecao = st.dataframe(tabela, column_config=COLUNAS_TABELA, hide_index=True, height=altura,
                           on_select="rerun", selection_mode="single-row", key="tabela_obras")
    st.download_button("Baixar estas obras (CSV)", csv_para_excel(df), "obras.csv", "text/csv")

    linhas = selecao.selection.rows
    # A seleção fica guardada quando os filtros mudam, então a linha pode não existir mais
    if linhas and linhas[0] < len(df):
        mostrar_obra(df.iloc[linhas[0]])


def mostrar_obra(o):
    st.divider()
    st.subheader(f"{o['codigo']} · {o['descricao']}")
    st.caption(f"{o['secretaria']} · {o['situacao'].capitalize()} · "
               f"{o['intervencao'] if pd.notna(o['intervencao']) else 'intervenção não informada'}")

    c = st.columns(4)
    for coluna, rotulo, campo in ((c[0], "Contratado", "valor_contratado"),
                                  (c[1], "Executado", "valor_executado"),
                                  (c[2], "Saldo", "saldo_contrato")):
        coluna.metric(rotulo, formatar.moeda_sem_centavos(o[campo]), help=formatar.moeda(o[campo]))
    c[3].metric("Percentual executado", formatar.percentual(o["pct_executado"]))

    def texto(valor):
        return valor if pd.notna(valor) else "-"

    esquerda, direita = st.columns(2)
    esquerda.markdown(
        f"**Local:** {texto(o['logradouro'])}  \n"
        f"**Empresa:** {texto(o['empresa_executora'])}  \n"
        f"**CNPJ:** {texto(o['cnpj_empresa'])}  \n"
        f"**Recurso:** {texto(o['tipo_recurso'])}"
    )
    direita.markdown(
        f"**Licitação:** {texto(o['num_licitacao'])} · **Contrato:** {texto(o['num_contrato'])}  \n"
        f"**Data do contrato:** {formatar.data(o['data_contrato'])}  \n"
        f"**Início da obra:** {formatar.data(o['inicio_obra'])}  \n"
        f"**Prazo final:** {formatar.data(o['prazo_final'])}"
    )


def aba_prazos(df):
    avaliadas = avaliar_prazos(df)
    atencao = obras_em_atencao(avaliadas)

    c = st.columns(3)
    c[0].metric("Paralisadas", int(avaliadas["paralisada"].sum()))
    c[1].metric("Com prazo vencido", int(avaliadas["prazo_vencido"].sum()))
    c[2].metric("Execução abaixo do prazo", int(avaliadas["abaixo_do_prazo"].sum()),
                help=f"Executado {DIFERENCA_MINIMA} pontos ou mais abaixo do prazo já decorrido.")

    st.subheader("Execução x prazo das obras não concluídas")
    fig, quantidade = graficos.execucao_x_prazo(avaliadas)
    st.caption(f"Cada ponto é uma obra ({quantidade} com datas e percentual cadastrados). "
               "Pontos abaixo da linha tracejada estão com a execução atrasada em relação ao prazo. "
               "As obras com o prazo já vencido ficam encostadas na marca de 100%.")
    st.plotly_chart(fig, config=SEM_BARRA)

    st.subheader(f"Obras que merecem atenção ({len(atencao)})")
    if atencao.empty:
        st.success("Nenhuma obra paralisada, vencida ou atrasada nos filtros atuais.")
        return
    colunas = {
        "codigo": st.column_config.TextColumn("Código", width="small"),
        "motivo": st.column_config.TextColumn("Motivo", width="large"),
        "prazo_final": st.column_config.DateColumn("Prazo final", format="DD/MM/YYYY"),
        "secretaria": st.column_config.TextColumn("Secretaria", width="small"),
        "descricao": st.column_config.TextColumn("Descrição", width="large"),
    }
    st.dataframe(atencao[list(colunas)], column_config=colunas, hide_index=True)
    st.download_button("Baixar a lista (CSV)", csv_para_excel(atencao[list(colunas)]),
                       "obras_em_atencao.csv", "text/csv")
    st.caption("A lista é um apoio para a fiscalização, calculado com as datas e percentuais "
               "publicados no portal. Não é uma auditoria.")


def aba_perguntas(df):
    st.caption("Pergunte sobre as obras filtradas. Exemplos: " + "; ".join(EXEMPLOS) + ".")
    historico = st.session_state.setdefault("historico", [])

    for mensagem in historico:
        with st.chat_message(mensagem["papel"]):
            st.write(mensagem["texto"])
            if mensagem.get("tabela") is not None:
                st.dataframe(mensagem["tabela"], hide_index=True)
            if mensagem.get("fonte"):
                st.caption(mensagem["fonte"])

    pergunta = st.chat_input("Escreva sua pergunta")
    if pergunta:
        resposta = responder(pergunta, df)
        historico.append({"papel": "user", "texto": pergunta})
        historico.append({"papel": "assistant", "texto": resposta.texto, "tabela": resposta.tabela,
                          "fonte": resposta.fonte})
        st.rerun()


def main():
    st.title("Obras públicas de Blumenau")
    st.caption("Dados coletados do portal de obras da prefeitura (EngeGov).")

    try:
        obras = carregar()
    except Exception as erro:
        st.error(f"Não consegui ler os dados. Confira o MySQL (ou o OBRAS_CSV) no arquivo .env.\n\n{erro}")
        st.stop()

    if obras.empty:
        st.warning("A tabela obras está vazia. Rode primeiro: python backend/processar_obras.py")
        st.stop()

    filtrado = filtros_da_barra_lateral(obras)
    if filtrado.empty:
        st.info("Nenhuma obra com esses filtros.")
        st.stop()

    geral, consulta, prazos, perguntas = st.tabs(
        ["Visão geral", "Consulta", "Prazos e atrasos", "Perguntas"]
    )
    with geral:
        aba_visao_geral(filtrado)
    with consulta:
        aba_consulta(filtrado)
    with prazos:
        aba_prazos(filtrado)
    with perguntas:
        aba_perguntas(filtrado)


main()
