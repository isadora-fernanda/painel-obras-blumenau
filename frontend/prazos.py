"""Compara o andamento de cada obra com o prazo do contrato.

Uma obra não concluída entra na lista de atenção quando:
- está paralisada;
- o prazo final do contrato já passou;
- o percentual executado está 20 pontos ou mais abaixo do percentual do prazo já decorrido
  (por exemplo, 70% do prazo passou e só 40% da obra foi executada).
"""

import pandas as pd

from dados import CONCLUIDA, PARALISADA

DIFERENCA_MINIMA = 20  # pontos percentuais entre prazo decorrido e execução


def avaliar_prazos(df, hoje=None):
    hoje = pd.Timestamp(hoje or pd.Timestamp.today()).normalize()
    r = df.copy()

    inicio = r["inicio_obra"].fillna(r["data_contrato"])
    duracao = (r["prazo_final"] - inicio).dt.days
    decorrido = (hoje - inicio).dt.days

    r["pct_prazo"] = (decorrido / duracao * 100).clip(0, 100).where(duracao > 0)
    r["dias_vencido"] = (hoje - r["prazo_final"]).dt.days.where(lambda d: d > 0)
    r["diferenca"] = r["pct_prazo"] - r["pct_executado"]

    aberta = r["situacao"] != CONCLUIDA
    r["paralisada"] = r["situacao"] == PARALISADA
    r["prazo_vencido"] = aberta & r["dias_vencido"].notna()
    r["abaixo_do_prazo"] = aberta & (r["diferenca"] >= DIFERENCA_MINIMA)
    r["atencao"] = r["paralisada"] | r["prazo_vencido"] | r["abaixo_do_prazo"]
    r["motivo"] = r.apply(_motivo, axis=1)
    return r


def _motivo(obra):
    partes = []
    if obra["paralisada"]:
        partes.append("paralisada")
    if obra["prazo_vencido"]:
        partes.append(f"prazo vencido há {int(obra['dias_vencido'])} dias")
    if obra["abaixo_do_prazo"]:
        partes.append(
            f"{obra['pct_executado']:.0f}% executado com {obra['pct_prazo']:.0f}% do prazo decorrido"
        )
    return "; ".join(partes)


def obras_em_atencao(df_avaliado):
    """Paralisadas primeiro, depois as de prazo vencido há mais tempo."""
    return df_avaliado[df_avaliado["atencao"]].sort_values(
        ["paralisada", "dias_vencido", "diferenca"], ascending=False, na_position="last"
    )
