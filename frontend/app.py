"""
Painel de Obras Publicas — Blumenau (frontend em arquivo unico).

Este arquivo consolida, sem alterar a logica de negocio original, tudo
que antes estava dividido em api/client.py, components/*.py,
utils/*.py e pages/*.py. Como e um unico arquivo, a navegacao
multipage do Streamlit (pasta pages/) foi substituida por abas
(st.tabs) dentro do mesmo app: Dashboard Executivo, Consulta de Obras,
Analise de Risco e Assistente Inteligente.

O frontend conecta direto no MySQL via PyMySQL, usando as mesmas
variaveis de ambiente do seu database.py (DB_HOST, DB_USER,
DB_PASSWORD, DB_PORT, DB_DATABASE) — nao depende do Flask (api.py)
estar rodando.

Nesta versao: tema escuro (fundo escuro / texto claro) em todos os
componentes nativos do Streamlit (via .streamlit/config.toml) e nos
elementos customizados (via CSS), alem de graficos redesenhados para
serem mais diretos de ler (rotulos com valores, eixos nomeados,
formatacao monetaria compacta, ordenacao por relevancia e um
indicador de execucao media no dashboard).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import pymysql
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# Conexao com o MySQL (equivalente ao seu database.py)
# =============================================================================

def obter_conexao():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        port=int(os.getenv("DB_PORT", 3306)),
        database=os.getenv("DB_DATABASE", "obrasblumenau"),
        cursorclass=pymysql.cursors.DictCursor,
    )


COLUNAS_DATA = [
    "data_contrato",
    "inicio_obra",
    "limite_execucao",
    "termino_contrato",
    "created_at",
    "updated_at",
]

COLUNAS_NUMERICAS = [
    "valor_contratado",
    "valor_executado",
    "saldo_contrato",
    "pct_executado",
]


class APIError(Exception):
    """Erro de comunicacao com o banco de dados."""


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    for coluna in COLUNAS_NUMERICAS:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    for coluna in COLUNAS_DATA:
        if coluna in df.columns:
            df[coluna] = pd.to_datetime(df[coluna], errors="coerce")

    # saldo_contrato pode nao vir preenchido no banco: calcula como reforco
    if {"valor_contratado", "valor_executado"}.issubset(df.columns):
        saldo_calculado = df["valor_contratado"].fillna(0) - df["valor_executado"].fillna(0)
        if "saldo_contrato" not in df.columns:
            df["saldo_contrato"] = saldo_calculado
        else:
            df["saldo_contrato"] = df["saldo_contrato"].fillna(saldo_calculado)

    if {"valor_contratado", "valor_executado"}.issubset(df.columns) and "pct_executado" not in df.columns:
        with pd.option_context("mode.use_inf_as_na", True):
            df["pct_executado"] = (
                df["valor_executado"] / df["valor_contratado"].replace(0, pd.NA) * 100
            )

    for coluna in ["secretaria", "situacao", "empresa_executora", "logradouro", "fiscal_obra"]:
        if coluna in df.columns:
            df[coluna] = df[coluna].astype("string").str.strip()

    return df


@st.cache_data(ttl=120, show_spinner="Carregando obras do banco de dados...")
def fetch_obras() -> pd.DataFrame:
    """Busca todas as obras cadastradas direto no MySQL."""
    try:
        conexao = obter_conexao()
    except Exception as exc:  # noqa: BLE001
        raise APIError(
            f"Nao foi possivel conectar ao MySQL. Confira host, usuario, senha, "
            f"porta e nome do banco no .env. Detalhe: {exc}"
        ) from exc

    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT * FROM obras")
            dados = cursor.fetchall()
    finally:
        conexao.close()

    df = pd.DataFrame(dados)
    return _normalizar(df)


def fetch_obra(codigo: str) -> dict | None:
    """Busca uma obra especifica pelo codigo, direto no MySQL."""
    try:
        conexao = obter_conexao()
    except Exception:  # noqa: BLE001
        return None

    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT * FROM obras WHERE codigo = %s", (codigo,))
            return cursor.fetchone()
    finally:
        conexao.close()


def check_api_health() -> tuple[bool, str]:
    """Confere se a conexao com o MySQL esta funcionando."""
    try:
        conexao = obter_conexao()
        conexao.close()
        return True, "Conectado ao MySQL (obrasblumenau)."
    except Exception as exc:  # noqa: BLE001
        return False, f"Falha na conexao com o MySQL: {exc}"


# =============================================================================
# components/styles.py — TEMA ESCURO
# =============================================================================
# Paleta pensada para fundo escuro: cores de destaque com boa luminosidade
# (teal, ambar, coral) para garantir contraste sobre o fundo quase-preto,
# e cores de status/risco levemente saturadas para nao "estourar" os olhos
# quando repetidas em varios graficos.

TOKENS = {
    "bg": "#0A1618",
    "surface": "#101E21",
    "surface_alt": "#16292D",
    "border": "#25404450",
    "border_solid": "#2C474C",
    "primary": "#4FD8C4",
    "primary_dim": "#2E8478",
    "primary_soft": "#123634",
    "accent": "#F2A65A",
    "text": "#EAF3F2",
    "text_muted": "#8FAAAD",
    "risco_baixo": "#4CD787",
    "risco_medio": "#F2C14E",
    "risco_alto": "#F2555A",
    "situacao_andamento": "#4FD8C4",
    "situacao_concluida": "#4CD787",
    "situacao_paralisada": "#F2555A",
    "situacao_licitacao": "#9C8CF2",
    "situacao_outro": "#7C9598",
}

FONT_DISPLAY = "'Sora', sans-serif"
FONT_BODY = "'IBM Plex Sans', sans-serif"
FONT_MONO = "'IBM Plex Mono', monospace"


def situacao_color(situacao: str) -> str:
    if not situacao:
        return TOKENS["situacao_outro"]
    valor = situacao.strip().upper()
    if "ANDAMENTO" in valor or "EXECU" in valor:
        return TOKENS["situacao_andamento"]
    if "CONCLU" in valor or "FINALIZ" in valor:
        return TOKENS["situacao_concluida"]
    if "PARALIS" in valor:
        return TOKENS["situacao_paralisada"]
    if "LICITA" in valor or "PROJETO" in valor or "PLANEJ" in valor:
        return TOKENS["situacao_licitacao"]
    return TOKENS["situacao_outro"]


def risco_color(nivel: str) -> str:
    return {
        "Baixo risco": TOKENS["risco_baixo"],
        "Medio risco": TOKENS["risco_medio"],
        "Alto risco": TOKENS["risco_alto"],
    }.get(nivel, TOKENS["text_muted"])


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap');

        html, body, [class*="css"] {{
            font-family: {FONT_BODY};
            color: {TOKENS["text"]};
        }}

        #MainMenu, footer, header {{visibility: hidden;}}

        .stApp {{
            background-color: {TOKENS["bg"]};
        }}

        section[data-testid="stSidebar"] {{
            background-color: {TOKENS["surface"]};
            border-right: 1px solid {TOKENS["border_solid"]};
        }}
        section[data-testid="stSidebar"] * {{
            color: {TOKENS["text"]} !important;
        }}
        section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] {{
            background-color: {TOKENS["primary_dim"]} !important;
        }}
        section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea {{
            background-color: {TOKENS["surface_alt"]} !important;
        }}

        h1, h2, h3 {{
            font-family: {FONT_DISPLAY};
            font-weight: 600;
            letter-spacing: -0.01em;
            color: {TOKENS["text"]};
        }}

        .page-eyebrow {{
            font-family: {FONT_MONO};
            font-size: 0.72rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: {TOKENS["accent"]};
            margin-bottom: 0.2rem;
        }}

        .page-title {{
            font-family: {FONT_DISPLAY};
            font-size: 1.9rem;
            font-weight: 700;
            color: {TOKENS["text"]};
            margin-bottom: 0.1rem;
        }}

        .page-subtitle {{
            color: {TOKENS["text_muted"]};
            font-size: 0.95rem;
            margin-bottom: 1.1rem;
        }}

        /* --- Ribbon de composicao por situacao (elemento assinatura) --- */
        .status-ribbon {{
            display: flex;
            width: 100%;
            height: 10px;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 0.35rem;
            box-shadow: inset 0 0 0 1px {TOKENS["border_solid"]};
        }}
        .status-ribbon-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.9rem;
            font-size: 0.78rem;
            color: {TOKENS["text_muted"]};
            margin-bottom: 1.6rem;
        }}
        .status-ribbon-legend span.dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 5px;
        }}

        /* --- Cards KPI --- */
        .kpi-card {{
            background-color: {TOKENS["surface"]};
            border: 1px solid {TOKENS["border_solid"]};
            border-radius: 12px;
            padding: 1.05rem 1.2rem;
            height: 100%;
        }}
        .kpi-label {{
            font-family: {FONT_MONO};
            font-size: 0.68rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {TOKENS["text_muted"]};
            margin-bottom: 0.45rem;
        }}
        .kpi-value {{
            font-family: {FONT_DISPLAY};
            font-size: 1.65rem;
            font-weight: 700;
            color: {TOKENS["text"]};
            line-height: 1.1;
        }}
        .kpi-value.accent {{ color: {TOKENS["accent"]}; }}
        .kpi-delta {{
            font-size: 0.78rem;
            color: {TOKENS["text_muted"]};
            margin-top: 0.3rem;
        }}

        /* --- Secao --- */
        .section-title {{
            font-family: {FONT_DISPLAY};
            font-size: 1.05rem;
            font-weight: 600;
            color: {TOKENS["text"]};
            margin: 0.4rem 0 0.6rem 0;
            padding-left: 0.55rem;
            border-left: 3px solid {TOKENS["accent"]};
        }}

        .panel-card {{
            background-color: {TOKENS["surface"]};
            border: 1px solid {TOKENS["border_solid"]};
            border-radius: 12px;
            padding: 1rem 1.1rem;
            color: {TOKENS["text"]};
        }}

        /* --- Badges --- */
        .badge {{
            display: inline-block;
            padding: 0.18rem 0.6rem;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 600;
            color: #06110F;
        }}

        .obra-codigo {{
            font-family: {FONT_MONO};
            color: {TOKENS["accent"]};
            font-weight: 500;
        }}

        [data-testid="stMetricValue"] {{
            font-family: {FONT_DISPLAY};
            color: {TOKENS["text"]};
        }}
        [data-testid="stMetricLabel"] {{
            color: {TOKENS["text_muted"]};
        }}

        div[data-testid="stDataFrame"] {{
            border: 1px solid {TOKENS["border_solid"]};
            border-radius: 10px;
        }}

        .stButton button {{
            background-color: {TOKENS["surface_alt"]};
            color: {TOKENS["text"]};
            border: 1px solid {TOKENS["border_solid"]};
        }}
        .stButton button:hover {{
            border-color: {TOKENS["primary"]};
            color: {TOKENS["primary"]};
        }}

        .chart-note {{
            font-size: 0.78rem;
            color: {TOKENS["text_muted"]};
            margin-top: -0.6rem;
            margin-bottom: 0.8rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="page-eyebrow">{eyebrow}</div>
        <div class="page-title">{title}</div>
        <div class="page-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def chart_note(texto: str) -> None:
    """Legenda curta abaixo de um grafico explicando como le-lo."""
    st.markdown(f'<div class="chart-note">{texto}</div>', unsafe_allow_html=True)


# =============================================================================
# components/cards.py
# =============================================================================

def _fmt_moeda(valor: float) -> str:
    if pd.isna(valor):
        return "R$ 0"
    texto = f"R$ {valor:,.0f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_moeda_compacta(valor: float) -> str:
    """Formato curto para rotulos de grafico: R$ 1,2 mi / R$ 850 mil."""
    if pd.isna(valor):
        return "R$ 0"
    valor = float(valor)
    sinal = "-" if valor < 0 else ""
    valor = abs(valor)
    if valor >= 1_000_000_000:
        return f"{sinal}R$ {valor / 1_000_000_000:,.1f} bi".replace(".", ",")
    if valor >= 1_000_000:
        return f"{sinal}R$ {valor / 1_000_000:,.1f} mi".replace(".", ",")
    if valor >= 1_000:
        return f"{sinal}R$ {valor / 1_000:,.0f} mil".replace(".", ",")
    return f"{sinal}R$ {valor:,.0f}".replace(".", ",")


def _is_situacao(df: pd.DataFrame, termos: list[str]) -> pd.Series:
    situ = df["situacao"].fillna("").str.upper()
    mask = pd.Series(False, index=df.index)
    for termo in termos:
        mask |= situ.str.contains(termo)
    return mask


def render_kpis(df: pd.DataFrame) -> None:
    total = len(df)
    em_andamento = int(_is_situacao(df, ["ANDAMENTO", "EXECU"]).sum()) if total else 0
    concluidas = int(_is_situacao(df, ["CONCLU", "FINALIZ"]).sum()) if total else 0
    paralisadas = int(_is_situacao(df, ["PARALIS"]).sum()) if total else 0
    secretarias = df["secretaria"].nunique() if total and "secretaria" in df else 0
    valor_total = df["valor_contratado"].sum() if total and "valor_contratado" in df else 0
    pct_medio = df["pct_executado"].mean() if total and "pct_executado" in df else 0

    itens = [
        ("Total de obras", f"{total:,}".replace(",", "."), False),
        ("Em andamento", f"{em_andamento:,}".replace(",", "."), False),
        ("Concluidas", f"{concluidas:,}".replace(",", "."), False),
        ("Paralisadas", f"{paralisadas:,}".replace(",", "."), True),
        ("Secretarias envolvidas", f"{secretarias:,}".replace(",", "."), False),
        ("Valor total contratado", _fmt_moeda(valor_total), False),
        ("Execucao media", f"{(pct_medio or 0):.1f}%", False),
    ]

    colunas = st.columns(len(itens))
    for coluna, (label, valor, alerta) in zip(colunas, itens):
        classe_valor = "kpi-value accent" if alerta and valor != "0" else "kpi-value"
        with coluna:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{label}</div>
                    <div class="{classe_valor}">{valor}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_status_ribbon(df: pd.DataFrame) -> None:
    """Faixa horizontal segmentada mostrando a composicao real das obras
    por situacao — o elemento assinatura do painel executivo."""
    if df.empty or "situacao" not in df.columns:
        return

    contagem = (
        df["situacao"].fillna("Nao informado").value_counts().sort_values(ascending=False)
    )
    total = contagem.sum()
    if total == 0:
        return

    segmentos = ""
    legenda = ""
    for situacao, qtd in contagem.items():
        pct = qtd / total * 100
        cor = situacao_color(situacao)
        segmentos += f'<div style="width:{pct}%; background-color:{cor};"></div>'
        legenda += (
            f'<span><span class="dot" style="background-color:{cor};"></span>'
            f"{situacao} · {qtd} ({pct:.0f}%)</span>"
        )

    st.markdown(
        f"""
        <div class="status-ribbon">{segmentos}</div>
        <div class="status-ribbon-legend">{legenda}</div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# components/filters.py
