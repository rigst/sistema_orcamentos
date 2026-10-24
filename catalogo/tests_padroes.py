"""Padrões visuais que dependem de dados do modelo."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from catalogo.models import CategoriaItem


class PreviaDoIconeTests(SimpleTestCase):
    def test_toda_cor_de_categoria_pinta_a_previa_do_icone(self):
        css = (Path(settings.BASE_DIR) / "static/css/padroes.css").read_text()
        for valor, _ in CategoriaItem.COLOR_CHOICES:
            with self.subTest(cor=valor):
                self.assertIn(f'input[name="cor"][value="{valor}"]:checked', css)
