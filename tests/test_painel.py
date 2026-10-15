"""Testes da preparação dos dados, dos filtros, dos prazos e do assistente (sem banco)."""

import sys
import unittest
import unittest.mock
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "frontend"))
import assistente  # noqa: E402
import formatar  # noqa: E402
import graficos  # noqa: E402
from dados import Filtros, aplicar_filtros, preparar  # noqa: E402
from prazos import avaliar_prazos, obras_em_atencao  # noqa: E402

HOJE = "2026-10-15"


def obras_exemplo():
    """Obras fictícias, no formato que sai do MySQL (Decimal vira texto, datas como texto)."""
    linhas = [
        # código, secretaria, descrição, situação, contratado, executado, %, início, término
        ("100", "SEMOB", "Pavimentação da Rua A", "EM ANDAMENTO", "1000000.00", "200000.00", 20, "2025-10-15", "2026-10-15"),
        ("101", "SEMOB", "Drenagem da Rua B", "PARALISADA", "500000.00", "100000.00", 20, "2025-01-01", "2026-12-31"),
        ("102", "SEMED", "Reforma da Escola C", "EM ANDAMENTO", "300000.00", "150000.00", 50, "2026-04-15", "2027-04-15"),
        ("103", "SEMED", "Construção da Creche D", "CONCLUÍDA", "800000.00", "800000.00", 100, "2023-01-01", "2024-01-01"),
        ("C104", "SEMUS", "Projeto do Posto E", "EM ANDAMENTO", None, None, None, None, None),
    ]
    colunas = ["codigo", "secretaria", "descricao", "situacao", "valor_contratado",
               "valor_executado", "pct_executado", "inicio_obra", "termino_contrato"]
    df = pd.DataFrame(linhas, columns=colunas)
    for coluna in ["logradouro", "intervencao", "empresa_executora", "limite_execucao",
                   "data_contrato", "saldo_contrato"]:
        df[coluna] = None
    df["data_contrato"] = df["inicio_obra"]
    df.loc[0, "empresa_executora"] = "Construtora Exemplo"
    return preparar(df)


class FormatarTests(unittest.TestCase):
    def test_moeda(self):
        self.assertEqual(formatar.moeda(1234567.8), "R$ 1.234.567,80")
        self.assertEqual(formatar.moeda_curta(148_750_000), "R$ 148,8 mi")
        self.assertEqual(formatar.moeda_curta(850_000), "R$ 850 mil")

    def test_sem_acento(self):
        self.assertEqual(formatar.sem_acento("CONCLUÍDA"), "concluida")


class FiltrosTests(unittest.TestCase):
    def setUp(self):
        self.df = obras_exemplo()

    def test_busca_ignora_acento_e_caracteres_especiais(self):
        self.assertEqual(len(aplicar_filtros(self.df, Filtros(busca="construcao"))), 1)
        self.assertEqual(len(aplicar_filtros(self.df, Filtros(busca="rua a ("))), 0)

    def test_filtro_por_secretaria_e_situacao(self):
        filtros = Filtros(secretarias=["SEMOB"], situacoes=["PARALISADA"])
        self.assertEqual(list(aplicar_filtros(self.df, filtros)["codigo"]), ["101"])

    def test_sem_filtro_de_ano_mantem_obras_sem_data(self):
        self.assertEqual(len(aplicar_filtros(self.df, Filtros())), 5)
        self.assertEqual(len(aplicar_filtros(self.df, Filtros(anos=(2025, 2026)))), 3)


class PrazosTests(unittest.TestCase):
    def setUp(self):
        self.avaliadas = avaliar_prazos(obras_exemplo(), hoje=HOJE).set_index("codigo")

    def test_execucao_abaixo_do_prazo(self):
        # 100% do prazo decorrido e só 20% executado
        self.assertTrue(self.avaliadas.loc["100", "abaixo_do_prazo"])

    def test_paralisada_entra_na_lista(self):
        self.assertTrue(self.avaliadas.loc["101", "atencao"])
        self.assertIn("paralisada", self.avaliadas.loc["101", "motivo"])

    def test_obra_em_dia_e_concluida_ficam_de_fora(self):
        # 102: metade do prazo e 50% executado; 103: concluída, mesmo com o prazo passado
        self.assertFalse(self.avaliadas.loc["102", "atencao"])
        self.assertFalse(self.avaliadas.loc["103", "atencao"])

    def test_obra_sem_datas_nao_quebra(self):
        self.assertFalse(self.avaliadas.loc["C104", "atencao"])

    def test_paralisadas_primeiro(self):
        ordem = list(obras_em_atencao(self.avaliadas.reset_index())["codigo"])
        self.assertEqual(ordem[0], "101")