# =============================================================================

def _opcoes(df: pd.DataFrame, coluna: str) -> list[str]:
    if coluna not in df.columns:
        return []
    return sorted(v for v in df[coluna].dropna().unique().tolist() if str(v).strip())


def render_sidebar_filters(df: pd.DataFrame, key_prefix: str = "") -> pd.DataFrame:
    st.sidebar.markdown("### Filtros")

    if df.empty:
        st.sidebar.info("Nenhum dado carregado ainda.")
        return df

    busca = st.sidebar.text_input(
        "Busca inteligente",
        placeholder="Codigo, descricao, rua, empresa...",
        help="Pesquisa em codigo, descricao, logradouro, secretaria e empresa executora.",
        key=f"{key_prefix}_busca",
    )

    secretarias = st.sidebar.multiselect(
        "Secretaria", _opcoes(df, "secretaria"), key=f"{key_prefix}_secretarias"
    )
    situacoes = st.sidebar.multiselect(
        "Situacao", _opcoes(df, "situacao"), key=f"{key_prefix}_situacoes"
    )
    empresas = st.sidebar.multiselect(
        "Empresa executora", _opcoes(df, "empresa_executora"), key=f"{key_prefix}_empresas"
    )
    logradouro = st.sidebar.text_input(
        "Bairro / logradouro", placeholder="Ex.: Rua XV de Novembro", key=f"{key_prefix}_logradouro"
    )

    faixa_execucao = None
    if "pct_executado" in df.columns and df["pct_executado"].notna().any():
        faixa_execucao = st.sidebar.slider(
            "Percentual executado",
            min_value=0,
            max_value=100,
            value=(0, 100),
            format="%d%%",
            key=f"{key_prefix}_faixa_execucao",
        )

    periodo = None
    if "inicio_obra" in df.columns and df["inicio_obra"].notna().any():
        min_data = pd.to_datetime(df["inicio_obra"]).min().date()
        max_data = pd.to_datetime(df["inicio_obra"]).max().date()
        if min_data < max_data:
            periodo = st.sidebar.date_input(
                "Periodo (inicio da obra)",
                value=(min_data, max_data),
                min_value=min_data,
                max_value=max_data,
                key=f"{key_prefix}_periodo",
            )

    st.sidebar.markdown("---")

    resultado = df.copy()

    if busca:
        termo = busca.strip().lower()
        colunas_busca = [
            c for c in ["codigo", "descricao", "logradouro", "secretaria", "empresa_executora"]
            if c in resultado.columns
        ]
        mascara = pd.Series(False, index=resultado.index)
        for coluna in colunas_busca:
            mascara |= resultado[coluna].astype(str).str.lower().str.contains(termo, na=False)
        resultado = resultado[mascara]

    if secretarias:
        resultado = resultado[resultado["secretaria"].isin(secretarias)]

    if situacoes:
        resultado = resultado[resultado["situacao"].isin(situacoes)]

    if empresas:
        resultado = resultado[resultado["empresa_executora"].isin(empresas)]

    if logradouro:
        resultado = resultado[
            resultado["logradouro"].astype(str).str.contains(logradouro, case=False, na=False)
        ]

    if faixa_execucao and "pct_executado" in resultado.columns:
        minimo, maximo = faixa_execucao
        if not (minimo == 0 and maximo == 100):
            resultado = resultado[
                resultado["pct_executado"].fillna(-1).between(minimo, maximo)
            ]

    if periodo and isinstance(periodo, tuple) and len(periodo) == 2 and "inicio_obra" in resultado.columns:
        inicio, fim = periodo
        resultado = resultado[
            (resultado["inicio_obra"].dt.date >= inicio) & (resultado["inicio_obra"].dt.date <= fim)
        ]

    st.sidebar.markdown(
        f'<div style="font-size:0.8rem; opacity:0.75;">{len(resultado)} de {len(df)} obras exibidas</div>',
        unsafe_allow_html=True,
    )

    return resultado


