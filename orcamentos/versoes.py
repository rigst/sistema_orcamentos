"""Retratos, desfazer e refazer do orçamento.

O retrato guarda o que o usuário edita: os dados gerais (sem número, status,
empresa e autoria) e os itens com os valores que geram o subtotal. Os totais
não entram, porque são recalculados ao restaurar.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction

from catalogo.models import ItemCatalogo
from clientes.models import Cliente

from .models import ItemOrcamento, Orcamento
from .models_versoes import VersaoOrcamento

LIMITE_VERSOES = 60

CAMPOS_ORCAMENTO = (
    "titulo",
    "cliente_id",
    "descricao_inicial",
    "observacoes_gerais",
    "data_emissao",
    "validade_em",
    "evento_nome",
    "evento_periodo",
    "evento_local",
    "evento_estande",
    "evento_area",
    "evento_contato",
    "evento_telefone",
    "evento_email",
    "desconto_global_valor",
    "desconto_global_percentual",
    "acrescimo_global_valor",
    "acrescimo_global_percentual",
    "condicoes_pagamento",
    "valor_locacao",
    "valor_servico",
    "servicos_taxas_inclusos",
    "contrato_razao_social",
    "contrato_cnpj",
    "contrato_endereco",
    "contrato_cidade",
    "contrato_cep",
    "contrato_responsavel_nome",
    "contrato_responsavel_documento",
    "contrato_cargo_funcao",
    "contrato_telefone",
    "contrato_email",
    "contrato_inscricao_estadual",
)
CAMPOS_ITEM = (
    "item_catalogo_id",
    "ordem",
    "codigo_item",
    "nome",
    "descricao",
    "unidade_medida",
    "quantidade",
    "valor_unitario",
    "desconto_valor",
    "desconto_percentual",
    "acrescimo_valor",
    "acrescimo_percentual",
    "observacoes",
)
_DECIMAIS_ORCAMENTO = {
    "desconto_global_valor",
    "desconto_global_percentual",
    "acrescimo_global_valor",
    "acrescimo_global_percentual",
    "valor_locacao",
    "valor_servico",
}
_DECIMAIS_ITEM = {
    "quantidade",
    "valor_unitario",
    "desconto_valor",
    "desconto_percentual",
    "acrescimo_valor",
    "acrescimo_percentual",
}
_DATAS = {"data_emissao", "validade_em"}


def _para_json(valor):
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def _de_json(campo, valor, decimais):
    if valor is None:
        return None
    if campo in decimais:
        return Decimal(valor)
    if campo in _DATAS:
        return date.fromisoformat(valor)
    return valor


def retrato(orcamento: Orcamento) -> dict:
    itens = orcamento.itens.order_by("ordem", "id")
    return {
        "orcamento": {c: _para_json(getattr(orcamento, c)) for c in CAMPOS_ORCAMENTO},
        "itens": [
            {"id": item.pk, **{c: _para_json(getattr(item, c)) for c in CAMPOS_ITEM}}
            for item in itens
        ],
    }


def versao_atual(orcamento: Orcamento):
    return orcamento.versoes.filter(desfeita=False).order_by("-id").first()


def registrar_versao(orcamento: Orcamento, usuario, descricao: str):
    """Guarda o estado atual como versão nova, se ele mudou desde a última.

    Seguro de chamar depois de qualquer alteração: sem mudança, não faz nada.
    """
    dados = retrato(orcamento)
    with transaction.atomic():
        atual = versao_atual(orcamento)
        if atual is not None and atual.dados == dados:
            return None
        orcamento.versoes.filter(desfeita=True).delete()
        nova = VersaoOrcamento.objects.create(
            orcamento=orcamento,
            descricao=(descricao or "Alteração")[:200],
            dados=dados,
            criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        )
        antigas = list(
            orcamento.versoes.order_by("-id").values_list("id", flat=True)[LIMITE_VERSOES:]
        )
        if antigas:
            VersaoOrcamento.objects.filter(id__in=antigas).delete()
    return nova


def garantir_versao_base(orcamento: Orcamento, usuario):
    """Ao abrir o editor: se o estado mudou por fora (importação de memorial,
    exclusão de item na página de confirmação), registra antes de editar."""
    if not orcamento.versoes.exists():
        return registrar_versao(orcamento, usuario, "Estado ao abrir")
    return registrar_versao(orcamento, usuario, "Alterações fora do editor")


def _restaurar(orcamento: Orcamento, dados: dict):
    for campo, valor in dados["orcamento"].items():
        setattr(orcamento, campo, _de_json(campo, valor, _DECIMAIS_ORCAMENTO))
    if orcamento.cliente_id and not Cliente.objects.filter(pk=orcamento.cliente_id).exists():
        orcamento.cliente_id = None
    orcamento.save()

    catalogo_existente = set(
        ItemCatalogo.objects.filter(
            pk__in=[i["item_catalogo_id"] for i in dados["itens"] if i["item_catalogo_id"]]
        ).values_list("pk", flat=True)
    )
    manter = {i["id"] for i in dados["itens"]}
    orcamento.itens.exclude(pk__in=manter).delete()
    existentes = {item.pk: item for item in orcamento.itens.all()}
    for item_dados in dados["itens"]:
        item = existentes.get(item_dados["id"]) or ItemOrcamento(orcamento=orcamento)
        for campo in CAMPOS_ITEM:
            setattr(item, campo, _de_json(campo, item_dados[campo], _DECIMAIS_ITEM))
        if item.item_catalogo_id not in catalogo_existente:
            item.item_catalogo_id = None
        item.save()
    orcamento.recalcular_totais()


def desfazer(orcamento: Orcamento):
    """Volta para a versão anterior. Devolve a versão desfeita, ou None."""
    with transaction.atomic():
        ativas = list(orcamento.versoes.filter(desfeita=False).order_by("-id")[:2])
        if len(ativas) < 2:
            return None
        atual, anterior = ativas
        atual.desfeita = True
        atual.save(update_fields=["desfeita"])
        _restaurar(orcamento, anterior.dados)
    return atual


def refazer(orcamento: Orcamento):
    """Reaplica a versão desfeita mais antiga. Devolve ela, ou None."""
    with transaction.atomic():
        proxima = orcamento.versoes.filter(desfeita=True).order_by("id").first()
        if proxima is None:
            return None
        proxima.desfeita = False
        proxima.save(update_fields=["desfeita"])
        _restaurar(orcamento, proxima.dados)
    return proxima


def estado_historico(orcamento: Orcamento) -> dict:
    """O que os botões de desfazer e refazer precisam saber."""
    ativas = orcamento.versoes.filter(desfeita=False).order_by("-id")
    atual = ativas.first()
    proxima = orcamento.versoes.filter(desfeita=True).order_by("id").first()
    return {
        "pode_desfazer": ativas.count() > 1,
        "pode_refazer": proxima is not None,
        "desfazer_rotulo": atual.descricao if atual else "",
        "refazer_rotulo": proxima.descricao if proxima else "",
    }