class AssistenteTests(unittest.TestCase):
    def setUp(self):
        self.df = obras_exemplo()

    def test_sinonimos_de_situacao(self):
        self.assertEqual(assistente.por_palavras_chave("tem obra parada?")[1]["situacao"], "PARALISADA")
        self.assertEqual(assistente.por_palavras_chave("quantas já terminaram?")[1],
                         {"situacao": "CONCLUÍDA", "so_contar": True})

    def test_palavras_chave(self):
        self.assertEqual(assistente.por_palavras_chave("Quantas obras estão atrasadas?")[0], "atrasadas")
        self.assertEqual(assistente.por_palavras_chave("Mostre a obra c104"),
                         ("detalhe_obra", {"codigo": "c104"}))
        self.assertEqual(assistente.por_palavras_chave("Secretaria com mais investimento")[1],
                         {"metrica": "valor"})

    def test_conta_paralisadas_no_singular(self):
        resposta = assistente.responder("Quantas obras estão paralisadas?", self.df)
        self.assertEqual(resposta.texto, "1 obra está paralisada.")

    def test_origem_do_recurso(self):
        self.assertEqual(assistente.por_palavras_chave("De onde vem o dinheiro?")[0], "por_recurso")

    def test_investimento(self):
        resposta = assistente.responder("Quanto foi investido?", self.df)
        self.assertIn("R$ 2.600.000,00", resposta.texto)

    def test_com_chave_a_ia_interpreta_a_pergunta(self):
        with unittest.mock.patch.dict("os.environ", {"GROQ_API_KEY": "chave-de-teste"}), \
             unittest.mock.patch.object(assistente, "pela_groq",
                                        return_value=("por_situacao", {"situacao": "cancelada"})) as ia:
            # "cancelada" não é uma situação do portal; vira resumo em vez de quebrar
            self.assertTrue(assistente.responder("tem obra parada?", self.df).texto.startswith("São 5 obras"))
        with unittest.mock.patch.dict("os.environ", {"GROQ_API_KEY": "chave-de-teste"}), \
             unittest.mock.patch.object(assistente, "pela_groq",
                                        return_value=("por_situacao", {"situacao": "paralisada", "so_contar": True})):
            resposta = assistente.responder("tem alguma obra parada?", self.df)
        ia.assert_called_once()
        self.assertEqual(resposta.texto, "1 obra está paralisada.")
        self.assertIn("IA", resposta.fonte)

    def test_groq_fora_do_ar_usa_palavras_chave(self):
        with unittest.mock.patch.dict("os.environ", {"GROQ_API_KEY": "chave-de-teste"}), \
             unittest.mock.patch.object(assistente, "pela_groq", side_effect=ConnectionError):
            resposta = assistente.responder("Quantas obras estão paralisadas?", self.df)
        self.assertEqual(resposta.texto, "1 obra está paralisada.")
        self.assertIn("não respondeu", resposta.fonte)

    def test_pergunta_desconhecida_sem_groq(self):
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            resposta = assistente.responder("Qual a cor do céu?", self.df)
        self.assertTrue(resposta.texto.startswith("Não entendi"))


class GraficosTests(unittest.TestCase):
    def test_graficos_sao_gerados(self):
        df = obras_exemplo()
        graficos.obras_por_secretaria(df)
        graficos.valor_por_secretaria(df)
        graficos.contratos_por_ano(df)
        graficos.valor_por_recurso(df)
        _, pontos = graficos.execucao_x_prazo(avaliar_prazos(df, hoje=HOJE))
        self.assertEqual(pontos, 3)  # C104 não tem datas e a 103 está concluída


if __name__ == "__main__":
    unittest.main()
