"""Gráficos do painel (Plotly)."""

import plotly.graph_objects as go

import formatar
from dados import CONCLUIDA, EM_ANDAMENTO, PARALISADA

CORES_SITUACAO = {
    EM_ANDAMENTO: "#2b6cb0",
    PARALISADA: "#c53030",
    CONCLUIDA: "#a0aec0",
}
COR_EXECUTADO = "#2b6cb0"
COR_SALDO = "#bee3f8"


def _layout(fig, altura, titulo_x=None):
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=10, t=10, b=0),
        plot_bgcolor="white",
        legend=dict(orientation="h", y=-0.15, title=None, traceorder="normal"),
        bargap=0.3,
    )
    fig.update_xaxes(title=titulo_x, gridcolor="#edf2f7", zeroline=False)
    fig.update_yaxes(title=None, gridcolor="#edf2f7")
    return fig


def obras_por_secretaria(df):
    """Barras empilhadas: quantas obras cada secretaria tem em cada situação."""
    tabela = df.pivot_table(index="secretaria", columns="situacao", values="codigo",
                            aggfunc="count", fill_value=0)
    tabela = tabela.loc[tabela.sum(axis=1).sort_values().index]

    fig = go.Figure()
    for situacao in (EM_ANDAMENTO, PARALISADA, CONCLUIDA):
        if situacao in tabela:
            fig.add_bar(
                y=tabela.index, x=tabela[situacao], orientation="h",
                name=situacao.capitalize(), marker_color=CORES_SITUACAO[situacao],
                hovertemplate="%{y}: %{x} obras<extra>" + situacao.lower() + "</extra>",
            )
    fig.update_layout(barmode="stack")
    return _layout(fig, 60 + 32 * len(tabela), "Quantidade de obras")


def valor_por_secretaria(df):
    """Valor contratado de cada secretaria, separado em já executado e saldo a executar."""
    soma = df.groupby("secretaria")[["valor_executado", "valor_contratado"]].sum()
    soma = soma[soma["valor_contratado"] > 0].sort_values("valor_contratado")
    saldo = (soma["valor_contratado"] - soma["valor_executado"]).clip(lower=0)

    fig = go.Figure()
    fig.add_bar(y=soma.index, x=soma["valor_executado"], orientation="h", name="Executado",
                marker_color=COR_EXECUTADO,
                customdata=[formatar.moeda(v) for v in soma["valor_executado"]],
                hovertemplate="%{y}: %{customdata} executados<extra></extra>")
    fig.add_bar(y=soma.index, x=saldo, orientation="h", name="Saldo a executar",
                marker_color=COR_SALDO,
                text=[formatar.moeda_curta(v) for v in soma["valor_contratado"]],
                textposition="outside", cliponaxis=False,
                customdata=[formatar.moeda(v) for v in saldo],
                hovertemplate="%{y}: %{customdata} a executar<extra></extra>")
    fig.update_layout(barmode="stack")
    fig = _layout(fig, 60 + 32 * len(soma), "Valor contratado (total no fim da barra)")
    # espaço à direita para o rótulo da maior barra não ser cortado
    fig.update_xaxes(showticklabels=False, range=[0, soma["valor_contratado"].max() * 1.2])
    return fig


def contratos_por_ano(df):
    """Quantidade de obras pelo ano de assinatura do contrato."""
    contagem = df.dropna(subset=["ano_contrato"]).groupby("ano_contrato").size()
    fig = go.Figure(go.Bar(
        x=contagem.index.astype(str), y=contagem.values, marker_color=COR_EXECUTADO,
        text=contagem.values, textposition="outside", cliponaxis=False,
        hovertemplate="%{x}: %{y} contratos<extra></extra>",
    ))
    fig.update_xaxes(type="category")
    return _layout(fig, 300, "Ano do contrato")


def valor_por_recurso(df):
    """Valor contratado pela origem do dinheiro. "Operação de crédito interna / Caixa"
    e "Operação de crédito interna / Banco do Brasil" entram juntas como "Operação de crédito interna"."""
    origem = df["tipo_recurso"].fillna("Não informado").str.split(" / ").str[0]
    soma = df.groupby(origem)["valor_contratado"].sum()
    soma = soma[soma > 0].sort_values()
    fig = go.Figure(go.Bar(
        y=soma.index, x=soma.values, orientation="h", marker_color=COR_EXECUTADO,
        text=[formatar.moeda_curta(v) for v in soma.values], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    fig = _layout(fig, 60 + 34 * len(soma))
    fig.update_xaxes(showticklabels=False, range=[0, soma.max() * 1.25])
    return fig


def execucao_x_prazo(df_avaliado):
    """Cada ponto é uma obra não concluída. Abaixo da linha, a execução está atrasada."""
    abertas = df_avaliado[
        (df_avaliado["situacao"] != CONCLUIDA)
        & df_avaliado["pct_prazo"].notna()
        & df_avaliado["pct_executado"].notna()
    ]
    fig = go.Figure()
    fig.add_scatter(x=[0, 100], y=[0, 100], mode="lines", name="Execução em dia",
                    line=dict(color="#718096", dash="dash", width=1), hoverinfo="skip")
    for situacao in (EM_ANDAMENTO, PARALISADA):
        parte = abertas[abertas["situacao"] == situacao]
        fig.add_scatter(
            x=parte["pct_prazo"], y=parte["pct_executado"], mode="markers",
            name=situacao.capitalize(),
            marker=dict(color=CORES_SITUACAO[situacao], size=9, opacity=0.8),
            customdata=parte[["codigo", "descricao"]].fillna("").map(lambda t: t[:70]),
            hovertemplate=("<b>%{customdata[0]}</b> %{customdata[1]}<br>"
                           "Prazo decorrido: %{x:.0f}%<br>Executado: %{y:.0f}%<extra></extra>"),
        )
    fig.update_xaxes(range=[-3, 103], ticksuffix="%")
    fig.update_yaxes(range=[-3, 103], ticksuffix="%", title="Executado")
    fig = _layout(fig, 420, "Prazo do contrato já decorrido")
    fig.update_yaxes(title="Executado")
    return fig, len(abertas)
