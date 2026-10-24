"""Planilha .xlsx do orçamento (openpyxl): números como números, moeda e
quantidade formatadas, cabeçalho congelado e mesma paleta do site."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from . import conteudo as c

FONTE = "Inter"
TINTA = "111827"
SUAVE = "586070"
LINHA = "E7E9EE"
PAINEL = "F7F8FA"
AZUL_50 = "EFF4FF"
MOEDA = '"R$" #,##0.00'
QUANTIDADE = "#,##0.00"
PERCENTUAL = '0.00"%"'

_fino = Side(style="thin", color=LINHA)
_forte = Side(style="medium", color=TINTA)


def _fonte(**kw) -> Font:
    base = {"name": FONTE, "size": 10, "color": TINTA}
    base.update(kw)
    return Font(**base)


def _rotulo(ws: Worksheet, linha: int, coluna: int, valor: str) -> None:
    cel = ws.cell(row=linha, column=coluna, value=valor.upper())
    cel.font = _fonte(size=8, bold=True, color=SUAVE)


_COLUNAS = (
    ("#", 5, None),
    ("Categoria", 20, None),
    ("Código", 24, None),
    ("Item", 38, None),
    ("Descrição", 48, None),
    ("Qtd.", 10, QUANTIDADE),
    ("Un.", 7, None),
    ("Valor unit.", 14, MOEDA),
    ("Desc. R$", 12, MOEDA),
    ("Desc. %", 9, PERCENTUAL),
    ("Acrésc. R$", 12, MOEDA),
    ("Acrésc. %", 10, PERCENTUAL),
    ("Subtotal", 15, MOEDA),
)


def _topo(ws: Worksheet, orcamento, configuracao, alerta) -> None:
    for i, (_, largura, _) in enumerate(_COLUNAS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws["A1"] = c.nome_empresa(configuracao) or "Orçamento"
    ws["A1"].font = _fonte(size=9, bold=True, color=SUAVE)
    ws["A2"] = f"{orcamento.numero} · {orcamento.titulo}"
    ws["A2"].font = _fonte(size=16, bold=True)
    ws.row_dimensions[2].height = 24
    dados = [
        ("Cliente", orcamento.cliente_exibicao),
        ("Emissão", c.formatar_data(orcamento.data_emissao)),
        ("Validade", c.validade_texto(orcamento, configuracao) or "-"),
        ("Situação", alerta.titulo),
    ]
    # Rótulos sobre colunas largas (A, D, E, H), para nada transbordar.
    for (rotulo, valor), coluna in zip(dados, (1, 4, 5, 8), strict=True):
        _rotulo(ws, 4, coluna, rotulo)
        ws.cell(row=5, column=coluna, value=valor).font = _fonte(size=10.5)


def _cabeca_tabela(ws: Worksheet, linha: int) -> None:
    for i, (titulo, _, formato) in enumerate(_COLUNAS, start=1):
        cel = ws.cell(row=linha, column=i, value=titulo.upper())
        cel.font = _fonte(size=8, bold=True, color=SUAVE)
        cel.fill = PatternFill("solid", fgColor=PAINEL)
        cel.border = Border(bottom=Side(style="thin", color="D8DBE2"))
        cel.alignment = Alignment(horizontal="right" if formato else "left", vertical="center")
    ws.row_dimensions[linha].height = 22


def _valores_item(numero: int, categoria: str, item) -> tuple:
    return (
        numero,
        categoria,
        item.codigo_item or "",
        item.nome,
        (item.descricao or "").strip(),
        float(item.quantidade),
        c.unidade_curta(item),
        float(item.valor_unitario),
        float(item.desconto_valor),
        float(item.desconto_percentual),
        float(item.acrescimo_valor),
        float(item.acrescimo_percentual),
        float(item.subtotal),
    )


def _linhas_itens(ws: Worksheet, orcamento, linha: int) -> int:
    """Escreve um item por linha a partir de `linha`; devolve a próxima livre."""
    numero = 0
    for grupo in orcamento.subtotais_por_categoria():
        for item in grupo["itens"]:
            numero += 1
            valores = _valores_item(numero, grupo["categoria_nome"], item)
            for col, valor in enumerate(valores, start=1):
                cel = ws.cell(row=linha, column=col, value=valor)
                formato = _COLUNAS[col - 1][2]
                cel.font = _fonte(bold=col in (4, 13), color=SUAVE if col in (1, 3) else TINTA)
                cel.border = Border(bottom=_fino)
                cel.alignment = Alignment(vertical="top", wrap_text=col in (4, 5))
                if formato:
                    cel.number_format = formato
            linha += 1
    return linha


def _conta(ws: Worksheet, orcamento, linha: int) -> int:
    """Conta calculada pelo sistema (a mesma da tela e do PDF)."""
    col_rot, col_val = 12, 13
    for linha_conta in c.linhas_da_conta(orcamento):
        ws.cell(row=linha, column=col_rot, value=linha_conta.rotulo).font = _fonte(color=SUAVE)
        ws.cell(row=linha, column=col_rot).alignment = Alignment(horizontal="right")
        cel = ws.cell(row=linha, column=col_val, value=linha_conta.valor_numerico)
        cel.number_format = MOEDA
        cel.font = _fonte()
        linha += 1
    ws.cell(row=linha, column=col_rot, value="TOTAL").font = _fonte(bold=True, size=11)
    ws.cell(row=linha, column=col_rot).alignment = Alignment(horizontal="right")
    total = ws.cell(row=linha, column=col_val, value=float(orcamento.total_final))
    total.number_format = MOEDA
    total.font = _fonte(bold=True, size=12)
    for col in (col_rot, col_val):
        ws.cell(row=linha, column=col).border = Border(top=_forte)
        ws.cell(row=linha, column=col).fill = PatternFill("solid", fgColor=AZUL_50)
    ws.row_dimensions[linha].height = 22
    return linha + 1


def _textos(ws: Worksheet, orcamento, configuracao, linha: int) -> None:
    textos = []
    if orcamento.mostrar_descricao_inicial_no_relatorio and orcamento.descricao_inicial:
        textos.append(c.SecaoTexto("Descrição inicial", orcamento.descricao_inicial))
    textos += c.secoes_finais_orcamento(orcamento, configuracao)
    rodape = c.rodape_institucional(orcamento, configuracao)
    if rodape:
        textos.append(c.SecaoTexto("Rodapé institucional", rodape))
    for secao in textos:
        _rotulo(ws, linha, 1, secao.titulo)
        ws.merge_cells(start_row=linha + 1, start_column=1, end_row=linha + 1, end_column=8)
        cel = ws.cell(row=linha + 1, column=1, value=secao.texto.strip())
        cel.font = _fonte()
        cel.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[linha + 1].height = max(
            18, 15 * (secao.texto.count("\n") + 1 + len(secao.texto) // 140)
        )
        linha += 3


def _impressao(ws: Worksheet, cabeca: int) -> None:
    ws.print_title_rows = f"{cabeca}:{cabeca}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    if ws.sheet_properties.pageSetUpPr is not None:
        ws.sheet_properties.pageSetUpPr.fitToPage = True


def _aba_itens(ws: Worksheet, orcamento, configuracao, alerta) -> None:
    ws.title = "Orçamento"
    ws.sheet_view.showGridLines = False
    _topo(ws, orcamento, configuracao, alerta)
    cabeca = 7
    _cabeca_tabela(ws, cabeca)
    proxima = _linhas_itens(ws, orcamento, cabeca + 1)
    ws.freeze_panes = f"A{cabeca + 1}"
    if proxima > cabeca + 1:
        ws.auto_filter.ref = f"A{cabeca}:{get_column_letter(len(_COLUNAS))}{proxima - 1}"
    depois_conta = _conta(ws, orcamento, proxima + 1)
    _textos(ws, orcamento, configuracao, depois_conta + 1)
    _impressao(ws, cabeca)


def _aba_categorias(wb: Workbook, orcamento) -> None:
    ws = wb.create_sheet("Por categoria")
    ws.sheet_view.showGridLines = False
    for letra, largura in zip("ABCD", (32, 10, 16, 10), strict=True):
        ws.column_dimensions[letra].width = largura
    for i, titulo in enumerate(("Categoria", "Itens", "Subtotal", "%"), start=1):
        cel = ws.cell(row=1, column=i, value=titulo.upper())
        cel.font = _fonte(size=8, bold=True, color=SUAVE)
        cel.fill = PatternFill("solid", fgColor=PAINEL)
        cel.alignment = Alignment(horizontal="left" if i == 1 else "right")
    linha = 2
    for grupo in orcamento.subtotais_por_categoria():
        valores: tuple[str | int | float, ...] = (
            grupo["categoria_nome"],
            grupo["quantidade_itens"],
            float(grupo["subtotal"]),
            float(grupo["percentual"]),
        )
        for col, valor_categoria in enumerate(valores, start=1):
            cel = ws.cell(row=linha, column=col, value=valor_categoria)
            cel.font = _fonte()
            cel.border = Border(bottom=_fino)
        ws.cell(row=linha, column=3).number_format = MOEDA
        ws.cell(row=linha, column=4).number_format = PERCENTUAL
        linha += 1
    ws.cell(row=linha, column=1, value="Total").font = _fonte(bold=True)
    total = ws.cell(row=linha, column=3, value=f"=SUM(C2:C{linha - 1})")
    total.number_format = MOEDA
    total.font = _fonte(bold=True)
    ws.freeze_panes = "A2"


def gerar_excel_orcamento(orcamento, configuracao, alerta_status: c.StatusRelatorio) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    _aba_itens(ws, orcamento, configuracao, alerta_status)
    _aba_categorias(wb, orcamento)
    wb.properties.title = f"Orçamento {orcamento.numero}"
    wb.properties.creator = c.nome_empresa(configuracao) or "Orçamentos"
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
