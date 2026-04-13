from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from PIL import Image as PILImage

from core.formatting import formatar_decimal_br, formatar_moeda_br


FONT_ROOT = Path("/usr/share/fonts/truetype/dejavu")
FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"


@dataclass
class StatusRelatorio:
    titulo: str
    detalhe: str
    nivel: str


def obter_alerta_status(orcamento) -> StatusRelatorio:
    status = orcamento.status
    if status == "aprovado":
        return StatusRelatorio(
            titulo="Orçamento aprovado",
            detalhe="Documento apto para envio formal ao cliente e registro comercial.",
            nivel="success",
        )
    if status == "enviado":
        return StatusRelatorio(
            titulo="Orçamento enviado",
            detalhe="Documento já foi encaminhado ao cliente. Revise apenas se houver nova versão.",
            nivel="info",
        )
    if status == "rascunho":
        return StatusRelatorio(
            titulo="Orçamento em rascunho",
            detalhe="Este documento ainda pode conter valores e itens provisórios. Use com cautela.",
            nivel="warning",
        )
    if status == "em_elaboracao":
        return StatusRelatorio(
            titulo="Orçamento em elaboração",
            detalhe="O conteúdo ainda está em montagem. Confirme itens e totais antes de compartilhar.",
            nivel="warning",
        )
    if status == "rejeitado":
        return StatusRelatorio(
            titulo="Orçamento rejeitado",
            detalhe="O cliente ou processo interno marcou este orçamento como rejeitado.",
            nivel="danger",
        )
    return StatusRelatorio(
        titulo="Orçamento cancelado",
        detalhe="Documento cancelado. A exportação deve ser usada apenas para histórico ou conferência interna.",
        nivel="danger",
    )


def formatar_moeda(valor: Decimal) -> str:
    return formatar_moeda_br(valor)


def formatar_data(valor: date | None) -> str:
    if not valor:
        return "-"
    return valor.strftime("%d/%m/%Y")


def formatar_unidade_relatorio(item) -> str:
    unidade = (item.unidade_medida or "").strip()
    quantidade = item.quantidade
    singular = quantidade == 1

    if unidade == "un":
        return "Unidade" if singular else "Unidades"
    if unidade == "hr":
        return "Hora" if singular else "Horas"
    if unidade == "dia":
        return "Dia" if singular else "Dias"
    if unidade == "m":
        return "Metro" if singular else "Metros"
    if unidade == "m2":
        return "Metro quadrado" if singular else "Metros quadrados"
    if unidade == "m3":
        return "Metro cúbico" if singular else "Metros cúbicos"
    if unidade == "kg":
        return "Quilo" if singular else "Quilos"
    if unidade == "cx":
        return "Caixa" if singular else "Caixas"
    if unidade == "pct":
        return "Pacote" if singular else "Pacotes"
    if unidade == "sv":
        return "Serviço" if singular else "Serviços"
    if unidade == "-":
        return "-"
    return item.get_unidade_medida_display()


def registrar_fontes_pdf():
    try:
        pdfmetrics.getFont(FONT_REGULAR)
    except KeyError:
        pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(FONT_ROOT / "DejaVuSans.ttf")))
    try:
        pdfmetrics.getFont(FONT_BOLD)
    except KeyError:
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_ROOT / "DejaVuSans-Bold.ttf")))


