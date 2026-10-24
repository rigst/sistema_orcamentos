"""Pontos de entrada dos relatórios (usados pelas views).

O conteúdo de cada documento sai de `conteudo.py`; o desenho, de `pdf.py`,
`planilha.py` e `word.py`.
"""

from .conteudo import (
    StatusRelatorio,
    formatar_data,
    formatar_data_extenso,
    formatar_moeda,
    formatar_unidade_relatorio,
    obter_alerta_status,
    texto_ou_linha,
)
from .pdf import gerar_pdf_memorial_descritivo, gerar_pdf_orcamento
from .planilha import gerar_excel_orcamento
from .word import gerar_docx_memorial_descritivo

__all__ = [
    "StatusRelatorio",
    "formatar_data",
    "formatar_data_extenso",
    "formatar_moeda",
    "formatar_unidade_relatorio",
    "gerar_docx_memorial_descritivo",
    "gerar_excel_orcamento",
    "gerar_pdf_memorial_descritivo",
    "gerar_pdf_orcamento",
    "obter_alerta_status",
    "texto_ou_linha",
]
