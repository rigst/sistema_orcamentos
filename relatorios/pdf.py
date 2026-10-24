"""PDF da proposta (orçamento) e do memorial descritivo."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    CondPageBreak,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.formatting import formatar_decimal_br

from . import conteudo as c
from .pdf_estilo import (
    AZUL,
    LARGURA_UTIL,
    LINHA,
    LINHA_FORTE,
    MARGEM_X,
    PAINEL,
    STATUS_CORES,
    TINTA,
    cabecalho_empresa,
    desenhar_rodape,
    estilos,
    faixa_de_dados,
    registrar_fontes,
    texto,
)


def _documento(buffer, titulo: str, autor: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buffer,
        leftMargin=MARGEM_X,
        rightMargin=MARGEM_X,
        topMargin=14 * mm,
        bottomMargin=20 * mm,
        title=titulo,
        author=autor,
        pageCompression=0,
    )


def _secao(titulo: str, est):
    return Paragraph(titulo.upper(), est["secao"])


def _selo_status(alerta: c.StatusRelatorio, est):
    fundo, cor = STATUS_CORES.get(alerta.nivel, STATUS_CORES["info"])
    hexa = cor.hexval()[2:]
    selo = Table(
        [
            [
                Paragraph(
                    f"<font color='#{hexa}'><b>{texto(alerta.titulo)}</b></font> · {texto(alerta.detalhe)}",
                    est["pequeno"],
                )
            ]
        ],
        colWidths=[LARGURA_UTIL],
    )
    selo.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fundo),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ]
        )
    )
    return selo


# Colunas da tabela de itens: nome ocupa o que sobra; números nunca quebram.
_COLUNAS = (8 * mm, None, 26 * mm, 27 * mm, 29 * mm)


def _larguras():
    fixas = sum(w for w in _COLUNAS if w)
    return [w if w else LARGURA_UTIL - fixas for w in _COLUNAS]


def _linha_item(numero: int, item, mostrar_ajustes: bool, est) -> list:
    detalhe = []
    if item.codigo_item:
        detalhe.append(texto(item.codigo_item))
    descricao = (item.descricao or "").strip()
    if descricao and descricao != item.nome:
        detalhe.append(texto(descricao))
    if mostrar_ajustes:
        detalhe += [texto(a) for a in c.ajustes_do_item(item)]
    celula_item = [Paragraph(texto(item.nome), est["celula_nome"])]
    if detalhe:
        celula_item.append(Paragraph("<br/>".join(detalhe), est["celula_detalhe"]))
    quantidade = f"{formatar_decimal_br(item.quantidade)}&nbsp;{texto(c.unidade_curta(item))}"
    return [
        Paragraph(str(numero), est["celula_detalhe"]),
        celula_item,
        Paragraph(quantidade, est["celula_num"]),
        Paragraph(c.formatar_moeda(item.valor_unitario).replace(" ", "&nbsp;"), est["celula_num"]),
        Paragraph(c.formatar_moeda(item.subtotal).replace(" ", "&nbsp;"), est["celula_num_forte"]),
    ]


def _linha_categoria(grupo, est) -> list:
    cor = grupo["categoria_cor"] or "#94A3B8"
    return [
        "",
        Paragraph(
            f"<font color='{cor}'>●</font>&nbsp;&nbsp;{texto(grupo['categoria_nome'])}",
            est["categoria"],
        ),
        "",
        "",
        Paragraph(c.formatar_moeda(grupo["subtotal"]), est["celula_num_forte"]),
    ]


def _tabela_itens(orcamento, est):
    mostrar_ajustes = orcamento.mostrar_ajustes_no_relatorio
    cabeca = [
        Paragraph("#", est["cabeca"]),
        Paragraph("ITEM", est["cabeca"]),
        Paragraph("QUANTIDADE", est["cabeca_num"]),
        Paragraph("VALOR UNIT.", est["cabeca_num"]),
        Paragraph("SUBTOTAL", est["cabeca_num"]),
    ]
    linhas = [cabeca]
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINHA_FORTE),
    ]
    grupos = orcamento.subtotais_por_categoria()
    varias_categorias = len(grupos) > 1
    numero = 0
    for grupo in grupos:
        if varias_categorias:
            idx = len(linhas)
            linhas.append(_linha_categoria(grupo, est))
            estilo += [
                ("SPAN", (1, idx), (3, idx)),
                ("BACKGROUND", (0, idx), (-1, idx), PAINEL),
                ("TOPPADDING", (0, idx), (-1, idx), 5),
                ("BOTTOMPADDING", (0, idx), (-1, idx), 5),
                ("LEFTPADDING", (0, idx), (0, idx), 4),
                ("RIGHTPADDING", (-1, idx), (-1, idx), 4),
                ("NOSPLIT", (0, idx), (-1, idx + 1)),
            ]
        for item in grupo["itens"]:
            numero += 1
            linhas.append(_linha_item(numero, item, mostrar_ajustes, est))
            estilo.append(("LINEBELOW", (0, len(linhas) - 1), (-1, len(linhas) - 1), 0.4, LINHA))
    tabela = Table(linhas, colWidths=_larguras(), repeatRows=1)
    tabela.setStyle(TableStyle(estilo))
    return tabela


def _conta(orcamento, est):
    linhas = [
        [
            Paragraph(texto(linha.rotulo), est["conta_rotulo"]),
            Paragraph(
                f"{'− ' if linha.sinal == '-' else '+ ' if linha.sinal == '+' else ''}"
                f"{linha.valor.replace(' ', '&nbsp;')}",
                est["conta_valor"],
            ),
        ]
        for linha in c.linhas_da_conta(orcamento)
    ]
    linhas.append(
        [
            Paragraph("Total", est["total_rotulo"]),
            Paragraph(
                c.formatar_moeda(orcamento.total_final).replace(" ", "&nbsp;"), est["total_valor"]
            ),
        ]
    )
    largura = 100 * mm
    tabela = Table(linhas, colWidths=[largura * 0.4, largura * 0.6], hAlign="RIGHT")
    n = len(linhas) - 1
    tabela.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, n), (-1, n), "BOTTOM"),
                ("LINEABOVE", (0, n), (-1, n), 1.4, TINTA),
                ("TOPPADDING", (0, n), (-1, n), 9),
            ]
        )
    )
    return tabela


def _blocos_texto(secoes: list[c.SecaoTexto], est):
    blocos = []
    for secao in secoes:
        blocos.append(
            KeepTogether([_secao(secao.titulo, est), Paragraph(texto(secao.texto), est["corpo"])])
        )
    return blocos


def gerar_pdf_orcamento(orcamento, configuracao, alerta_status: c.StatusRelatorio) -> bytes:
    registrar_fontes()
    est = estilos()
    buffer = BytesIO()
    empresa = c.nome_empresa(configuracao)
    doc = _documento(buffer, f"Orçamento {orcamento.numero}", empresa)

    story = [cabecalho_empresa(configuracao, est, c.contato_empresa(configuracao)), Spacer(1, 18)]
    story.append(Paragraph(f"PROPOSTA COMERCIAL · {texto(orcamento.numero)}", est["rotulo"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(texto(orcamento.titulo), est["titulo"]))
    if orcamento.status != "aprovado" and orcamento.status != "enviado":
        story += [Spacer(1, 8), _selo_status(alerta_status, est)]
    story.append(Spacer(1, 12))

    campos = [
        ("Cliente", orcamento.cliente_exibicao),
        ("Emissão", c.formatar_data(orcamento.data_emissao)),
        ("Validade", c.validade_texto(orcamento, configuracao) or "-"),
        ("Total", c.formatar_moeda(orcamento.total_final)),
    ]
    evento = [
        ("Evento", orcamento.evento_nome),
        ("Data e local", c.linha_data_local(orcamento)),
        ("Estande", orcamento.evento_estande),
        ("Área", orcamento.evento_area),
    ]
    story.append(faixa_de_dados(campos, est))
    dados_evento = [c.Campo(r, v) for r, v in evento if v]
    if dados_evento:
        story += [Spacer(1, 2), _lista_campos(dados_evento, est, largura_rotulo=32 * mm)]

    if orcamento.mostrar_descricao_inicial_no_relatorio and orcamento.descricao_inicial:
        story += [
            _secao("Apresentação", est),
            Paragraph(texto(orcamento.descricao_inicial), est["corpo"]),
        ]

    story += [_secao("Itens", est), _tabela_itens(orcamento, est), Spacer(1, 14)]
    story.append(KeepTogether([_conta(orcamento, est)]))
    story += _blocos_texto(c.secoes_finais_orcamento(orcamento, configuracao), est)

    rodape = c.rodape_institucional(orcamento, configuracao)
    if rodape:
        story += [Spacer(1, 18), Paragraph(texto(rodape), est["pequeno"])]

    desenhar = desenhar_rodape(f"Orçamento {orcamento.numero}", empresa)
    doc.build(story, onFirstPage=desenhar, onLaterPages=desenhar)
    return buffer.getvalue()


# ---------------------------------------------------------------- memorial


def _lista_campos(campos: list[c.Campo], est, largura_rotulo=46 * mm):
    linhas = [
        [
            Paragraph(texto(campo.rotulo), est["pequeno"]),
            Paragraph(texto(campo.valor), est["corpo"]),
        ]
        for campo in campos
    ]
    tabela = Table(linhas, colWidths=[largura_rotulo, LARGURA_UTIL - largura_rotulo])
    tabela.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINHA),
            ]
        )
    )
    return tabela


def _categorias_memorial(categorias, est) -> list:
    story: list = []
    for grupo in categorias:
        cor = grupo["categoria_cor"] or "#94A3B8"
        titulo = Paragraph(
            f"<font color='{cor}'>●</font>&nbsp;&nbsp;{texto(grupo['categoria_nome'])}",
            est["corpo_forte"],
        )
        cabeca = Table(
            [[titulo, Paragraph(c.formatar_moeda(grupo["subtotal"]), est["celula_num_forte"])]],
            colWidths=[LARGURA_UTIL - 40 * mm, 40 * mm],
        )
        cabeca.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINHA_FORTE),
                ]
            )
        )
        itens = [
            Paragraph(texto(c.linha_item_memorial(item)), est["lista"], bulletText="–")
            for item in grupo["itens"]
        ]
        story += [
            CondPageBreak(30 * mm),
            Spacer(1, 14),
            KeepTogether([cabeca, Spacer(1, 6), *itens[:2]]),
            *itens[2:],
        ]
    return story


def _assinatura(linhas: list[str], est):
    bloco: list = [Spacer(1, 36)]
    traco = Table([[""]], colWidths=[70 * mm], hAlign="LEFT")
    traco.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.8, TINTA)]))
    bloco.append(traco)
    bloco.append(Paragraph(texto(linhas[0]), est["corpo_forte"]))
    bloco += [Paragraph(texto(p), est["pequeno"]) for p in linhas[1:]]
    return KeepTogether(bloco)


def gerar_pdf_memorial_descritivo(orcamento, configuracao) -> bytes:
    registrar_fontes()
    est = estilos()
    buffer = BytesIO()
    empresa = c.nome_empresa(configuracao)
    doc = _documento(buffer, f"Memorial Descritivo {orcamento.numero}", empresa)
    memorial = c.montar_memorial(orcamento, configuracao)

    story = [cabecalho_empresa(configuracao, est, c.contato_empresa(configuracao)), Spacer(1, 18)]
    story.append(Paragraph(f"MEMORIAL DESCRITIVO · {texto(orcamento.numero)}", est["rotulo"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(texto(orcamento.evento_nome or orcamento.titulo), est["titulo"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(texto(memorial.local_data), est["subtitulo"]))
    story.append(Spacer(1, 12))
    story.append(_lista_campos(memorial.cabecalho, est, largura_rotulo=32 * mm))
    story += [
        Spacer(1, 14),
        Paragraph(texto(memorial.saudacao), est["corpo"]),
        Spacer(1, 4),
        Paragraph(texto(memorial.introducao), est["corpo"]),
    ]

    story += _categorias_memorial(memorial.categorias, est)

    if memorial.financeiro:
        story += [
            CondPageBreak(40 * mm),
            _secao("Condições comerciais", est),
            _lista_campos(memorial.financeiro, est),
        ]
    story += _blocos_texto(memorial.secoes, est)
    if memorial.contrato:
        story += [
            CondPageBreak(40 * mm),
            _secao("Dados para contrato", est),
            _lista_campos(memorial.contrato, est),
        ]

    if memorial.assinatura:
        story.append(_assinatura(memorial.assinatura, est))

    desenhar = desenhar_rodape(f"Memorial descritivo {orcamento.numero}", empresa)
    doc.build(story, onFirstPage=desenhar, onLaterPages=desenhar)
    return buffer.getvalue()


__all__ = ["AZUL", "colors", "gerar_pdf_memorial_descritivo", "gerar_pdf_orcamento"]