# =============================================================================
# components/charts.py — redesenhados para leitura direta (sem depender de
# hover): rotulos com valor, eixos nomeados, ordenacao por relevancia.
# =============================================================================

PALETA_SEQUENCIAL = [
    TOKENS["primary_dim"], TOKENS["primary"], "#7FE3D3",
    TOKENS["accent"], "#F2C695", "#9C8CF2", "#C7BCF5",
]

_EIXO_COMUM = dict(
    gridcolor=TOKENS["border_solid"],
    zerolinecolor=TOKENS["border_solid"],
    color=TOKENS["text_muted"],
    linecolor=TOKENS["border_solid"],
)


def _layout_base(fig: go.Figure, titulo: str, altura: int = 360, subtitulo: str | None = None) -> go.Figure:
    titulo_html = f"<b>{titulo}</b>"
    if subtitulo:
        titulo_html += f"<br><span style='font-size:11px; color:{TOKENS['text_muted']}'>{subtitulo}</span>"

    fig.update_layout(
        title=dict(
            text=titulo_html,
            font=dict(family=FONT_DISPLAY, size=15, color=TOKENS["text"]),
            x=0,
            xanchor="left",
        ),
        font=dict(family=FONT_BODY, size=12, color=TOKENS["text"]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=58, b=10),
        height=altura,
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, font=dict(size=11, color=TOKENS["text_muted"])),
        hoverlabel=dict(bgcolor=TOKENS["surface_alt"], font=dict(color=TOKENS["text"], family=FONT_BODY)),
        xaxis=_EIXO_COMUM,
        yaxis=_EIXO_COMUM,
    )
    return fig