def gerar_excel_orcamento(orcamento, configuracao, alerta_status: StatusRelatorio) -> bytes:
    def texto_planilha(valor) -> str:
        return escape(str(valor or "")).replace("\n", "&#10;")

    empresa = configuracao.nome_empresa if configuracao else "Sua empresa"
    cliente = str(orcamento.cliente)
    linhas_itens = []
    for item in orcamento.itens.select_related("item_catalogo__categoria").all().order_by("ordem", "id"):
        categoria_nome = (
            item.item_catalogo.categoria.nome
            if item.item_catalogo_id and item.item_catalogo and item.item_catalogo.categoria_id
            else "Sem categoria"
        )
        linhas_itens.append(
            f"""
            <Row>
                <Cell><Data ss:Type="Number">{item.ordem}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(item.codigo_item or "")}</Data></Cell>
                <Cell><Data ss:Type="String">{texto_planilha(categoria_nome)}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(item.nome)}</Data></Cell>
                <Cell><Data ss:Type="String">{texto_planilha(item.descricao or "")}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.quantidade}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(formatar_unidade_relatorio(item))}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.valor_unitario}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.desconto_valor}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.desconto_percentual}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.acrescimo_valor}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.acrescimo_percentual}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.subtotal}</Data></Cell>
            </Row>
            """
        )

    linhas_subtotais_categoria = []
    for grupo in orcamento.subtotais_por_categoria():
        linhas_subtotais_categoria.append(
            f"""
            <Row>
                <Cell><Data ss:Type="String">{texto_planilha(grupo["categoria_nome"])}</Data></Cell>
                <Cell ss:StyleID="Currency"><Data ss:Type="Number">{grupo["subtotal"]}</Data></Cell>
            </Row>
            """
        )

    linhas_contexto = []
    if orcamento.mostrar_descricao_inicial_no_relatorio and orcamento.descricao_inicial:
        linhas_contexto.append(
            f'<Row><Cell><Data ss:Type="String">Descrição inicial: {texto_planilha(orcamento.descricao_inicial)}</Data></Cell></Row>'
        )
    if orcamento.mostrar_observacoes_gerais_no_relatorio and orcamento.observacoes_gerais:
        linhas_contexto.append(
            f'<Row><Cell><Data ss:Type="String">Observações gerais: {texto_planilha(orcamento.observacoes_gerais)}</Data></Cell></Row>'
        )
    if (
        orcamento.mostrar_rodape_institucional_no_relatorio
        and configuracao
        and configuracao.rodape_relatorio
    ):
        linhas_contexto.append(
            f'<Row><Cell><Data ss:Type="String">Rodapé institucional: {texto_planilha(configuracao.rodape_relatorio)}</Data></Cell></Row>'
        )

    xml = f"""<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Styles>
  <Style ss:ID="Title">
   <Font ss:Bold="1" ss:Size="14"/>
  </Style>
  <Style ss:ID="Header">
   <Font ss:Bold="1"/>
   <Interior ss:Color="#DCE9FF" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="Currency">
   <NumberFormat ss:Format="&quot;R$&quot; #,##0.00"/>
  </Style>
 </Styles>
 <Worksheet ss:Name="Orçamento">
  <Table>
   <Row><Cell ss:StyleID="Title"><Data ss:Type="String">{escape(empresa)}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">Orçamento {escape(orcamento.numero)} - {escape(orcamento.titulo)}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">{escape(alerta_status.titulo + ": " + alerta_status.detalhe)}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">Cliente: {escape(cliente)}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">Status: {escape(orcamento.get_status_display())}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">Emissão: {formatar_data(orcamento.data_emissao)}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">Validade: {formatar_data(orcamento.validade_em)}</Data></Cell></Row>
   {''.join(linhas_contexto)}
   <Row />
   <Row ss:StyleID="Header">
    <Cell><Data ss:Type="String">Ordem</Data></Cell>
    <Cell><Data ss:Type="String">Código</Data></Cell>
    <Cell><Data ss:Type="String">Categoria</Data></Cell>
    <Cell><Data ss:Type="String">Item</Data></Cell>
    <Cell><Data ss:Type="String">Descrição</Data></Cell>
    <Cell><Data ss:Type="String">Qtd</Data></Cell>
    <Cell><Data ss:Type="String">Unidade</Data></Cell>
    <Cell><Data ss:Type="String">Valor unitário</Data></Cell>
    <Cell><Data ss:Type="String">Desc. valor</Data></Cell>
    <Cell><Data ss:Type="String">Desc. %</Data></Cell>
    <Cell><Data ss:Type="String">Acrésc. valor</Data></Cell>
    <Cell><Data ss:Type="String">Acrésc. %</Data></Cell>
    <Cell><Data ss:Type="String">Subtotal</Data></Cell>
   </Row>
   {''.join(linhas_itens)}
   <Row />
   <Row ss:StyleID="Header"><Cell><Data ss:Type="String">Subtotais por categoria</Data></Cell></Row>
   {''.join(linhas_subtotais_categoria)}
   <Row />
   <Row><Cell><Data ss:Type="String">Subtotal dos itens</Data></Cell><Cell ss:StyleID="Currency"><Data ss:Type="Number">{orcamento.subtotal_itens}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">Desconto global em valor</Data></Cell><Cell ss:StyleID="Currency"><Data ss:Type="Number">{orcamento.desconto_global_valor}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">Desconto global em %</Data></Cell><Cell><Data ss:Type="Number">{orcamento.desconto_global_percentual}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">Acréscimo global em valor</Data></Cell><Cell ss:StyleID="Currency"><Data ss:Type="Number">{orcamento.acrescimo_global_valor}</Data></Cell></Row>
   <Row><Cell><Data ss:Type="String">Acréscimo global em %</Data></Cell><Cell><Data ss:Type="Number">{orcamento.acrescimo_global_percentual}</Data></Cell></Row>
   <Row><Cell ss:StyleID="Header"><Data ss:Type="String">Total final</Data></Cell><Cell ss:StyleID="Currency"><Data ss:Type="Number">{orcamento.total_final}</Data></Cell></Row>
  </Table>
 </Worksheet>
</Workbook>
"""
    return xml.encode("utf-8")


def carregar_logo_pdf(configuracao, largura_maxima=140, altura_maxima=48):
    if not configuracao or not configuracao.logo:
        return None
    try:
        with PILImage.open(configuracao.logo.path) as image:
            convertido = image.convert("RGB")
            convertido.thumbnail((largura_maxima * 4, altura_maxima * 4))
            buffer = BytesIO()
            convertido.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer, min(largura_maxima, convertido.width / 4), min(altura_maxima, convertido.height / 4)
    except Exception:
        return None


