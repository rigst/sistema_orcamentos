"""Padrões de componente: toda tela usa a mesma anatomia de tabela, formulário
e cabeçalho. Os testes varrem os templates para não nascer exceção nova."""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.identificacao import PALETA_IDENTIFICACAO, cor_por_id, iniciais_de

TEMPLATES = Path(settings.BASE_DIR) / "templates"


def _templates():
    return sorted(TEMPLATES.rglob("*.html"))


class IdentificacaoTests(SimpleTestCase):
    def test_iniciais(self):
        self.assertEqual(iniciais_de("Expointer pavilhão 3"), "EP")
        self.assertEqual(iniciais_de("Festival"), "FE")
        self.assertEqual(iniciais_de("2026 - Mostra Casa Cor"), "MC")
        self.assertEqual(iniciais_de("   "), "#")
        self.assertEqual(iniciais_de("ação social"), "AS")

    def test_cor_fixa_pelo_id(self):
        self.assertEqual(cor_por_id(3), cor_por_id(3 + len(PALETA_IDENTIFICACAO)))
        self.assertEqual(cor_por_id(None), PALETA_IDENTIFICACAO[0])


class TabelasTests(SimpleTestCase):
    def test_toda_tabela_de_dados_usa_o_invólucro_padrao(self):
        for arquivo in _templates():
            texto = arquivo.read_text()
            for tabela in re.finditer(r"<table\b[^>]*>", texto):
                if "fechamento-tabela" in tabela.group(0):
                    continue  # resumo compacto, continua tabela no celular
                antes = texto[: tabela.start()].rstrip()
                with self.subTest(arquivo=str(arquivo.relative_to(TEMPLATES))):
                    self.assertTrue(antes.endswith('<div class="ds-table-wrap">'))

    def test_toda_tabela_tem_coluna_principal_para_o_cartao(self):
        for arquivo in _templates():
            texto = arquivo.read_text()
            if '<div class="ds-table-wrap">' not in texto:
                continue
            with self.subTest(arquivo=str(arquivo.relative_to(TEMPLATES))):
                self.assertIn("col-principal", texto)

    def test_sem_alternador_tabela_cards(self):
        base = (TEMPLATES / "base.html").read_text()
        self.assertNotIn("orca-list-view", base)
        self.assertNotIn("cards-mode", base)


class FormulariosTests(SimpleTestCase):
    def test_formulario_nao_fica_dentro_de_caixa(self):
        caixa_em_volta = re.compile(r'<div class="(?:ds-card|form-panel)[^"]*">\s*<form\b')
        for arquivo in _templates():
            with self.subTest(arquivo=str(arquivo.relative_to(TEMPLATES))):
                self.assertIsNone(caixa_em_volta.search(arquivo.read_text()))

    def test_sem_subtitulo_antigo_de_barra(self):
        for arquivo in _templates():
            with self.subTest(arquivo=str(arquivo.relative_to(TEMPLATES))):
                self.assertNotIn("form-subhead", arquivo.read_text())

    def test_acoes_de_formulario_usam_o_rodape_padrao(self):
        for nome in (
            "catalogo/item_form.html",
            "catalogo/categoria_form.html",
            "clientes/form.html",
            "relatorios/configuracao_form.html",
            "catalogo/importar_excel.html",
            "orcamentos/item_inline_form.html",
        ):
            with self.subTest(arquivo=nome):
                self.assertIn('class="form-acoes"', (TEMPLATES / nome).read_text())