def chart_indicador_execucao(df: pd.DataFrame) -> go.Figure:
    """Mostrador (gauge) com a execucao media do portfolio filtrado — leitura
    imediata do 'estado geral' antes de entrar nos detalhes."""
    media = float(df["pct_executado"].mean()) if "pct_executado" in df.columns and df["pct_executado"].notna().any() else 0.0
    media = max(0.0, min(100.0, media))

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=media,
            number=dict(suffix="%", font=dict(family=FONT_DISPLAY, size=34, color=TOKENS["text"])),
            gauge=dict(
                axis=dict(range=[0, 100], tickcolor=TOKENS["text_muted"], tickfont=dict(color=TOKENS["text_muted"], size=10)),
                bar=dict(color=TOKENS["primary"], thickness=0.32),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                steps=[
                    dict(range=[0, 40], color=TOKENS["surface_alt"]),
                    dict(range=[40, 75], color=TOKENS["primary_soft"]),
                    dict(range=[75, 100], color="#1D4B45"),
                ],
            ),
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_BODY, color=TOKENS["text"]),
        height=220,
        margin=dict(l=20, r=20, t=40, b=10),
        title=dict(
            text=f"<b>Execucao media do portfolio</b><br><span style='font-size:11px; color:{TOKENS['text_muted']}'>Media do % executado nas obras filtradas</span>",
            font=dict(family=FONT_DISPLAY, size=15, color=TOKENS["text"]),
            x=0, xanchor="left",
        ),
    )
    return fig


def chart_situacao_bar(df: pd.DataFrame) -> go.Figure:
    """Barras horizontais por situacao — mais facil de comparar quantidades
    exatas do que um donut, principalmente com muitas categorias."""
    contagem = df["situacao"].fillna("Nao informado").value_counts().sort_values()
    total = contagem.sum()
    cores = [situacao_color(s) for s in contagem.index]

    fig = go.Figure(
        go.Bar(
            x=contagem.values,
            y=contagem.index,
            orientation="h",
            marker=dict(color=cores),
            text=[f"{v} ({v / total * 100:.0f}%)" for v in contagem.values],
            textposition="outside",
            textfont=dict(color=TOKENS["text"]),
            hovertemplate="%{y}: %{x} obras<extra></extra>",
        )
    )
    fig.update_xaxes(title="Quantidade de obras")
    return _layout_base(fig, "Obras por situacao", subtitulo="Quantidade e % do total filtrado")


def chart_financeiro_waterfall(df: pd.DataFrame) -> go.Figure:
    contratado = float(df["valor_contratado"].sum())
    executado = float(df["valor_executado"].sum())
    saldo = contratado - executado
    pct = (executado / contratado * 100) if contratado else 0

    fig = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "total"],
            x=["Valor contratado", "Valor executado", "Saldo remanescente"],
            y=[contratado, -executado, saldo],
            text=[_fmt_moeda_compacta(v) for v in [contratado, executado, saldo]],
            textposition="outside",
            textfont=dict(color=TOKENS["text"]),
            connector=dict(line=dict(color=TOKENS["border_solid"])),
            decreasing=dict(marker=dict(color=TOKENS["accent"])),
            increasing=dict(marker=dict(color=TOKENS["primary"])),
            totals=dict(marker=dict(color=TOKENS["primary_dim"])),
        )
    )
    fig.update_yaxes(title="Valor (R$)", tickprefix="R$ ", separatethousands=True)
    return _layout_base(
        fig,
        "Execucao financeira do portfolio",
        subtitulo=f"{pct:.0f}% do valor contratado ja foi executado",
    )


def chart_secretarias_treemap(df: pd.DataFrame) -> go.Figure:
    contagem = df["secretaria"].fillna("Nao informado").value_counts().reset_index()
    contagem.columns = ["secretaria", "obras"]
    total = contagem["obras"].sum()
    fig = go.Figure(
        go.Treemap(
            labels=contagem["secretaria"],
            parents=[""] * len(contagem),
            values=contagem["obras"],
            marker=dict(
                colors=contagem["obras"],
                colorscale=[[0, TOKENS["surface_alt"]], [1, TOKENS["primary"]]],
                line=dict(color=TOKENS["bg"], width=2),
            ),
            textinfo="label+value+percent root",
            textfont=dict(size=12, color=TOKENS["bg"]),
            hovertemplate="%{label}<br>%{value} obras (%{percentRoot})<extra></extra>",
        )
    )
    return _layout_base(
        fig,
        "Volume de obras por secretaria",
        subtitulo=f"{total} obras distribuidas — quanto maior o bloco, mais obras",
        altura=380,
    )


def chart_ranking_valor_secretaria(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    agrupado = (
        df.groupby("secretaria", dropna=True)["valor_contratado"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .sort_values()
    )
    fig = go.Figure(
        go.Bar(
            x=agrupado.values,
            y=agrupado.index,
            orientation="h",
            marker=dict(color=TOKENS["primary"]),
            text=[_fmt_moeda_compacta(v) for v in agrupado.values],
            textposition="outside",
            textfont=dict(color=TOKENS["text"]),
            hovertemplate="%{y}<br>%{customdata}<extra></extra>",
            customdata=[_fmt_moeda(v) for v in agrupado.values],
        )
    )
    fig.update_xaxes(title="Valor contratado (R$)", tickprefix="R$ ", separatethousands=True)
    return _layout_base(
        fig,
        f"Ranking de secretarias por valor investido (top {top_n})",
        subtitulo="Soma do valor contratado das obras filtradas",
        altura=380,
    )


def chart_heatmap_secretaria_situacao(df: pd.DataFrame, top_n: int = 12) -> go.Figure:
    top_secretarias = df["secretaria"].fillna("Nao informado").value_counts().head(top_n).index
    recorte = df[df["secretaria"].fillna("Nao informado").isin(top_secretarias)]
    tabela = pd.crosstab(
        recorte["secretaria"].fillna("Nao informado"), recorte["situacao"].fillna("Nao informado")
    )
    # ordena as secretarias pelo total de obras, da maior para a menor
    tabela = tabela.loc[tabela.sum(axis=1).sort_values(ascending=True).index]

    fig = go.Figure(
        go.Heatmap(
            z=tabela.values,
            x=tabela.columns,
            y=tabela.index,
            colorscale=[[0, TOKENS["surface_alt"]], [1, TOKENS["primary"]]],
            hovertemplate="Secretaria: %{y}<br>Situacao: %{x}<br>Obras: %{z}<extra></extra>",
            colorbar=dict(title=dict(text="Obras", font=dict(color=TOKENS["text_muted"])), thickness=14, tickfont=dict(color=TOKENS["text_muted"])),
            texttemplate="%{z}",
            textfont=dict(color=TOKENS["bg"]),
        )
    )
    return _layout_base(
        fig,
        "Mapa de calor — secretaria x situacao",
        subtitulo=f"Top {min(top_n, len(tabela))} secretarias com mais obras",
        altura=420,
    )


def chart_timeline_cumulativo(df: pd.DataFrame) -> go.Figure:
    serie = df.dropna(subset=["inicio_obra"]).copy()
    if serie.empty:
        return _layout_base(go.Figure(), "Evolucao temporal das obras (sem datas informadas)")

    serie = serie.sort_values("inicio_obra")
    serie["mes"] = serie["inicio_obra"].dt.to_period("M").dt.to_timestamp()
    mensal = serie.groupby("mes").size().reset_index(name="novas_obras")
    mensal["acumulado"] = mensal["novas_obras"].cumsum()

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=mensal["mes"],
            y=mensal["novas_obras"],
            marker=dict(color=TOKENS["accent"]),
            name="Novas obras no mes",
            opacity=0.85,
            hovertemplate="%{x|%b/%Y}: %{y} novas obras<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=mensal["mes"],
            y=mensal["acumulado"],
            mode="lines",
            line=dict(color=TOKENS["primary"], width=2.5, shape="spline"),
            fill="tozeroy",
            fillcolor="rgba(79,216,196,0.12)",
            name="Total acumulado",
            hovertemplate="%{x|%b/%Y}: %{y} obras acumuladas<extra></extra>",
        )
    )
    fig.update_xaxes(title="Mes de inicio da obra")
    fig.update_yaxes(title="Quantidade de obras")
    return _layout_base(
        fig,
        "Evolucao temporal das obras",
        subtitulo=f"{int(mensal['acumulado'].iloc[-1])} obras acumuladas no periodo filtrado",
        altura=380,
    )


