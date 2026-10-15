"""Formatação de números e datas no padrão brasileiro."""

import unicodedata

import pandas as pd


def _trocar_separadores(texto):
    # 1,234.56 -> 1.234,56
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def moeda(valor):
    """1234.5 -> 'R$ 1.234,50'."""
    if pd.isna(valor):
        return "-"
    return "R$ " + _trocar_separadores(f"{valor:,.2f}")


def moeda_sem_centavos(valor):
    """1992408.56 -> 'R$ 1.992.409'. Usado nos números grandes da tela, onde os centavos não cabem."""
    if pd.isna(valor):
        return "-"
    return "R$ " + _trocar_separadores(f"{valor:,.0f}")


def moeda_curta(valor):
    """Versão curta para rótulos de gráfico: 'R$ 148,8 mi', 'R$ 850 mil'."""
    if pd.isna(valor):
        return "-"
    for limite, sufixo in ((1e9, "bi"), (1e6, "mi")):
        if abs(valor) >= limite:
            return f"R$ {valor / limite:.1f} {sufixo}".replace(".", ",")
    if abs(valor) >= 1e3:
        return f"R$ {valor / 1e3:.0f} mil"
    return f"R$ {valor:.0f}"


def inteiro(valor):
    return _trocar_separadores(f"{valor:,.0f}")


def percentual(valor):
    if pd.isna(valor):
        return "-"
    return f"{valor:.0f}%"


def data(valor):
    if pd.isna(valor):
        return "-"
    return valor.strftime("%d/%m/%Y")


def sem_acento(texto):
    """'CONCLUÍDA' -> 'concluida'. Usado nas buscas, para o acento não atrapalhar."""
    normalizado = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn").lower()
