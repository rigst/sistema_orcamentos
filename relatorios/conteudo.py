"""Conteúdo dos relatórios, independente de formato.

Os geradores (PDF, planilha, Word) só cuidam do desenho: o que entra em cada
documento, com que texto e em que ordem, sai daqui. Assim os quatro arquivos
contam a mesma história.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from core.formatting import formatar_decimal_br, formatar_moeda_br


@dataclass
class StatusRelatorio:
    titulo: str
    detalhe: str
    nivel: str


_STATUS = {
    "aprovado": (
        "Orçamento aprovado",
        "Documento apto para envio formal ao cliente e registro comercial.",
        "success",
    ),
    "enviado": (
        "Orçamento enviado",
        "Documento já foi encaminhado ao cliente. Revise apenas se houver nova versão.",
        "info",
    ),
    "rascunho": (
        "Orçamento em rascunho",
        "Este documento ainda pode conter valores e itens provisórios. Use com cautela.",
        "warning",
    ),
    "em_elaboracao": (
        "Orçamento em elaboração",
        "O conteúdo ainda está em montagem. Confirme itens e totais antes de compartilhar.",
        "warning",
    ),
    "rejeitado": (
        "Orçamento rejeitado",
        "O cliente ou processo interno marcou este orçamento como rejeitado.",
        "danger",
    ),
}
_STATUS_CANCELADO = (
    "Orçamento cancelado",
    "Documento cancelado. A exportação deve ser usada apenas para histórico ou conferência interna.",
    "danger",
)


def obter_alerta_status(orcamento) -> StatusRelatorio:
    titulo, detalhe, nivel = _STATUS.get(orcamento.status, _STATUS_CANCELADO)
    return StatusRelatorio(titulo=titulo, detalhe=detalhe, nivel=nivel)


MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def formatar_moeda(valor: Decimal) -> str:
    return formatar_moeda_br(valor)


def formatar_data(valor: date | None) -> str:
    return valor.strftime("%d/%m/%Y") if valor else "-"


def formatar_data_extenso(valor: date | None) -> str:
    if not valor:
        return "-"
    return f"{valor.day:02d} de {MESES[valor.month - 1]} de {valor.year}"


def texto_ou_linha(valor: str | None, *, tamanho: int = 30) -> str:
    texto = str(valor or "").strip()
    return texto or "_" * tamanho


_UNIDADES = {
    "un": ("Unidade", "Unidades"),
    "hr": ("Hora", "Horas"),
    "dia": ("Dia", "Dias"),
    "m": ("Metro", "Metros"),
    "m2": ("Metro quadrado", "Metros quadrados"),
    "m3": ("Metro cúbico", "Metros cúbicos"),
    "kg": ("Quilo", "Quilos"),
    "cx": ("Caixa", "Caixas"),
    "pct": ("Pacote", "Pacotes"),
    "sv": ("Serviço", "Serviços"),
}

# Forma curta para colunas estreitas (tabela do PDF e planilha).
_UNIDADES_CURTAS = {"m2": "m²", "m3": "m³", "hr": "h", "sv": "serv.", "un": "un", "-": "-"}


def formatar_unidade_relatorio(item) -> str:
    unidade = (item.unidade_medida or "").strip()
    if unidade == "-":
        return "-"
    if unidade in _UNIDADES:
        singular, plural = _UNIDADES[unidade]
        return singular if item.quantidade == 1 else plural
    return item.get_unidade_medida_display()


def unidade_curta(item) -> str:
    unidade = (item.unidade_medida or "").strip()
    return _UNIDADES_CURTAS.get(unidade, unidade)


def nome_empresa(configuracao) -> str:
    return configuracao.nome_empresa if configuracao and configuracao.nome_empresa else ""


def linha_data_local(orcamento) -> str:
    partes = [p for p in (orcamento.evento_periodo, orcamento.evento_local) if p]
    return " em ".join(partes)


def validade_texto(orcamento, configuracao) -> str:
    if orcamento.validade_em:
        return formatar_data(orcamento.validade_em)
    if configuracao and configuracao.validade_padrao_proposta:
        padrao = str(configuracao.validade_padrao_proposta).strip()
        return padrao if not padrao.isdigit() else f"{padrao} dias"
    return ""


def descricao_do_item(item) -> str:
    return (item.descricao or "").strip() or item.nome


def ajustes_do_item(item) -> list[str]:
    linhas = []
    if item.desconto_valor or item.desconto_percentual:
        linhas.append(
            f"Desconto: {formatar_moeda(item.desconto_valor)} + "
            f"{formatar_decimal_br(item.desconto_percentual)}%"
        )
    if item.acrescimo_valor or item.acrescimo_percentual:
        linhas.append(
            f"Acréscimo: {formatar_moeda(item.acrescimo_valor)} + "
            f"{formatar_decimal_br(item.acrescimo_percentual)}%"
        )
    return linhas


@dataclass
class LinhaConta:
    rotulo: str
    valor: str
    sinal: str = ""  # "-", "+" ou "" (subtotal/total)
    valor_numerico: float = 0.0  # com sinal, para a planilha


def linhas_da_conta(orcamento) -> list[LinhaConta]:
    """Subtotal, ajustes globais (só os que existem) e total."""
    linhas = [
        LinhaConta(
            "Subtotal dos itens",
            formatar_moeda(orcamento.subtotal_itens),
            valor_numerico=float(orcamento.subtotal_itens),
        )
    ]
    ajustes = (
        (
            "Desconto",
            "-",
            orcamento.desconto_global_valor,
            orcamento.desconto_global_percentual,
            orcamento.valor_desconto_percentual_global,
        ),
        (
            "Acréscimo",
            "+",
            orcamento.acrescimo_global_valor,
            orcamento.acrescimo_global_percentual,
            orcamento.valor_acrescimo_percentual_global,
        ),
    )
    for nome, sinal, valor, percentual, valor_do_percentual in ajustes:
        fator = -1 if sinal == "-" else 1
        if valor:
            linhas.append(
                LinhaConta(f"{nome} em valor", formatar_moeda(valor), sinal, fator * float(valor))
            )
        if percentual:
            linhas.append(
                LinhaConta(
                    f"{nome} de {formatar_decimal_br(percentual)}%",
                    formatar_moeda(valor_do_percentual),
                    sinal,
                    fator * float(valor_do_percentual),
                )
            )
    return linhas


@dataclass
class SecaoTexto:
    titulo: str
    texto: str


def secoes_finais_orcamento(orcamento) -> list[SecaoTexto]:
    secoes = []
    if orcamento.condicoes_pagamento:
        secoes.append(SecaoTexto("Condições de pagamento", orcamento.condicoes_pagamento))
    if orcamento.servicos_taxas_inclusos:
        secoes.append(SecaoTexto("Serviços e taxas inclusos", orcamento.servicos_taxas_inclusos))
    if orcamento.mostrar_observacoes_gerais_no_relatorio and orcamento.observacoes_gerais:
        secoes.append(SecaoTexto("Observações", orcamento.observacoes_gerais))
    return secoes


def rodape_institucional(orcamento, configuracao) -> str:
    if (
        orcamento.mostrar_rodape_institucional_no_relatorio
        and configuracao
        and configuracao.rodape_relatorio
    ):
        return configuracao.rodape_relatorio.strip()
    return ""


def contato_empresa(configuracao) -> list[str]:
    """Linhas curtas de identificação da empresa (CNPJ, endereço, contato)."""
    if not configuracao:
        return []
    linhas = []
    if configuracao.cpf_cnpj:
        linhas.append(f"CNPJ {configuracao.cpf_cnpj}")
    rua = ", ".join(p for p in (configuracao.logradouro, configuracao.numero) if p)
    if configuracao.complemento:
        rua = f"{rua} - {configuracao.complemento}" if rua else configuracao.complemento
    cidade = "/".join(p for p in (configuracao.cidade, configuracao.estado) if p)
    endereco = " · ".join(p for p in (rua, configuracao.bairro, cidade) if p)
    if endereco:
        linhas.append(endereco)
    contato = " · ".join(
        p for p in (configuracao.telefone, configuracao.email, configuracao.site) if p
    )
    if contato:
        linhas.append(contato)
    return linhas


# ---------------------------------------------------------------- memorial


@dataclass
class Campo:
    rotulo: str
    valor: str


@dataclass
class ConteudoMemorial:
    local_data: str
    cabecalho: list[Campo]
    saudacao: str
    introducao: str
    categorias: list[dict]
    financeiro: list[Campo] = field(default_factory=list)
    secoes: list[SecaoTexto] = field(default_factory=list)
    contrato: list[Campo] = field(default_factory=list)
    assinatura: list[str] = field(default_factory=list)


INTRODUCAO_MEMORIAL = (
    "Conforme solicitado, apresentamos proposta para prestação de serviços, locação, "
    "montagem e desmontagem de estande, conforme descritivo abaixo."
)


def _campos(pares) -> list[Campo]:
    return [
        Campo(rotulo, str(valor).strip()) for rotulo, valor in pares if str(valor or "").strip()
    ]


def _cabecalho_memorial(orcamento) -> list[Campo]:
    cabecalho = _campos(
        (
            ("Expositor", orcamento.cliente_exibicao),
            ("Evento", orcamento.evento_nome or orcamento.titulo),
            ("Data e local", linha_data_local(orcamento)),
            ("Estande", orcamento.evento_estande),
            ("Área", orcamento.evento_area),
        )
    )
    if orcamento.mostrar_contatos_evento_no_memorial:
        cabecalho += _campos(
            (
                ("A/C", orcamento.evento_contato),
                ("Telefone", orcamento.evento_telefone),
                ("E-mail", orcamento.evento_email),
            )
        )
    return cabecalho


def _financeiro_memorial(orcamento, configuracao) -> list[Campo]:
    financeiro = [("Valor total", formatar_moeda(orcamento.total_final))]
    if orcamento.valor_locacao:
        financeiro.append(("Locação", formatar_moeda(orcamento.valor_locacao)))
    if orcamento.valor_servico:
        financeiro.append(("Serviço", formatar_moeda(orcamento.valor_servico)))
    financeiro.append(("Condições de pagamento", orcamento.condicoes_pagamento))
    if configuracao:
        financeiro.append(("Dados bancários", configuracao.dados_bancarios))
        financeiro.append(("Chave PIX", configuracao.chave_pix))
    financeiro.append(("Validade da proposta", validade_texto(orcamento, configuracao)))
    return _campos(financeiro)


def _contrato_memorial(orcamento) -> list[Campo]:
    return _campos(
        (
            ("Razão social", orcamento.contrato_razao_social),
            ("CNPJ", orcamento.contrato_cnpj),
            ("Endereço", orcamento.contrato_endereco),
            ("Cidade", orcamento.contrato_cidade),
            ("CEP", orcamento.contrato_cep),
            ("Inscrição estadual", orcamento.contrato_inscricao_estadual),
            ("Responsável pela assinatura", orcamento.contrato_responsavel_nome),
            ("RG e CPF do responsável", orcamento.contrato_responsavel_documento),
            ("Cargo ou função", orcamento.contrato_cargo_funcao),
            ("Telefone", orcamento.contrato_telefone),
            ("E-mail para o contrato", orcamento.contrato_email),
        )
    )


def montar_memorial(orcamento, configuracao) -> ConteudoMemorial:
    cidade = configuracao.cidade if configuracao and configuracao.cidade else "Porto Alegre"
    cabecalho = _cabecalho_memorial(orcamento)
    conteudo = ConteudoMemorial(
        local_data=f"{cidade}, {formatar_data_extenso(orcamento.data_emissao)}",
        cabecalho=cabecalho,
        saudacao="Prezados,",
        introducao=INTRODUCAO_MEMORIAL,
        categorias=orcamento.subtotais_por_categoria(),
    )

    if orcamento.mostrar_financeiro_no_memorial:
        conteudo.financeiro = _financeiro_memorial(orcamento, configuracao)

    if orcamento.servicos_taxas_inclusos:
        conteudo.secoes.append(SecaoTexto("Serviços e taxas", orcamento.servicos_taxas_inclusos))
    if orcamento.mostrar_observacoes_gerais_no_relatorio and orcamento.observacoes_gerais:
        conteudo.secoes.append(SecaoTexto("Observações", orcamento.observacoes_gerais))

    if orcamento.mostrar_dados_contratuais_no_memorial:
        conteudo.contrato = _contrato_memorial(orcamento)

    if orcamento.mostrar_informacoes_complementares_no_memorial and configuracao:
        complementares = "\n\n".join(
            p
            for p in (
                getattr(configuracao, "texto_institucional_memorial", ""),
                getattr(configuracao, "rodape_relatorio", ""),
            )
            if p
        )
        if complementares:
            conteudo.secoes.append(SecaoTexto("Informações complementares", complementares))

    if configuracao:
        conteudo.assinatura = [
            p
            for p in (
                configuracao.assinatura_nome,
                configuracao.assinatura_cargo,
                configuracao.assinatura_contato,
            )
            if p
        ]
    return conteudo


def linha_item_memorial(item) -> str:
    quantidade = formatar_decimal_br(item.quantidade)
    return f"{quantidade} {formatar_unidade_relatorio(item).lower()} de {descricao_do_item(item)}"
