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
    empresa = configuracao.nome_empresa if configuracao else "Sua empresa"
    cliente = str(orcamento.cliente)
    linhas_itens = []
    for item in orcamento.itens.all().order_by("ordem", "id"):
        linhas_itens.append(
            f"""
            <Row>
                <Cell><Data ss:Type="Number">{item.ordem}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(item.codigo_item or "")}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(item.nome)}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.quantidade}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(item.get_unidade_medida_display())}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.valor_unitario}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.desconto_valor}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.desconto_percentual}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.acrescimo_valor}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.acrescimo_percentual}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.subtotal}</Data></Cell>
            </Row>
            """
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
   <Row />
   <Row ss:StyleID="Header">
    <Cell><Data ss:Type="String">Ordem</Data></Cell>
    <Cell><Data ss:Type="String">Código</Data></Cell>
    <Cell><Data ss:Type="String">Item</Data></Cell>
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
            leading=16,
            textColor=colors.HexColor("#48627E"),
        ),
        "body_strong": ParagraphStyle(
            "BodyStrong",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#17304A"),
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#617A95"),
        ),
        "label": ParagraphStyle(
            "Label",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=11,
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
    canvas.setFont(FONT_REGULAR, 8.5)
    canvas.setFillColor(colors.HexColor("#617A95"))
    canvas.drawRightString(width - doc.rightMargin, 10.5 * mm, f"Página {doc.page}")
    canvas.restoreState()


def bloco_info(styles, label: str, valor: str):
    return Paragraph(f"<font name='{FONT_BOLD}' color='#617A95'>{label}</font><br/>{valor}", styles["body"])


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

    empresa = configuracao.nome_empresa if configuracao else "Sua empresa"
    nome_fantasia = configuracao.nome_fantasia if configuracao and configuracao.nome_fantasia else "Proposta comercial"
    logo = carregar_logo_pdf(configuracao)
    status_bg, status_fg = cor_status(alerta_status.nivel)

    header_text = [
        Paragraph(empresa, styles["hero"]),
        Paragraph(nome_fantasia, styles["body"]),
        Spacer(1, 4),
        Paragraph(f"<font name='{FONT_BOLD}'>Orçamento {orcamento.numero}</font><br/>{orcamento.titulo}", styles["body"]),
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

    if orcamento.descricao_inicial:
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
                Paragraph(f"{formatar_decimal_br(item.quantidade)}<br/>{item.get_unidade_medida_display()}", styles["body"]),
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
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#17304A")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(tabela_totais)

    if orcamento.observacoes_gerais:
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

    if configuracao and configuracao.rodape_relatorio:
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