def obter_estilos_pdf():
    base = getSampleStyleSheet()
    return {
        "hero": ParagraphStyle(
            "Hero",
            parent=base["Heading1"],
            fontName=FONT_BOLD,
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#17304A"),
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "Title",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#17304A"),
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#48627E"),
        ),
        "body_strong": ParagraphStyle(
            "BodyStrong",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#17304A"),
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#617A95"),
        ),
        "memorial_section": ParagraphStyle(
            "MemorialSection",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#17304A"),
            spaceBefore=4,
            spaceAfter=6,
        ),
        "memorial_bullet": ParagraphStyle(
            "MemorialBullet",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=12,
            leading=15,
            leftIndent=12,
            bulletIndent=0,
            textColor=colors.HexColor("#48627E"),
            spaceAfter=4,
        ),
        "label": ParagraphStyle(
            "Label",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#617A95"),
        ),
    }


def cor_status(nivel: str):
    if nivel == "success":
        return colors.HexColor("#E6F6EB"), colors.HexColor("#3D8F56")
    if nivel == "warning":
        return colors.HexColor("#FBF1E4"), colors.HexColor("#A16B18")
    if nivel == "danger":
        return colors.HexColor("#FBEAEA"), colors.HexColor("#BE4444")
    return colors.HexColor("#EAF3FF"), colors.HexColor("#2F78DB")