def chart_ranking_locais(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    agrupado = (
        df["logradouro"].fillna("Nao informado").value_counts().head(top_n).sort_values()
    )
    fig = go.Figure(
        go.Bar(
            x=agrupado.values,
            y=agrupado.index,
            orientation="h",
            marker=dict(color=TOKENS["primary_dim"]),
            text=agrupado.values,
            textposition="outside",
            textfont=dict(color=TOKENS["text"]),
            hovertemplate="%{y}: %{x} obras<extra></extra>",
        )
    )
    fig.update_xaxes(title="Quantidade de obras")
    return _layout_base(fig, f"Locais com mais obras (top {top_n})", altura=420)


# =============================================================================
# utils/risk.py
# =============================================================================

PESOS = {
    "paralisada_base": 45,
    "em_andamento_base": 8,
    "prazo_vencido": 25,
    "gap_cronograma": 0.5,  # multiplicador sobre o gap percentual (0-100)
}

LIMIAR_MEDIO = 30
LIMIAR_ALTO = 60


def _situacao_upper(valor) -> str:
    return str(valor or "").strip().upper()


def _calcular_linha(row: pd.Series, hoje: pd.Timestamp) -> tuple[float, str]:
    situacao = _situacao_upper(row.get("situacao"))

    if "CONCLU" in situacao or "FINALIZ" in situacao:
        return 0.0, "Obra concluida."

    score = 0.0
    motivos: list[str] = []

    if "PARALIS" in situacao:
        score += PESOS["paralisada_base"]
        motivos.append("obra paralisada")
    else:
        score += PESOS["em_andamento_base"]

    prazo_fim = row.get("termino_contrato")
    if pd.isna(prazo_fim):
        prazo_fim = row.get("limite_execucao")

    if pd.notna(prazo_fim) and hoje > prazo_fim:
        score += PESOS["prazo_vencido"]
        motivos.append("prazo contratual vencido")

    inicio = row.get("inicio_obra")
    if pd.isna(inicio):
        inicio = row.get("data_contrato")

    if pd.notna(inicio) and pd.notna(prazo_fim) and prazo_fim > inicio:
        dias_totais = (prazo_fim - inicio).days or 1
        dias_decorridos = max(0, min((hoje - inicio).days, dias_totais))
        tempo_pct = dias_decorridos / dias_totais * 100
        exec_pct = row.get("pct_executado")
        exec_pct = 0.0 if pd.isna(exec_pct) else float(exec_pct)
        gap = tempo_pct - exec_pct
        if gap > 0:
            score += min(gap, 100) * PESOS["gap_cronograma"]
        if gap > 20:
            motivos.append("execucao abaixo do cronograma")

    if not motivos:
        motivos.append("sem sinais criticos")

    return min(round(score, 1), 100.0), ", ".join(motivos)


def _classificar(score: float) -> str:
    if score >= LIMIAR_ALTO:
        return "Alto risco"
    if score >= LIMIAR_MEDIO:
        return "Medio risco"
    return "Baixo risco"


def compute_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona as colunas risco_score, risco_nivel e risco_motivo."""
    if df.empty:
        resultado = df.copy()
        resultado["risco_score"] = pd.Series(dtype=float)
        resultado["risco_nivel"] = pd.Series(dtype=str)
        resultado["risco_motivo"] = pd.Series(dtype=str)
        return resultado

    hoje = pd.Timestamp.now().normalize()
    resultado = df.copy()

    calculos = resultado.apply(lambda row: _calcular_linha(row, hoje), axis=1)
    resultado["risco_score"] = [c[0] for c in calculos]
    resultado["risco_motivo"] = [c[1] for c in calculos]
    resultado["risco_nivel"] = resultado["risco_score"].apply(_classificar)

    return resultado


# =============================================================================
# utils/ai_tools.py
# =============================================================================

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

INTENTS_DISPONIVEIS = [
    "resumo_geral",
    "contar_por_situacao",
    "obras_atrasadas",
    "secretaria_com_mais_obras",
    "ranking_secretarias",
    "listar_por_situacao",
    "local_com_mais_investimento",
    "total_investido",
]

CATALOGO_PROMPT = """
Voce classifica perguntas em portugues sobre um painel de obras publicas
dentro de um catalogo fixo de intencoes. Responda SOMENTE com um JSON
no formato {"intent": "...", "params": {...}}, sem nenhum texto adicional.

Intencoes disponiveis:
- resumo_geral: visao geral (nenhum parametro)
- contar_por_situacao: conta obras de uma situacao. params: {"situacao": "texto ou null"}
- obras_atrasadas: lista obras com prazo vencido e nao concluidas (nenhum parametro)
- secretaria_com_mais_obras: qual secretaria tem mais obras (nenhum parametro)
- ranking_secretarias: ranking de secretarias. params: {"top_n": int, "metrica": "quantidade" ou "valor"}
- listar_por_situacao: lista obras de uma situacao especifica. params: {"situacao": "texto"}
- local_com_mais_investimento: bairro/logradouro com mais valor contratado (nenhum parametro)
- total_investido: soma dos valores contratados/executados (nenhum parametro)

Se a pergunta nao se encaixar em nenhuma intencao, responda
{"intent": "resumo_geral", "params": {}}.
"""


@dataclass
class RespostaAssistente:
    texto: str
    tabela: pd.DataFrame | None = None


def _fmt_moeda_ia(valor: float) -> str:
    if pd.isna(valor):
        valor = 0
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def classify_intent(pergunta: str) -> dict:
    """Usa o Groq apenas para mapear a pergunta a uma intencao pre-aprovada."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "sua-chave-groq-aqui":
        return {"intent": "erro_configuracao", "params": {}}

    try:
        from groq import Groq

        cliente = Groq(api_key=api_key)
        resposta = cliente.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": CATALOGO_PROMPT},
                {"role": "user", "content": pergunta},
            ],
        )
        bruto = resposta.choices[0].message.content
        dados = json.loads(bruto)
        if dados.get("intent") not in INTENTS_DISPONIVEIS:
            dados["intent"] = "resumo_geral"
        dados.setdefault("params", {})
        return dados
    except Exception:  # noqa: BLE001
        return {"intent": "erro_groq", "params": {}}


