"""Testes do scraper com respostas XML de exemplo, no formato do PrimeFaces (sem internet)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import scraper  # noqa: E402

RESPOSTA_TABELA = """<?xml version="1.0" encoding="UTF-8"?>
<partial-response><changes>
<update id="frmListaObras:tblListaObras"><![CDATA[
<table><tbody>
<tr><td>3849</td><td>SEMOB</td><td>REQUALIFICAÇÃO VIÁRIA DA RUA SANTA TEREZINHA</td>
<td>RUA SANTA TEREZINHA</td><td>Execução de Obra</td><td>EM ANDAMENTO</td></tr>
</tbody></table>]]></update>
<update id="j_id1:javax.faces.ViewState:0"><![CDATA[novo-viewstate]]></update>
</changes></partial-response>"""

# Mesma estrutura do HTML que o portal devolve ao clicar na obra 3657 (conferida em out/2026),
# com quebras de linha dentro dos rótulos e o percentual no input do gráfico circular.
RESPOSTA_DETALHE = """<?xml version="1.0" encoding="UTF-8"?>
<partial-response><changes>
<update id="frmAndamentoObra"><![CDATA[<form id="frmAndamentoObra">
<span class="icon-label">Valor Total Contratado</span> <span>R$
\t\t\t1.992.408,56
\t\t</span>
<span class="icon-label">Valor
\t\t\tExecutado (Medido)</span> <span>R$ 857.336,39</span>
<span class="icon-label">Saldo
\t\t\tdo Contrato</span> <span>R$ 1.135.072,17</span>
<span class="icon-label">Percentual
\t\t\tExecutado</span>
<div class="knob-container"><input id="frmAndamentoObra:j_idt138" value="43" class="knob" /></div>
<script>PrimeFaces.cw("Knob","widget_frmAndamentoObra_j_idt138",{labelTemplate:"43%"});</script>
</form>]]></update>
<update id="frmDadosContratoObra"><![CDATA[<form id="frmDadosContratoObra">
<label class="ui-outputlabel ui-widget">Empresa:</label>
<label class="ui-outputlabel ui-widget">CONSTRUTORA EXEMPLO LTDA</label>
<label class="ui-outputlabel ui-widget">CNPJ:</label>
<label class="ui-outputlabel ui-widget">12.345.678/0001-90</label>
<label class="ui-outputlabel ui-widget">Nº Processo Licitatório:</label>
<label class="ui-outputlabel ui-widget">Não Cadastrado!</label>
<label class="ui-outputlabel ui-widget">Número do Contrato:</label>
<label class="ui-outputlabel ui-widget">257/2025</label>
<label class="ui-outputlabel ui-widget">Data do Contrato:</label>
<label class="ui-outputlabel ui-widget">07/11/2025</label>
<label class="ui-outputlabel ui-widget">Nº Ordem de Serviço:</label>
<label class="ui-outputlabel ui-widget">015/2025</label>
<label class="ui-outputlabel ui-widget">Valor Total Contratado:</label>
<label class="ui-outputlabel ui-widget">1.992.408,56</label>
<label class="ui-outputlabel ui-widget">Início da obra:</label>
<label class="ui-outputlabel ui-widget">04/12/0202</label>
<label class="ui-outputlabel ui-widget">Data Limite Execução:</label>
<label class="ui-outputlabel ui-widget">08/09/2026</label>
<label class="ui-outputlabel ui-widget">Término Contrato:</label>
<label class="ui-outputlabel ui-widget">22/09/2026</label>
<label class="ui-outputlabel ui-widget">Tipo de Recurso:</label>
<label class="ui-outputlabel ui-widget">Operação de crédito externa</label>
</form>]]></update>
</changes></partial-response>"""


class ConversaoTests(unittest.TestCase):
    def test_valor_em_reais(self):
        self.assertEqual(scraper.converter_valor("R$ 1.234.567,89"), 1234567.89)
        self.assertEqual(scraper.converter_valor(""), 0)
        self.assertEqual(scraper.converter_valor("abc"), 0)

    def test_data_brasileira(self):
        self.assertEqual(scraper.converter_data("31/12/2025"), "2025-12-31")
        self.assertIsNone(scraper.converter_data("Não Cadastrado"))
        self.assertIsNone(scraper.converter_data("16/05/0202"))

    def test_texto_nao_cadastrado_vira_vazio(self):
        self.assertIsNone(scraper.limpar_texto("Não Cadastrado!"))
        self.assertEqual(scraper.limpar_texto("  SEMOB "), "SEMOB")


class RespostaTests(unittest.TestCase):
    def test_viewstate_novo(self):
        self.assertEqual(scraper.atualizar_viewstate(RESPOSTA_TABELA), "novo-viewstate")

    def test_linha_da_tabela(self):
        obra = scraper.ler_linha_da_tabela(RESPOSTA_TABELA, "3849")
        self.assertEqual(obra["secretaria"], "SEMOB")
        self.assertEqual(obra["situacao"], "EM ANDAMENTO")
        self.assertIsNone(scraper.ler_linha_da_tabela(RESPOSTA_TABELA, "9999"))

    def test_dados_do_contrato(self):
        contrato = scraper.extrair_contrato(RESPOSTA_DETALHE)
        self.assertEqual(contrato["empresa_executora"], "CONSTRUTORA EXEMPLO LTDA")
        self.assertEqual(contrato["cnpj_empresa"], "12.345.678/0001-90")
        self.assertEqual(contrato["num_contrato"], "257/2025")
        self.assertEqual(contrato["tipo_recurso"], "Operação de crédito externa")
        self.assertEqual(contrato["termino_contrato"], "2026-09-22")
        self.assertEqual(contrato["valor_contratado"], 1992408.56)

    def test_campo_nao_cadastrado_e_data_digitada_errado(self):
        contrato = scraper.extrair_contrato(RESPOSTA_DETALHE)
        self.assertIsNone(contrato["num_licitacao"])
        self.assertIsNone(contrato["inicio_obra"])  # 04/12/0202 no portal

    def test_andamento_com_rotulos_quebrados_em_linhas(self):
        andamento = scraper.extrair_andamento(RESPOSTA_DETALHE)
        self.assertEqual(andamento["valor_contratado"], 1992408.56)
        self.assertEqual(andamento["valor_executado"], 857336.39)
        self.assertEqual(andamento["saldo_contrato"], 1135072.17)
        self.assertEqual(andamento["pct_executado"], 43.0)


if __name__ == "__main__":
    unittest.main()