def desenhar_fundo(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(colors.HexColor("#F6FAFE"))
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setStrokeColor(colors.HexColor("#DCE7F3"))
    canvas.line(doc.leftMargin, 15 * mm, width - doc.rightMargin, 15 * mm)
    canvas.setFont(FONT_REGULAR, 12)
    canvas.setFillColor(colors.HexColor("#617A95"))
    canvas.drawRightString(width - doc.rightMargin, 10.5 * mm, f"Página {doc.page}")
    canvas.restoreState()


def bloco_info(styles, label: str, valor: str):
    return Paragraph(f"<font name='{FONT_BOLD}' color='#617A95'>{label}</font><br/>{valor}", styles["body"])


def quebrar_linhas_texto(valor: str | None) -> str:
    return escape((valor or "").strip()).replace("\n", "<br/>")


def adicionar_secao_texto(story, styles, titulo: str, conteudo: str | None):
    texto = (conteudo or "").strip()
    if not texto:
        return
    story.append(Spacer(1, 8))
    story.append(Paragraph(titulo, styles["memorial_section"]))
    story.append(Paragraph(quebrar_linhas_texto(texto), styles["body"]))


def montar_topo_pdf(orcamento, configuracao, styles, titulo_documento: str, subtitulo: str | None = None):
    empresa = configuracao.nome_empresa if configuracao else "Sua empresa"
    nome_fantasia = configuracao.nome_fantasia if configuracao and configuracao.nome_fantasia else "Proposta comercial"
    logo = carregar_logo_pdf(configuracao)

    header_text = [
        Paragraph(empresa, styles["hero"]),
        Paragraph(nome_fantasia, styles["body"]),
        Spacer(1, 4),
        Paragraph(
            f"<font name='{FONT_BOLD}'>{titulo_documento}</font><br/>{subtitulo or orcamento.titulo}",
            styles["body"],
        ),
    ]
    if logo:
        image_buffer, width, height = logo
        logo_flow = Image(image_buffer, width=width * mm, height=height * mm)
        topo = Table([[logo_flow, header_text]], colWidths=[44 * mm, 122 * mm])
    else:
        topo = Table([[header_text]], colWidths=[166 * mm])
    topo.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FBFE")),
                ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#DCE7F3")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return topo


def gerar_pdf_orcamento(orcamento, configuracao, alerta_status: StatusRelatorio) -> bytes:
    registrar_fontes_pdf()
    styles = obter_estilos_pdf()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=f"Orçamento {orcamento.numero}",
        author=configuracao.nome_empresa if configuracao and configuracao.nome_empresa else "",
        pageCompression=0,
    )

    status_bg, status_fg = cor_status(alerta_status.nivel)

    topo = montar_topo_pdf(orcamento, configuracao, styles, f"Orçamento {orcamento.numero}")

    status_card = Table(
        [[Paragraph(f"<font name='{FONT_BOLD}' color='#{status_fg.hexval()[2:]}'> {alerta_status.titulo}</font><br/>{alerta_status.detalhe}", styles["body"])]],
        colWidths=[166 * mm],
    )
    status_card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), status_bg),
                ("LINEBEFORE", (0, 0), (0, -1), 3, status_fg),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    resumo = Table(
        [
            [
                bloco_info(styles, "CLIENTE", str(orcamento.cliente)),
                bloco_info(styles, "STATUS", orcamento.get_status_display()),
                bloco_info(styles, "EMISSÃO", formatar_data(orcamento.data_emissao)),
            ],
            [
                bloco_info(styles, "VALIDADE", formatar_data(orcamento.validade_em)),
                bloco_info(styles, "SUBTOTAL", formatar_moeda(orcamento.subtotal_itens)),
                bloco_info(styles, "TOTAL FINAL", formatar_moeda(orcamento.total_final)),
            ],
        ],
        colWidths=[55 * mm, 55 * mm, 56 * mm],
    )
    resumo.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCFDFF")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#DCE7F3")),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#E7EFF8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ]
        )
    )

    story = [topo, Spacer(1, 10), status_card, Spacer(1, 10), resumo, Spacer(1, 12)]

    if orcamento.mostrar_descricao_inicial_no_relatorio and orcamento.descricao_inicial:
        story.extend(
            [
                Paragraph("Descrição inicial", styles["title"]),
                Table(
                    [[Paragraph(orcamento.descricao_inicial.replace("\n", "<br/>"), styles["body"])]],
                    colWidths=[166 * mm],
                    style=TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCFDFF")),
                            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#DCE7F3")),
                            ("LEFTPADDING", (0, 0), (-1, -1), 14),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                            ("TOPPADDING", (0, 0), (-1, -1), 12),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                        ]
                    ),
                ),
                Spacer(1, 12),
            ]
        )

    story.append(Paragraph("Itens do orçamento", styles["title"]))
    mostrar_ajustes = orcamento.mostrar_ajustes_no_relatorio
    linhas_itens = [
        [
            Paragraph("<b>Ordem</b>", styles["small"]),
            Paragraph("<b>Item</b>", styles["small"]),
            Paragraph("<b>Qtd.</b>", styles["small"]),
            Paragraph("<b>Valor unitário</b>", styles["small"]),
            Paragraph("<b>Subtotal</b>", styles["small"]),
        ]
    ]
    for item in orcamento.itens.all().order_by("ordem", "id"):
        detalhes = [f"<b>{item.nome}</b>", item.codigo_item or "Sem código"]
        if item.descricao:
            detalhes.append(item.descricao)
        if mostrar_ajustes:
            if item.desconto_valor or item.desconto_percentual:
                detalhes.append(
                    f"Desconto: {formatar_moeda(item.desconto_valor)} + {formatar_decimal_br(item.desconto_percentual)}%"
                )
            if item.acrescimo_valor or item.acrescimo_percentual:
                detalhes.append(
                    f"Acréscimo: {formatar_moeda(item.acrescimo_valor)} + {formatar_decimal_br(item.acrescimo_percentual)}%"
                )

        linhas_itens.append(
            [
                Paragraph(str(item.ordem), styles["body"]),
                Paragraph("<br/>".join(detalhes), styles["body"]),
                Paragraph(f"{formatar_decimal_br(item.quantidade)}<br/>{formatar_unidade_relatorio(item)}", styles["body"]),
                Paragraph(formatar_moeda(item.valor_unitario), styles["body"]),
                Paragraph(f"<b>{formatar_moeda(item.subtotal)}</b>", styles["body"]),
            ]
        )

    tabela_itens = Table(linhas_itens, colWidths=[16 * mm, 78 * mm, 22 * mm, 25 * mm, 25 * mm], repeatRows=1)
    tabela_itens.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17304A")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FCFDFF")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FCFDFF"), colors.white]),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#DCE7F3")),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#E7EFF8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([tabela_itens, Spacer(1, 12), Paragraph("Resumo financeiro", styles["title"])])

    linhas_totais = [["Campo", "Valor"]]
    linhas_totais.append(["Subtotal dos itens", formatar_moeda(orcamento.subtotal_itens)])
    if mostrar_ajustes:
        linhas_totais.append(
            [
                "Desconto global",
                f"{formatar_moeda(orcamento.desconto_global_valor)} | {formatar_decimal_br(orcamento.desconto_global_percentual)}%",
            ]
        )
        linhas_totais.append(
            [
                "Acréscimo global",
                f"{formatar_moeda(orcamento.acrescimo_global_valor)} | {formatar_decimal_br(orcamento.acrescimo_global_percentual)}%",
            ]
        )
    linhas_totais.append(["Total final", formatar_moeda(orcamento.total_final)])
    tabela_totais = Table(linhas_totais, colWidths=[90 * mm, 76 * mm])
    tabela_totais.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3FF")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F0F7FF")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#DCE7F3")),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#E7EFF8")),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, -1), (-1, -1), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -2), FONT_REGULAR),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#17304A")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(tabela_totais)

    if orcamento.mostrar_observacoes_gerais_no_relatorio and orcamento.observacoes_gerais:
        story.extend([Spacer(1, 12), Paragraph("Observações gerais", styles["title"])])
        story.append(
            Table(
                [[Paragraph(orcamento.observacoes_gerais.replace("\n", "<br/>"), styles["body"])]],
                colWidths=[166 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCFDFF")),
                        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#DCE7F3")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 14),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                        ("TOPPADDING", (0, 0), (-1, -1), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ]
                ),
            )
        )

    if (
        orcamento.mostrar_rodape_institucional_no_relatorio
        and configuracao
        and configuracao.rodape_relatorio
    ):
        story.extend([Spacer(1, 12), Paragraph("Rodapé institucional", styles["title"])])
        story.append(
            Table(
                [[Paragraph(configuracao.rodape_relatorio.replace("\n", "<br/>"), styles["body"])]],
                colWidths=[166 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCFDFF")),
                        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#DCE7F3")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 14),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                        ("TOPPADDING", (0, 0), (-1, -1), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ]
                ),
            )
        )

    doc.build(story, onFirstPage=desenhar_fundo, onLaterPages=desenhar_fundo)
    return buffer.getvalue()