def _resumo_geral(df: pd.DataFrame, _params: dict) -> RespostaAssistente:
    total = len(df)
    por_situacao = df["situacao"].fillna("Nao informado").value_counts()
    linhas = "; ".join(f"{s}: {q}" for s, q in por_situacao.items())
    valor_total = df["valor_contratado"].sum()
    texto = (
        f"O painel possui {total} obras cadastradas, distribuidas assim por situacao: "
        f"{linhas}. O valor total contratado e {_fmt_moeda_ia(valor_total)}."
    )
    return RespostaAssistente(texto, por_situacao.reset_index().rename(
        columns={"index": "situacao", "situacao": "quantidade"}
    ))


def _contar_por_situacao(df: pd.DataFrame, params: dict) -> RespostaAssistente:
    situacao = (params.get("situacao") or "").strip()
    if not situacao:
        return _resumo_geral(df, params)
    mascara = df["situacao"].fillna("").str.upper().str.contains(situacao.upper())
    qtd = int(mascara.sum())
    return RespostaAssistente(f'Existem {qtd} obras com situacao contendo "{situacao}".')


def _obras_atrasadas(df: pd.DataFrame, _params: dict) -> RespostaAssistente:
    hoje = pd.Timestamp.now().normalize()
    prazo = df["termino_contrato"].fillna(df.get("limite_execucao"))
    nao_concluida = ~df["situacao"].fillna("").str.upper().str.contains("CONCLU|FINALIZ", regex=True)
    atrasadas = df[(prazo.notna()) & (prazo < hoje) & nao_concluida]
    colunas = [c for c in ["codigo", "secretaria", "situacao", "termino_contrato", "limite_execucao"] if c in atrasadas.columns]
    texto = f"Ha {len(atrasadas)} obras com prazo contratual vencido e ainda nao concluidas."
    return RespostaAssistente(texto, atrasadas[colunas].head(50) if len(atrasadas) else None)


def _secretaria_com_mais_obras(df: pd.DataFrame, _params: dict) -> RespostaAssistente:
    if df["secretaria"].dropna().empty:
        return RespostaAssistente("Nao ha dados de secretaria cadastrados.")
    contagem = df["secretaria"].value_counts()
    nome, qtd = contagem.index[0], contagem.iloc[0]
    return RespostaAssistente(f'A secretaria com mais obras e "{nome}", com {qtd} obras.', contagem.head(10).reset_index())


def _ranking_secretarias(df: pd.DataFrame, params: dict) -> RespostaAssistente:
    top_n = int(params.get("top_n") or 5)
    metrica = params.get("metrica", "quantidade")
    if metrica == "valor":
        agrupado = df.groupby("secretaria")["valor_contratado"].sum().sort_values(ascending=False).head(top_n)
        linhas = "; ".join(f"{s}: {_fmt_moeda_ia(v)}" for s, v in agrupado.items())
        texto = f"Ranking das {top_n} secretarias por valor contratado: {linhas}."
    else:
        agrupado = df["secretaria"].value_counts().head(top_n)
        linhas = "; ".join(f"{s}: {q}" for s, q in agrupado.items())
        texto = f"Ranking das {top_n} secretarias por quantidade de obras: {linhas}."
    return RespostaAssistente(texto, agrupado.reset_index())


def _listar_por_situacao(df: pd.DataFrame, params: dict) -> RespostaAssistente:
    situacao = (params.get("situacao") or "").strip()
    if not situacao:
        return _resumo_geral(df, params)
    mascara = df["situacao"].fillna("").str.upper().str.contains(situacao.upper())
    filtrado = df[mascara]
    colunas = [c for c in ["codigo", "secretaria", "descricao", "logradouro", "situacao"] if c in filtrado.columns]
    texto = f'{len(filtrado)} obras encontradas com situacao contendo "{situacao}".'
    return RespostaAssistente(texto, filtrado[colunas].head(50) if len(filtrado) else None)


def _local_com_mais_investimento(df: pd.DataFrame, _params: dict) -> RespostaAssistente:
    if df["logradouro"].dropna().empty:
        return RespostaAssistente("Nao ha dados de logradouro cadastrados.")
    agrupado = df.groupby("logradouro")["valor_contratado"].sum().sort_values(ascending=False)
    nome, valor = agrupado.index[0], agrupado.iloc[0]
    return RespostaAssistente(
        f'O local com maior investimento e "{nome}", com {_fmt_moeda_ia(valor)} contratados.',
        agrupado.head(10).reset_index(),
    )


def _total_investido(df: pd.DataFrame, _params: dict) -> RespostaAssistente:
    contratado = df["valor_contratado"].sum()
    executado = df["valor_executado"].sum()
    saldo = contratado - executado
    texto = (
        f"Valor total contratado: {_fmt_moeda_ia(contratado)}. "
        f"Valor total executado: {_fmt_moeda_ia(executado)}. "
        f"Saldo remanescente: {_fmt_moeda_ia(saldo)}."
    )
    return RespostaAssistente(texto)


_EXECUTORES = {
    "resumo_geral": _resumo_geral,
    "contar_por_situacao": _contar_por_situacao,
    "obras_atrasadas": _obras_atrasadas,
    "secretaria_com_mais_obras": _secretaria_com_mais_obras,
    "ranking_secretarias": _ranking_secretarias,
    "listar_por_situacao": _listar_por_situacao,
    "local_com_mais_investimento": _local_com_mais_investimento,
    "total_investido": _total_investido,
}


def responder(pergunta: str, df: pd.DataFrame) -> RespostaAssistente:
    if df.empty:
        return RespostaAssistente("Ainda nao ha obras carregadas para analisar.")

    classificacao = classify_intent(pergunta)
    intent = classificacao.get("intent")

    if intent == "erro_configuracao":
        return RespostaAssistente(
            "O assistente precisa de uma chave da Groq configurada em GROQ_API_KEY "
            "(arquivo .env) para interpretar perguntas em linguagem natural."
        )
    if intent == "erro_groq":
        return RespostaAssistente(
            "Nao foi possivel consultar o servico de IA agora. Tente novamente em instantes."
        )

    executor = _EXECUTORES.get(intent, _resumo_geral)
    try:
        return executor(df, classificacao.get("params", {}))
    except Exception as exc:  # noqa: BLE001
        return RespostaAssistente(f"Nao consegui calcular essa resposta ({exc}).")


# =============================================================================
# pages/1_Consulta_de_Obras.py  ->  render_pagina_consulta()
# =============================================================================

