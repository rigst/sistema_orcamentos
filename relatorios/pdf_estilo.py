"""Identidade visual comum dos PDFs (mesma do site: Inter + Manrope, grafite e
azul, linhas finas, nada de caixa dentro de caixa)."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

FONTES = Path(__file__).resolve().parent / "fontes"

SANS = "Inter"
SANS_MEDIA = "Inter-Medium"
SANS_SEMI = "Inter-SemiBold"
SANS_BOLD = "Inter-Bold"
DISPLAY = "Manrope-Bold"
DISPLAY_FORTE = "Manrope-ExtraBold"

# Tokens do design system do site (stolben-ui.css).
TINTA = colors.HexColor("#111827")  # --ds-t-900
TEXTO = colors.HexColor("#374151")  # --ds-t-700
SUAVE = colors.HexColor("#586070")  # --ds-t-500
APAGADO = colors.HexColor("#8B91A0")  # --ds-t-400
LINHA = colors.HexColor("#E7E9EE")  # --ds-line
LINHA_FORTE = colors.HexColor("#D8DBE2")  # --ds-line-strong
PAINEL = colors.HexColor("#F7F8FA")  # --ds-panel
AZUL = colors.HexColor("#2563EB")  # --ds-blue
AZUL_ESCURO = colors.HexColor("#1D4ED8")
AZUL_50 = colors.HexColor("#EFF4FF")
GRAFITE = colors.HexColor("#0F1115")  # --ds-ink

LARGURA_PAGINA, ALTURA_PAGINA = A4
MARGEM_X = 16 * mm
LARGURA_UTIL = LARGURA_PAGINA - 2 * MARGEM_X

STATUS_CORES = {
    "success": (colors.HexColor("#ECFDF3"), colors.HexColor("#15803D")),
    "warning": (colors.HexColor("#FFFBEB"), colors.HexColor("#B45309")),
    "danger": (colors.HexColor("#FEF2F2"), colors.HexColor("#B91C1C")),
    "info": (AZUL_50, AZUL_ESCURO),
}


def registrar_fontes() -> None:
    for nome, arquivo in (
        (SANS, "Inter-Regular.ttf"),
        (SANS_MEDIA, "Inter-Medium.ttf"),
        (SANS_SEMI, "Inter-SemiBold.ttf"),
        (SANS_BOLD, "Inter-Bold.ttf"),
        (DISPLAY, "Manrope-Bold.ttf"),
        (DISPLAY_FORTE, "Manrope-ExtraBold.ttf"),
    ):
        try:
            pdfmetrics.getFont(nome)
        except KeyError:
            pdfmetrics.registerFont(TTFont(nome, str(FONTES / arquivo)))
    pdfmetrics.registerFontFamily(
        SANS, normal=SANS, bold=SANS_SEMI, italic=SANS, boldItalic=SANS_SEMI
    )


# Estilos de parágrafo: nome -> ajustes sobre o texto base.
_BASE = {"fontName": SANS, "fontSize": 9.5, "leading": 13.5, "textColor": TEXTO}
_ESTILOS: dict[str, dict] = {
    "empresa": {"fontName": DISPLAY, "fontSize": 13, "leading": 16, "textColor": TINTA},
    "empresa_info": {"fontSize": 8, "leading": 11, "textColor": SUAVE},
    "rotulo": {"fontName": SANS_SEMI, "fontSize": 7, "leading": 9, "textColor": SUAVE},
    "titulo": {"fontName": DISPLAY_FORTE, "fontSize": 24, "leading": 28, "textColor": TINTA},
    "subtitulo": {"fontSize": 11, "leading": 15, "textColor": SUAVE},
    "secao": {
        "fontName": SANS_SEMI,
        "fontSize": 7.5,
        "leading": 10,
        "textColor": SUAVE,
        "spaceBefore": 16,
        "spaceAfter": 8,
    },
    "corpo": {},
    "corpo_forte": {"fontName": SANS_SEMI, "textColor": TINTA},
    "valor": {"fontName": SANS_MEDIA, "textColor": TINTA},
    "pequeno": {"fontSize": 8, "leading": 11, "textColor": SUAVE},
    "celula": {"fontSize": 9, "leading": 12.5},
    "celula_nome": {"fontName": SANS_SEMI, "fontSize": 9, "leading": 12.5, "textColor": TINTA},
    "celula_detalhe": {"fontSize": 8, "leading": 11, "textColor": SUAVE},
    "celula_num": {"fontSize": 9, "leading": 12.5, "alignment": TA_RIGHT},
    "celula_num_forte": {
        "fontName": SANS_SEMI,
        "fontSize": 9,
        "leading": 12.5,
        "alignment": TA_RIGHT,
        "textColor": TINTA,
    },
    "cabeca": {"fontName": SANS_SEMI, "fontSize": 7, "leading": 9, "textColor": SUAVE},
    "cabeca_num": {
        "fontName": SANS_SEMI,
        "fontSize": 7,
        "leading": 9,
        "textColor": SUAVE,
        "alignment": TA_RIGHT,
    },
    "categoria": {"fontName": SANS_SEMI, "fontSize": 8.5, "leading": 11, "textColor": TINTA},
    "conta_rotulo": {"fontSize": 9.5, "leading": 13, "textColor": SUAVE},
    "conta_valor": {
        "fontName": SANS_MEDIA,
        "fontSize": 9.5,
        "leading": 13,
        "textColor": TINTA,
        "alignment": TA_RIGHT,
    },
    "total_rotulo": {"fontName": SANS_SEMI, "fontSize": 11, "leading": 15, "textColor": TINTA},
    "total_valor": {
        "fontName": DISPLAY_FORTE,
        "fontSize": 20,
        "leading": 24,
        "textColor": TINTA,
        "alignment": TA_RIGHT,
    },
    "lista": {"leftIndent": 12, "bulletIndent": 0, "spaceAfter": 3},
}


def estilos() -> dict[str, ParagraphStyle]:
    return {
        nome: ParagraphStyle(nome, **{**_BASE, **ajustes}) for nome, ajustes in _ESTILOS.items()
    }


def texto(valor) -> str:
    """Escapa para o mini-HTML do reportlab e mantém as quebras de linha."""
    return escape(str(valor or "").strip()).replace("\n", "<br/>")


def carregar_logo(configuracao, largura_max=46 * mm, altura_max=16 * mm):
    if not configuracao or not configuracao.logo:
        return None
    try:
        with PILImage.open(configuracao.logo.path) as imagem:
            convertida = imagem.convert("RGBA")
            fundo = PILImage.new("RGBA", convertida.size, (255, 255, 255, 255))
            fundo.alpha_composite(convertida)
            rgb = fundo.convert("RGB")
            rgb.thumbnail((int(largura_max / mm * 12), int(altura_max / mm * 12)))
            buffer = BytesIO()
            rgb.save(buffer, format="PNG")
            buffer.seek(0)
            proporcao = rgb.width / rgb.height
            largura = min(largura_max, altura_max * proporcao)
            return Image(buffer, width=largura, height=largura / proporcao)
    except (OSError, ValueError, PILImage.DecompressionBombError):
        # Logo ausente no disco ou arquivo inválido: o relatório sai sem logo,
        # mas o problema fica registrado para alguém corrigir o cadastro.
        logger.warning(
            "Logo da empresa %s ilegível; relatório gerado sem logo.",
            getattr(configuracao, "empresa_id", "?"),
            exc_info=True,
        )
        return None


def _identidade_empresa(configuracao, nome: str, logo, est) -> list:
    """Lado esquerdo do topo: a logo, ou o nome (e o fantasia) quando não há logo."""
    if logo:
        return [logo]
    fantasia = configuracao.nome_fantasia if configuracao and configuracao.nome_fantasia else ""
    bloco = [Paragraph(texto(nome), est["empresa"])] if nome else []
    if fantasia and fantasia != nome:
        bloco.append(Paragraph(texto(fantasia), est["empresa_info"]))
    return bloco


def cabecalho_empresa(configuracao, est, linhas_contato: list[str]):
    """Logo + nome à esquerda; dados de contato à direita. Sem caixa."""
    nome = configuracao.nome_empresa if configuracao and configuracao.nome_empresa else ""
    logo = carregar_logo(configuracao)
    esquerda = _identidade_empresa(configuracao, nome, logo, est)
    direita = [Paragraph(texto(nome), est["corpo_forte"])] if logo and nome else []
    direita += [Paragraph(texto(linha), est["empresa_info"]) for linha in linhas_contato]
    if not esquerda and not direita:
        # Empresa sem cadastro: nada de faixa vazia no topo.
        return Spacer(1, 0)
    for p in direita:
        p.style = ParagraphStyle("dir", parent=p.style, alignment=TA_RIGHT)
    tabela = Table(
        [[esquerda or "", direita or ""]], colWidths=[LARGURA_UTIL * 0.45, LARGURA_UTIL * 0.55]
    )
    tabela.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINHA_FORTE),
            ]
        )
    )
    return tabela


def faixa_de_dados(campos: list[tuple[str, str]], est, colunas: int = 4):
    """Grade de "RÓTULO / valor" em colunas, separadas por linhas finas."""
    celulas: list[object] = [
        [Paragraph(rotulo.upper(), est["rotulo"]), Paragraph(texto(valor) or "-", est["valor"])]
        for rotulo, valor in campos
    ]
    linhas = [celulas[i : i + colunas] for i in range(0, len(celulas), colunas)]
    for linha in linhas:
        linha += [""] * (colunas - len(linha))
    tabela = Table(linhas, colWidths=[LARGURA_UTIL / colunas] * colunas)
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINHA),
    ]
    tabela.setStyle(TableStyle(estilo))
    return tabela


def desenhar_rodape(rotulo_documento: str, empresa: str):
    def desenhar(canvas, doc):
        canvas.saveState()
        y = 10 * mm
        canvas.setStrokeColor(LINHA)
        canvas.setLineWidth(0.5)
        canvas.line(MARGEM_X, y + 4.5 * mm, LARGURA_PAGINA - MARGEM_X, y + 4.5 * mm)
        canvas.setFont(SANS, 7.5)
        canvas.setFillColor(APAGADO)
        esquerda = " · ".join(p for p in (empresa, rotulo_documento) if p)
        canvas.drawString(MARGEM_X, y, esquerda)
        canvas.drawRightString(LARGURA_PAGINA - MARGEM_X, y, f"Página {doc.page}")
        canvas.restoreState()

    return desenhar
