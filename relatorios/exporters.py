from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from textwrap import wrap
from xml.sax.saxutils import escape

from PIL import Image

from core.formatting import formatar_decimal_br, formatar_moeda_br


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


class SimplePDF:
    def __init__(self):
        self.pages: list[list[str]] = [[]]
        self.page_images: list[list[dict]] = [[]]
        self.page_width = 595
        self.page_height = 842
        self.margin = 48
        self.current_y = self.page_height - self.margin

    def _escape(self, text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _append(self, command: str):
        self.pages[-1].append(command)

    def new_page(self):
        self.pages.append([])
        self.page_images.append([])
        self.current_y = self.page_height - self.margin

    def rect(self, x, y, w, h, fill_rgb=None, stroke_rgb=None):
        if fill_rgb:
            self._append(f"{fill_rgb[0]} {fill_rgb[1]} {fill_rgb[2]} rg")
        if stroke_rgb:
            self._append(f"{stroke_rgb[0]} {stroke_rgb[1]} {stroke_rgb[2]} RG")
        self._append(f"{x} {y} {w} {h} re B")

    def text(self, x, y, text, size=10):
        self._append(f"BT /F1 {size} Tf 1 0 0 1 {x} {y} Tm ({self._escape(text)}) Tj ET")

    def paragraph(self, text, size=10, leading=14):
        lines = []
        for raw_line in str(text).splitlines() or [""]:
            wrapped = wrap(raw_line, width=88) or [""]
            lines.extend(wrapped)
        for line in lines:
            if self.current_y < 80:
                self.new_page()
            self.text(self.margin, self.current_y, line, size=size)
            self.current_y -= leading

    def spacer(self, height=10):
        self.current_y -= height
        if self.current_y < 80:
            self.new_page()

    def image(self, jpeg_bytes: bytes, width_px: int, height_px: int, x: int, y: int, width: int, height: int):
        image_name = f"Im{sum(len(page) for page in self.page_images) + 1}"
        self.page_images[-1].append(
            {
                "name": image_name,
                "bytes": jpeg_bytes,
                "width_px": width_px,
                "height_px": height_px,
            }
        )
        self._append(f"q {width} 0 0 {height} {x} {y} cm /{image_name} Do Q")

    def render(self) -> bytes:
        objects = []
        objects.append("<< /Type /Catalog /Pages 2 0 R >>")
        kids = " ".join(f"{index} 0 R" for index in range(3, 3 + len(self.pages) * 2, 2))
        objects.append(f"<< /Type /Pages /Count {len(self.pages)} /Kids [{kids}] >>")

        image_entries = [image for page in self.page_images for image in page]
        image_object_start = 3 + len(self.pages) * 2
        for idx, image in enumerate(image_entries):
            image["object_number"] = image_object_start + idx

        for idx, commands in enumerate(self.pages):
            stream = "q\n" + "\n".join(commands) + "\nQ"
            content_obj_num = 4 + idx * 2
            page_obj_num = 3 + idx * 2
            page_images = self.page_images[idx]
            xobject_resources = ""
            if page_images:
                entries = " ".join(f"/{image['name']} {image['object_number']} 0 R" for image in page_images)
                xobject_resources = f" /XObject << {entries} >>"
            objects.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.page_width} {self.page_height}] "
                f"/Contents {content_obj_num} 0 R /Resources << /Font << /F1 {image_object_start + len(image_entries)} 0 R >>{xobject_resources} >> >>"
            )
            objects.append(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")

        for image in image_entries:
            image_header = (
                f"<< /Type /XObject /Subtype /Image /Width {image['width_px']} /Height {image['height_px']} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(image['bytes'])} >>\nstream\n"
            ).encode("latin-1")
            objects.append(image_header + image["bytes"] + b"\nendstream")

        objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

        buffer = BytesIO()
        buffer.write(b"%PDF-1.4\n")
        offsets = [0]
        for idx, obj in enumerate(objects, start=1):
            offsets.append(buffer.tell())
            buffer.write(f"{idx} 0 obj\n".encode("latin-1"))
            if isinstance(obj, bytes):
                buffer.write(obj)
                buffer.write(b"\n")
            else:
                buffer.write(f"{obj}\n".encode("latin-1"))
            buffer.write(b"endobj\n")

        xref_pos = buffer.tell()
        buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        buffer.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            buffer.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
        buffer.write(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("latin-1")
        )
        return buffer.getvalue()


def carregar_logo_pdf(configuracao, max_width=120, max_height=42):
    if not configuracao or not configuracao.logo:
        return None

    try:
        with Image.open(configuracao.logo.path) as image:
            image = image.convert("RGB")
            image.thumbnail((max_width * 4, max_height * 4))
            output = BytesIO()
            image.save(output, format="JPEG", quality=88)
            return {
                "bytes": output.getvalue(),
                "width_px": image.width,
                "height_px": image.height,
                "draw_width": min(max_width, image.width / 4),
                "draw_height": min(max_height, image.height / 4),
            }
    except Exception:
        return None


def gerar_pdf_orcamento(orcamento, configuracao, alerta_status: StatusRelatorio) -> bytes:
    pdf = SimplePDF()
    empresa = configuracao.nome_empresa if configuracao else "Sua empresa"
    logo = carregar_logo_pdf(configuracao)

    pdf.rect(40, 760, 515, 54, fill_rgb=(0.48, 0.69, 1.0), stroke_rgb=(0.48, 0.69, 1.0))
    title_x = 52
    if logo:
        pdf.image(
            logo["bytes"],
            logo["width_px"],
            logo["height_px"],
            52,
            768,
            int(logo["draw_width"]),
            int(logo["draw_height"]),
        )
        title_x = 190

    pdf.text(title_x, 792, empresa, size=18)
    pdf.text(title_x, 772, f"Orçamento {orcamento.numero}", size=12)
    pdf.current_y = 736

    pdf.paragraph(f"Título: {orcamento.titulo}", size=14, leading=18)
    pdf.paragraph(f"Cliente: {orcamento.cliente}", size=11)
    pdf.paragraph(f"Status: {orcamento.get_status_display()}", size=11)
    pdf.paragraph(f"Emissão: {formatar_data(orcamento.data_emissao)}   Validade: {formatar_data(orcamento.validade_em)}", size=11)
    pdf.spacer(8)
    pdf.paragraph(f"{alerta_status.titulo}: {alerta_status.detalhe}", size=11, leading=16)
    pdf.spacer(12)

    if orcamento.descricao_inicial:
        pdf.paragraph("Descrição inicial", size=12, leading=16)
        pdf.paragraph(orcamento.descricao_inicial, size=10, leading=14)
        pdf.spacer(10)

    pdf.paragraph("Itens do orçamento", size=12, leading=16)
    for item in orcamento.itens.all().order_by("ordem", "id"):
        linha = (
            f"{item.ordem}. {item.nome} | {formatar_decimal_br(item.quantidade)} {item.get_unidade_medida_display()} | "
            f"Unit. {formatar_moeda(item.valor_unitario)} | Subtotal {formatar_moeda(item.subtotal)}"
        )
        pdf.paragraph(linha, size=10, leading=14)
        if item.descricao:
            pdf.paragraph(f"Descrição: {item.descricao}", size=9, leading=13)
        ajustes = []
        if item.desconto_valor or item.desconto_percentual:
            ajustes.append(
                f"Desconto: {formatar_moeda(item.desconto_valor)} + {formatar_decimal_br(item.desconto_percentual)}%"
            )
        if item.acrescimo_valor or item.acrescimo_percentual:
            ajustes.append(
                f"Acréscimo: {formatar_moeda(item.acrescimo_valor)} + {formatar_decimal_br(item.acrescimo_percentual)}%"
            )
        if ajustes:
            pdf.paragraph(" | ".join(ajustes), size=9, leading=13)
        pdf.spacer(6)

    pdf.spacer(10)
    pdf.paragraph("Resumo financeiro", size=12, leading=16)
    pdf.paragraph(f"Subtotal dos itens: {formatar_moeda(orcamento.subtotal_itens)}", size=10)
    pdf.paragraph(f"Desconto global em valor: {formatar_moeda(orcamento.desconto_global_valor)}", size=10)
    pdf.paragraph(
        f"Desconto global em percentual: {formatar_decimal_br(orcamento.desconto_global_percentual)}%",
        size=10,
    )
    pdf.paragraph(f"Acréscimo global em valor: {formatar_moeda(orcamento.acrescimo_global_valor)}", size=10)
    pdf.paragraph(
        f"Acréscimo global em percentual: {formatar_decimal_br(orcamento.acrescimo_global_percentual)}%",
        size=10,
    )
    pdf.paragraph(f"Total final: {formatar_moeda(orcamento.total_final)}", size=12, leading=16)

    if orcamento.observacoes_gerais:
        pdf.spacer(10)
        pdf.paragraph("Observações gerais", size=12, leading=16)
        pdf.paragraph(orcamento.observacoes_gerais, size=10, leading=14)

    if configuracao and configuracao.rodape_relatorio:
        pdf.spacer(12)
        pdf.paragraph(configuracao.rodape_relatorio, size=9, leading=13)

    return pdf.render()