def render_pagina_consulta(df: pd.DataFrame) -> None:
    page_header(
        "Consulta",
        "Consulta de obras",
        "Pesquise, veja o detalhe completo e exporte os dados de qualquer obra do portfolio.",
    )

    df = compute_risk(df)

    if df.empty:
        st.info("Nenhuma obra corresponde aos filtros selecionados.")
        return

    col_lista, col_detalhe = st.columns([1, 1.4])

    with col_lista:
        st.markdown('<div class="section-title">Resultados</div>', unsafe_allow_html=True)
        tabela = df[["codigo", "secretaria", "situacao", "logradouro"]].reset_index(drop=True)
        selecao = st.dataframe(
            tabela,
            use_container_width=True,
            height=460,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="tabela_consulta",
        )

        st.download_button(
            "Exportar resultados filtrados (CSV)",
            data=df.drop(columns=["risco_score", "risco_nivel", "risco_motivo"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
            file_name="obras_filtradas.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_filtradas",
        )

    with col_detalhe:
        st.markdown('<div class="section-title">Detalhe da obra</div>', unsafe_allow_html=True)

        linhas_selecionadas = selecao.selection.rows if selecao and selecao.selection else []
        if not linhas_selecionadas:
            st.markdown(
                '<div class="panel-card">Selecione uma obra na tabela ao lado para ver o detalhe completo.</div>',
                unsafe_allow_html=True,
            )
        else:
            obra = df.iloc[linhas_selecionadas[0]]

            cor_situacao = situacao_color(obra.get("situacao"))
            cor_risco = risco_color(obra.get("risco_nivel"))

            st.markdown(
                f"""
                <div class="panel-card">
                    <div class="obra-codigo" style="font-size:1.05rem;">{obra.get('codigo', '—')}</div>
                    <div style="font-size:1.05rem; font-weight:600; margin:0.15rem 0 0.5rem 0;">
                        {obra.get('descricao') or 'Sem descricao cadastrada'}
                    </div>
                    <span class="badge" style="background-color:{cor_situacao};">{obra.get('situacao') or 'Nao informado'}</span>
                    <span class="badge" style="background-color:{cor_risco}; margin-left:0.4rem;">{obra.get('risco_nivel', '—')}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("<br>", unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Valor contratado", f"R$ {obra.get('valor_contratado', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                st.metric("Percentual executado", f"{(obra.get('pct_executado') or 0):.1f}%")
            with c2:
                st.metric("Valor executado", f"R$ {obra.get('valor_executado', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                st.metric("Saldo do contrato", f"R$ {obra.get('saldo_contrato', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            st.markdown('<div class="section-title">Local e responsaveis</div>', unsafe_allow_html=True)
            st.write(f"**Logradouro:** {obra.get('logradouro') or '—'}")
            st.write(f"**Intervencao:** {obra.get('intervencao') or '—'}")
            st.write(f"**Secretaria:** {obra.get('secretaria') or '—'}")
            st.write(f"**Empresa executora:** {obra.get('empresa_executora') or '—'}")
            st.write(f"**Fiscal da obra:** {obra.get('fiscal_obra') or '—'}")

            st.markdown('<div class="section-title">Historico contratual</div>', unsafe_allow_html=True)
            datas = {
                "Data do contrato": obra.get("data_contrato"),
                "Inicio da obra": obra.get("inicio_obra"),
                "Limite de execucao": obra.get("limite_execucao"),
                "Termino do contrato": obra.get("termino_contrato"),
            }
            for label, valor in datas.items():
                valor_fmt = valor.strftime("%d/%m/%Y") if pd.notna(valor) else "—"
                st.write(f"**{label}:** {valor_fmt}")

            st.write(f"**Numero da licitacao:** {obra.get('num_licitacao') or '—'}")
            st.write(f"**Numero do contrato:** {obra.get('num_contrato') or '—'}")
            st.write(f"**Ordem de servico:** {obra.get('num_ordem_servico') or '—'}")
            st.write(f"**Tipo de recurso:** {obra.get('tipo_recurso') or '—'}")

            st.caption(f"Indice de atencao: {obra.get('risco_score', 0):.0f}/100 — {obra.get('risco_motivo', '')}")

            st.download_button(
                "Exportar esta obra (CSV)",
                data=obra.to_frame().T.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"obra_{obra.get('codigo', 'obra')}.csv",
                mime="text/csv",
                key="download_obra_unica",
            )


# =============================================================================
# pages/2_Analise_de_Risco.py  ->  render_pagina_risco()
# =============================================================================

def render_pagina_risco(df: pd.DataFrame) -> None:
    page_header(
        "Fiscalizacao",
        "Indice de atencao da obra",
        "Pontuacao automatica que combina prazo, situacao e ritmo de execucao "
        "para indicar quais obras merecem atencao prioritaria.",
    )

    df = compute_risk(df)

    if df.empty:
        st.info("Nenhuma obra corresponde aos filtros selecionados.")
        return

    contagem_risco = df["risco_nivel"].value_counts()
    ordem = ["Alto risco", "Medio risco", "Baixo risco"]
    contagem_risco = contagem_risco.reindex(ordem).fillna(0)

    col_kpi, col_grafico = st.columns([1, 1.6])

    with col_kpi:
        for nivel in ordem:
            qtd = int(contagem_risco.get(nivel, 0))
            st.markdown(
                f"""
                <div class="kpi-card" style="margin-bottom:0.7rem; border-left: 5px solid {risco_color(nivel)};">
                    <div class="kpi-label">{nivel}</div>
                    <div class="kpi-value">{qtd}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_grafico:
        fig = go.Figure(
            go.Bar(
                x=ordem,
                y=[contagem_risco.get(n, 0) for n in ordem],
                marker=dict(color=[risco_color(n) for n in ordem]),
                text=[int(contagem_risco.get(n, 0)) for n in ordem],
                textposition="outside",
                textfont=dict(color=TOKENS["text"]),
            )
        )
        fig.update_yaxes(title="Quantidade de obras", **_EIXO_COMUM)
        fig.update_xaxes(**_EIXO_COMUM)
        fig.update_layout(
            title=dict(text="<b>Distribuicao por nivel de risco</b>", font=dict(family=FONT_DISPLAY, size=15, color=TOKENS["text"]), x=0, xanchor="left"),
            font=dict(family=FONT_BODY, size=12, color=TOKENS["text"]),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=320,
            margin=dict(l=10, r=10, t=48, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="section-title">Obras que precisam de atencao</div>', unsafe_allow_html=True)

    prioritarias = df[df["risco_nivel"] == "Alto risco"].sort_values("risco_score", ascending=False)

    if prioritarias.empty:
        st.success("Nenhuma obra classificada como alto risco no recorte atual.")
    else:
        colunas = [
            "codigo", "secretaria", "situacao", "risco_score", "risco_motivo",
            "pct_executado", "termino_contrato", "empresa_executora", "fiscal_obra",
        ]
        colunas = [c for c in colunas if c in prioritarias.columns]
        st.dataframe(
            prioritarias[colunas].rename(columns={
                "codigo": "Codigo",
                "secretaria": "Secretaria",
                "situacao": "Situacao",
                "risco_score": "Indice",
                "risco_motivo": "Motivo",
                "pct_executado": "% executado",
                "termino_contrato": "Termino do contrato",
                "empresa_executora": "Empresa executora",
                "fiscal_obra": "Fiscal",
            }),
            use_container_width=True,
            hide_index=True,
            height=420,
        )

        st.download_button(
            "Exportar obras de alto risco (CSV)",
            data=prioritarias.to_csv(index=False).encode("utf-8-sig"),
            file_name="obras_alto_risco.csv",
            mime="text/csv",
            key="download_alto_risco",
        )

    with st.expander("Como o indice de atencao e calculado"):
        st.write(
            "A pontuacao (0 a 100) considera: situacao atual da obra, se o prazo "
            "contratual ja venceu, e o descompasso entre o percentual do tempo "
            "de contrato ja decorrido e o percentual efetivamente executado. "
            "Obras concluidas recebem pontuacao zero. E uma heuristica de apoio "
            "a priorizacao da fiscalizacao, nao uma auditoria formal."
        )


# =============================================================================
# pages/3_Assistente_IA.py  ->  render_pagina_assistente()
# =============================================================================

def render_pagina_assistente(obras: pd.DataFrame) -> None:
    page_header(
        "Assistente",
        "Assistente inteligente",
        "Pergunte em portugues sobre o portfolio de obras. O assistente interpreta a "
        "pergunta e calcula a resposta diretamente sobre os dados carregados — "
        "sem gerar ou executar SQL livre contra o banco de producao.",
    )

    if "historico_chat" not in st.session_state:
        st.session_state.historico_chat = []

    sugestoes = [
        "Quantas obras estao atrasadas?",
        "Qual secretaria possui mais obras?",
        "Liste obras paralisadas",
        "Qual local recebeu mais investimentos?",
    ]

    st.markdown('<div class="section-title">Perguntas frequentes</div>', unsafe_allow_html=True)
    colunas = st.columns(len(sugestoes))
    pergunta_rapida = None
    for coluna, sugestao in zip(colunas, sugestoes):
        with coluna:
            if st.button(sugestao, use_container_width=True, key=f"sugestao_{sugestao}"):
                pergunta_rapida = sugestao

    for mensagem in st.session_state.historico_chat:
        with st.chat_message(mensagem["papel"]):
            st.write(mensagem["conteudo"])
            if mensagem.get("tabela") is not None:
                st.dataframe(mensagem["tabela"], use_container_width=True, hide_index=True)

    pergunta = st.chat_input("Pergunte algo sobre as obras...") or pergunta_rapida

    if pergunta:
        st.session_state.historico_chat.append({"papel": "user", "conteudo": pergunta})
        with st.chat_message("user"):
            st.write(pergunta)

        with st.chat_message("assistant"):
            with st.spinner("Analisando o portfolio..."):
                resultado = responder(pergunta, obras)
            st.write(resultado.texto)
            if resultado.tabela is not None and not resultado.tabela.empty:
                st.dataframe(resultado.tabela, use_container_width=True, hide_index=True)

        st.session_state.historico_chat.append(
            {"papel": "assistant", "conteudo": resultado.texto, "tabela": resultado.tabela}
        )


# =============================================================================
# app.py — pagina inicial (Dashboard Executivo) + navegacao entre abas
# =============================================================================

def render_pagina_dashboard(df: pd.DataFrame) -> None:
    page_header(
        "Painel executivo",
        "Gestao de obras publicas",
        "Visao consolidada do portfolio de obras da Prefeitura de Blumenau, "
        "atualizada a partir da base oficial.",
    )

    if df.empty:
        st.info("Nenhuma obra corresponde aos filtros selecionados.")
        return

    render_status_ribbon(df)
    render_kpis(df)

    st.markdown("<br>", unsafe_allow_html=True)

    col_gauge, col_agua = st.columns([1, 1.6])
    with col_gauge:
        st.plotly_chart(chart_indicador_execucao(df), use_container_width=True, config={"displayModeBar": False})
    with col_agua:
        st.plotly_chart(chart_financeiro_waterfall(df), use_container_width=True, config={"displayModeBar": False})

    col1, col2 = st.columns([1, 1.3])
    with col1:
        st.plotly_chart(chart_situacao_bar(df), use_container_width=True, config={"displayModeBar": False})
    with col2:
        st.plotly_chart(chart_secretarias_treemap(df), use_container_width=True, config={"displayModeBar": False})

    st.plotly_chart(chart_ranking_valor_secretaria(df), use_container_width=True, config={"displayModeBar": False})

    st.plotly_chart(chart_heatmap_secretaria_situacao(df), use_container_width=True, config={"displayModeBar": False})

    col5, col6 = st.columns([1.2, 1])
    with col5:
        st.plotly_chart(chart_timeline_cumulativo(df), use_container_width=True, config={"displayModeBar": False})
    with col6:
        st.plotly_chart(chart_ranking_locais(df), use_container_width=True, config={"displayModeBar": False})

    st.caption(
        "Fonte: banco de dados obrasblumenau (MySQL), replicado do portal oficial "
        "engegov.blumenau.sc.gov.br. Dados atualizados a cada 2 minutos."
    )


def main() -> None:
    st.set_page_config(
        page_title="Obras Blumenau — Painel Executivo",
        page_icon=":material/monitoring:",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inject_css()

    with st.sidebar:
        st.markdown("## Obras Blumenau")
        ok, mensagem = check_api_health()
        cor = TOKENS["risco_baixo"] if ok else TOKENS["risco_alto"]
        st.markdown(
            f'<div style="font-size:0.78rem; margin-bottom:0.8rem;">'
            f'<span style="color:{cor};">&#9679;</span> {mensagem}</div>',
            unsafe_allow_html=True,
        )

    try:
        obras = fetch_obras()
    except APIError as exc:
        page_header(
            "Painel executivo",
            "Gestao de obras publicas",
            "Visao consolidada do portfolio de obras da Prefeitura de Blumenau.",
        )
        st.error(str(exc))
        return

    if obras.empty:
        page_header(
            "Painel executivo",
            "Gestao de obras publicas",
            "Visao consolidada do portfolio de obras da Prefeitura de Blumenau.",
        )
        st.warning(
            "Nenhuma obra encontrada na tabela 'obras'. Confira se ha dados "
            "cadastrados no banco obrasblumenau."
        )
        return

    aba_dashboard, aba_consulta, aba_risco, aba_assistente = st.tabs(
        ["Dashboard executivo", "Consulta de obras", "Analise de risco", "Assistente inteligente"]
    )

    df_filtrado = render_sidebar_filters(obras, key_prefix="global")

    with aba_dashboard:
        render_pagina_dashboard(df_filtrado)

    with aba_consulta:
        render_pagina_consulta(df_filtrado)

    with aba_risco:
        render_pagina_risco(df_filtrado)

    with aba_assistente:
        render_pagina_assistente(obras)


if __name__ == "__main__":
    main()