def gerar_pdf_memorial_descritivo(orcamento, configuracao) -> bytes:
    registrar_fontes_pdf()
    styles = obter_estilos_pdf()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=f"Memorial Descritivo {orcamento.numero}",
        author=configuracao.nome_empresa if configuracao and configuracao.nome_empresa else "",
        pageCompression=0,
    )

    topo = montar_topo_pdf(
        orcamento,
        configuracao,
        styles,
        f"Memorial Descritivo {orcamento.numero}",
        orcamento.titulo,
    )

    bloco_cliente = str(orcamento.cliente)
    bloco_evento = orcamento.evento_nome or orcamento.titulo
    bloco_local = orcamento.evento_local or formatar_data(orcamento.data_emissao)
    resumo = Table(
        [
            [
                bloco_info(styles, "CLIENTE", escape(bloco_cliente)),
                bloco_info(styles, "EVENTO/PROJETO", escape(bloco_evento)),
                bloco_info(styles, "TOTAL FINAL", formatar_moeda(orcamento.total_final)),
            ],
            [
                bloco_info(styles, "EMISSÃO", formatar_data(orcamento.data_emissao)),
                bloco_info(styles, "LOCAL", escape(bloco_local)),
                bloco_info(styles, "VALIDADE", formatar_data(orcamento.validade_em)),
            ],
        ],
        colWidths=[55 * mm, 55 * mm, 56 * mm],
    )
    resumo.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCFDFF")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#DCE7F3")),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#E7EFF8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ]
        )
    )

    story = [topo, Spacer(1, 10), resumo, Spacer(1, 12), Paragraph("Memorial Descritivo", styles["title"])]

    if configuracao and any([configuracao.cidade, configuracao.estado]):
        local_empresa = configuracao.cidade or ""
        if configuracao.estado:
            local_empresa = f"{local_empresa}/{configuracao.estado}" if local_empresa else configuracao.estado
        story.append(Paragraph(f"{local_empresa}, {formatar_data(orcamento.data_emissao)}.", styles["body"]))
        story.append(Spacer(1, 8))

    referencia_evento = escape(orcamento.evento_nome or orcamento.titulo)
    detalhe_evento = []
    if orcamento.evento_local:
        detalhe_evento.append(f"no local <b>{escape(orcamento.evento_local)}</b>")
    if orcamento.evento_periodo:
        detalhe_evento.append(f"no período <b>{escape(orcamento.evento_periodo)}</b>")
    if orcamento.evento_estande:
        detalhe_evento.append(f"estande <b>{escape(orcamento.evento_estande)}</b>")
    if orcamento.evento_area:
        detalhe_evento.append(f"área de <b>{escape(orcamento.evento_area)}</b>")

    introducao = (
        f"Conforme solicitado, apresento o memorial descritivo referente ao orçamento "
        f"<b>{orcamento.numero}</b>, para <b>{referencia_evento}</b>, "
        f"destinado ao cliente <b>{escape(str(orcamento.cliente))}</b>"
    )
    if detalhe_evento:
        introducao = f"{introducao}, {'; '.join(detalhe_evento)}"
    introducao = f"{introducao}, conforme especificações abaixo."
    story.append(Paragraph(introducao, styles["body"]))
    story.append(Spacer(1, 10))

    contatos_evento = []
    if orcamento.evento_contato:
        contatos_evento.append(f"<b>A/C:</b> {escape(orcamento.evento_contato)}")
    if orcamento.evento_telefone:
        contatos_evento.append(f"<b>Telefone:</b> {escape(orcamento.evento_telefone)}")
    if orcamento.evento_email:
        contatos_evento.append(f"<b>E-mail:</b> {escape(orcamento.evento_email)}")
    if orcamento.mostrar_contatos_evento_no_memorial and contatos_evento:
        story.append(Paragraph("<br/>".join(contatos_evento), styles["body"]))
        story.append(Spacer(1, 10))

    for grupo in orcamento.subtotais_por_categoria():
        story.append(Paragraph(grupo["categoria_nome"].upper(), styles["memorial_section"]))
        story.append(Paragraph("ESPECIFICAÇÕES:", styles["label"]))
        story.append(Spacer(1, 4))

        for item in grupo["itens"]:
            descricao = (item.descricao or "").strip() or item.nome
            quantidade = formatar_decimal_br(item.quantidade)
            story.append(
                Paragraph(
                    f"{quantidade} {escape(formatar_unidade_relatorio(item))} de {descricao.replace(chr(10), '<br/>')}",
                    styles["memorial_bullet"],
                    bulletText="▪",
                )
            )
        story.append(
            Paragraph(
                f"<b>Subtotal da categoria:</b> {formatar_moeda(grupo['subtotal'])}",
                styles["body"],
            )
        )
        story.append(Spacer(1, 10))

    if orcamento.mostrar_financeiro_no_memorial:
        story.append(Paragraph("ESPECIFICAÇÕES FINANCEIRAS", styles["memorial_section"]))
        story.append(Paragraph(f"Valor total final: <b>{formatar_moeda(orcamento.total_final)}</b>.", styles["body"]))
        if orcamento.valor_locacao is not None:
            story.append(Paragraph(f"Valor de locação: <b>{formatar_moeda(orcamento.valor_locacao)}</b>.", styles["body"]))
        if orcamento.valor_servico is not None:
            story.append(Paragraph(f"Valor de serviço: <b>{formatar_moeda(orcamento.valor_servico)}</b>.", styles["body"]))

        validade_texto = formatar_data(orcamento.validade_em)
        if configuracao and configuracao.validade_padrao_proposta and not orcamento.validade_em:
            validade_texto = f"{configuracao.validade_padrao_proposta} dias"
        if validade_texto and validade_texto != "-":
            story.append(Paragraph(f"Validade da proposta: {escape(validade_texto)}.", styles["body"]))
        if orcamento.condicoes_pagamento:
            story.append(Paragraph(f"Condições de pagamento: {quebrar_linhas_texto(orcamento.condicoes_pagamento)}.", styles["body"]))
        if configuracao and configuracao.dados_bancarios:
            story.append(Paragraph(f"Dados bancários: {quebrar_linhas_texto(configuracao.dados_bancarios)}.", styles["body"]))
        if configuracao and configuracao.chave_pix:
            story.append(Paragraph(f"Chave PIX: {escape(configuracao.chave_pix)}.", styles["body"]))

    adicionar_secao_texto(story, styles, "SERVIÇOS E TAXAS INCLUSOS", orcamento.servicos_taxas_inclusos)
    if orcamento.mostrar_observacoes_gerais_no_relatorio:
        adicionar_secao_texto(story, styles, "OBSERVAÇÕES", orcamento.observacoes_gerais)

    dados_contratuais = []
    if orcamento.contrato_razao_social:
        dados_contratuais.append(f"<b>Razão social:</b> {escape(orcamento.contrato_razao_social)}")
    if orcamento.contrato_cnpj:
        dados_contratuais.append(f"<b>CNPJ:</b> {escape(orcamento.contrato_cnpj)}")
    if orcamento.contrato_inscricao_estadual:
        dados_contratuais.append(f"<b>Inscrição estadual:</b> {escape(orcamento.contrato_inscricao_estadual)}")
    if orcamento.contrato_endereco:
        dados_contratuais.append(f"<b>Endereço:</b> {escape(orcamento.contrato_endereco)}")
    if orcamento.contrato_cidade:
        cidade_contrato = escape(orcamento.contrato_cidade)
        if orcamento.contrato_cep:
            cidade_contrato = f"{cidade_contrato} | CEP {escape(orcamento.contrato_cep)}"
        dados_contratuais.append(f"<b>Cidade:</b> {cidade_contrato}")
    elif orcamento.contrato_cep:
        dados_contratuais.append(f"<b>CEP:</b> {escape(orcamento.contrato_cep)}")
    if orcamento.contrato_responsavel_nome:
        responsavel = escape(orcamento.contrato_responsavel_nome)
        if orcamento.contrato_cargo_funcao:
            responsavel = f"{responsavel} ({escape(orcamento.contrato_cargo_funcao)})"
        dados_contratuais.append(f"<b>Responsável:</b> {responsavel}")
    if orcamento.contrato_responsavel_documento:
        dados_contratuais.append(f"<b>Documento:</b> {escape(orcamento.contrato_responsavel_documento)}")
    if orcamento.contrato_telefone:
        dados_contratuais.append(f"<b>Telefone:</b> {escape(orcamento.contrato_telefone)}")
    if orcamento.contrato_email:
        dados_contratuais.append(f"<b>E-mail:</b> {escape(orcamento.contrato_email)}")
    if orcamento.mostrar_dados_contratuais_no_memorial and dados_contratuais:
        story.append(Spacer(1, 8))
        story.append(Paragraph("DADOS CONTRATUAIS", styles["memorial_section"]))
        story.append(Paragraph("<br/>".join(dados_contratuais), styles["body"]))

    if orcamento.mostrar_informacoes_complementares_no_memorial:
        adicionar_secao_texto(
            story,
            styles,
            "INFORMAÇÕES COMPLEMENTARES",
            (
                "\n\n".join(
                    parte
                    for parte in [
                        getattr(configuracao, "texto_institucional_memorial", "") if configuracao else "",
                        getattr(configuracao, "rodape_relatorio", "") if configuracao else "",
                    ]
                    if parte
                )
            ),
        )

    assinatura_linhas = []
    if configuracao and configuracao.assinatura_nome:
        assinatura_linhas.append(f"<b>{escape(configuracao.assinatura_nome)}</b>")
    if configuracao and configuracao.assinatura_cargo:
        assinatura_linhas.append(escape(configuracao.assinatura_cargo))
    if configuracao and configuracao.assinatura_contato:
        assinatura_linhas.append(escape(configuracao.assinatura_contato))
    if assinatura_linhas:
        story.append(Spacer(1, 16))
        story.append(Paragraph("<br/>".join(assinatura_linhas), styles["body"]))

    doc.build(story, onFirstPage=desenhar_fundo, onLaterPages=desenhar_fundo)
    return buffer.getvalue()


def _rtf_escape(texto: str | None) -> str:
    texto = str(texto or "")
    convertido = []
    for caractere in texto:
        if caractere == "\\":
            convertido.append(r"\\")
        elif caractere == "{":
            convertido.append(r"\{")
        elif caractere == "}":
            convertido.append(r"\}")
        elif caractere == "\n":
            convertido.append(r"\line ")
        elif ord(caractere) > 127:
            codigo = ord(caractere)
            if codigo > 32767:
                codigo -= 65536
            convertido.append(fr"\u{codigo}?")
        else:
            convertido.append(caractere)
    return "".join(convertido)


def _rtf_paragrafo(texto: str | None, *, negrito: bool = False, espacamento: int = 180) -> str:
    conteudo = _rtf_escape(texto)
    if negrito:
        conteudo = rf"\b {conteudo}\b0"
    return rf"\pard\sa{espacamento}\sl276\slmult1\f0\fs24 {conteudo}\par"


def gerar_word_memorial_descritivo(orcamento, configuracao) -> bytes:
    partes = [
        r"{\rtf1\ansi\deff0",
        r"{\fonttbl{\f0 Arial;}}",
        r"\viewkind4\uc1",
        _rtf_paragrafo(f"Memorial Descritivo {orcamento.numero}", negrito=True, espacamento=220),
        _rtf_paragrafo(f"Título: {orcamento.titulo}"),
        _rtf_paragrafo(f"Cliente: {orcamento.cliente}"),
        _rtf_paragrafo(f"Emissão: {formatar_data(orcamento.data_emissao)}"),
        _rtf_paragrafo(f"Validade: {formatar_data(orcamento.validade_em)}"),
    ]

    if orcamento.evento_nome:
        partes.append(_rtf_paragrafo(f"Evento/Projeto: {orcamento.evento_nome}"))
    if orcamento.evento_local:
        partes.append(_rtf_paragrafo(f"Local: {orcamento.evento_local}"))
    if orcamento.evento_periodo:
        partes.append(_rtf_paragrafo(f"Período: {orcamento.evento_periodo}"))
    if orcamento.evento_estande:
        partes.append(_rtf_paragrafo(f"Estande: {orcamento.evento_estande}"))
    if orcamento.evento_area:
        partes.append(_rtf_paragrafo(f"Área: {orcamento.evento_area}"))

    if orcamento.mostrar_contatos_evento_no_memorial:
        if orcamento.evento_contato:
            partes.append(_rtf_paragrafo(f"A/C: {orcamento.evento_contato}"))
        if orcamento.evento_telefone:
            partes.append(_rtf_paragrafo(f"Telefone: {orcamento.evento_telefone}"))
        if orcamento.evento_email:
            partes.append(_rtf_paragrafo(f"E-mail: {orcamento.evento_email}"))

    partes.append(_rtf_paragrafo("Itens e especificações", negrito=True, espacamento=220))
    for grupo in orcamento.subtotais_por_categoria():
        partes.append(_rtf_paragrafo(grupo["categoria_nome"].upper(), negrito=True, espacamento=200))
        for item in grupo["itens"]:
            descricao = (item.descricao or "").strip() or item.nome
            quantidade = formatar_decimal_br(item.quantidade)
            partes.append(_rtf_paragrafo(f"- {quantidade} {formatar_unidade_relatorio(item)} de {descricao}", espacamento=140))
        partes.append(_rtf_paragrafo(f"Subtotal da categoria: {formatar_moeda(grupo['subtotal'])}"))

    if orcamento.mostrar_financeiro_no_memorial:
        partes.append(_rtf_paragrafo("Especificações financeiras", negrito=True, espacamento=220))
        partes.append(_rtf_paragrafo(f"Valor total final: {formatar_moeda(orcamento.total_final)}"))
        if orcamento.valor_locacao is not None:
            partes.append(_rtf_paragrafo(f"Valor de locação: {formatar_moeda(orcamento.valor_locacao)}"))
        if orcamento.valor_servico is not None:
            partes.append(_rtf_paragrafo(f"Valor de serviço: {formatar_moeda(orcamento.valor_servico)}"))
        validade_texto = formatar_data(orcamento.validade_em)
        if configuracao and configuracao.validade_padrao_proposta and not orcamento.validade_em:
            validade_texto = f"{configuracao.validade_padrao_proposta} dias"
        if validade_texto and validade_texto != "-":
            partes.append(_rtf_paragrafo(f"Validade da proposta: {validade_texto}"))
        if orcamento.condicoes_pagamento:
            partes.append(_rtf_paragrafo(f"Condições de pagamento: {orcamento.condicoes_pagamento}"))
        if configuracao and configuracao.dados_bancarios:
            partes.append(_rtf_paragrafo(f"Dados bancários: {configuracao.dados_bancarios}"))
        if configuracao and configuracao.chave_pix:
            partes.append(_rtf_paragrafo(f"Chave PIX: {configuracao.chave_pix}"))

    if orcamento.servicos_taxas_inclusos:
        partes.append(_rtf_paragrafo("Serviços e taxas inclusos", negrito=True, espacamento=220))
        partes.append(_rtf_paragrafo(orcamento.servicos_taxas_inclusos))
    if orcamento.mostrar_observacoes_gerais_no_relatorio and orcamento.observacoes_gerais:
        partes.append(_rtf_paragrafo("Observações", negrito=True, espacamento=220))
        partes.append(_rtf_paragrafo(orcamento.observacoes_gerais))

    if orcamento.mostrar_dados_contratuais_no_memorial:
        dados_contratuais = []
        if orcamento.contrato_razao_social:
            dados_contratuais.append(f"Razão social: {orcamento.contrato_razao_social}")
        if orcamento.contrato_cnpj:
            dados_contratuais.append(f"CNPJ: {orcamento.contrato_cnpj}")
        if orcamento.contrato_inscricao_estadual:
            dados_contratuais.append(f"Inscrição estadual: {orcamento.contrato_inscricao_estadual}")
        if orcamento.contrato_endereco:
            dados_contratuais.append(f"Endereço: {orcamento.contrato_endereco}")
        if orcamento.contrato_cidade:
            cidade_contrato = orcamento.contrato_cidade
            if orcamento.contrato_cep:
                cidade_contrato = f"{cidade_contrato} | CEP {orcamento.contrato_cep}"
            dados_contratuais.append(f"Cidade: {cidade_contrato}")
        elif orcamento.contrato_cep:
            dados_contratuais.append(f"CEP: {orcamento.contrato_cep}")
        if orcamento.contrato_responsavel_nome:
            responsavel = orcamento.contrato_responsavel_nome
            if orcamento.contrato_cargo_funcao:
                responsavel = f"{responsavel} ({orcamento.contrato_cargo_funcao})"
            dados_contratuais.append(f"Responsável: {responsavel}")
        if orcamento.contrato_responsavel_documento:
            dados_contratuais.append(f"Documento: {orcamento.contrato_responsavel_documento}")
        if orcamento.contrato_telefone:
            dados_contratuais.append(f"Telefone: {orcamento.contrato_telefone}")
        if orcamento.contrato_email:
            dados_contratuais.append(f"E-mail: {orcamento.contrato_email}")
        if dados_contratuais:
            partes.append(_rtf_paragrafo("Dados contratuais", negrito=True, espacamento=220))
            for linha in dados_contratuais:
                partes.append(_rtf_paragrafo(linha, espacamento=140))

    if orcamento.mostrar_informacoes_complementares_no_memorial:
        informacoes_complementares = "\n\n".join(
            parte
            for parte in [
                getattr(configuracao, "texto_institucional_memorial", "") if configuracao else "",
                getattr(configuracao, "rodape_relatorio", "") if configuracao else "",
            ]
            if parte
        )
        if informacoes_complementares:
            partes.append(_rtf_paragrafo("Informações complementares", negrito=True, espacamento=220))
            partes.append(_rtf_paragrafo(informacoes_complementares))

    assinatura_linhas = []
    if configuracao and configuracao.assinatura_nome:
        assinatura_linhas.append(configuracao.assinatura_nome)
    if configuracao and configuracao.assinatura_cargo:
        assinatura_linhas.append(configuracao.assinatura_cargo)
    if configuracao and configuracao.assinatura_contato:
        assinatura_linhas.append(configuracao.assinatura_contato)
    if assinatura_linhas:
        partes.append(_rtf_paragrafo("Assinatura", negrito=True, espacamento=220))
        for linha in assinatura_linhas:
            partes.append(_rtf_paragrafo(linha, espacamento=140))

    partes.append("}")
    return "".join(partes).encode("utf-8")
