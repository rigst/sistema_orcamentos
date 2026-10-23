"""Leva para o catálogo os itens que a IA sugeriu fora dele.

Depois da importação, os itens novos estão só no orçamento, sem vínculo com o
catálogo. Aqui o usuário escolhe quais viram item de catálogo e em qual
categoria (existente ou nova). O valor padrão é o que o item tem no orçamento
NESTE momento, ou seja, o preço que o usuário já ajustou na linha.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from catalogo.models import CategoriaItem, ItemCatalogo
from orcamentos.models import ItemOrcamento

from .models import ImportacaoMemorial

UNIDADES_CATALOGO = {codigo for codigo, _ in ItemCatalogo.UNIDADE_CHOICES}


@dataclass(frozen=True)
class Escolha:
    item_id: int
    categoria_id: int | None
    categoria_nova: str


def itens_fora_do_catalogo(importacao: ImportacaoMemorial):
    """Itens desta importação que ainda não estão no catálogo, como tuplas
    (item, categoria sugerida pela IA). Só os que ainda existem no orçamento."""
    sugestoes = {
        s.get("item_id"): s
        for s in (importacao.resultado or {}).get("itens") or []
        if s.get("item_id") and not s.get("no_catalogo")
    }
    if not sugestoes:
        return []
    itens = ItemOrcamento.objects.filter(
        orcamento=importacao.orcamento, pk__in=sugestoes, item_catalogo__isnull=True
    ).order_by("ordem", "id")
    return [(item, (sugestoes[item.pk].get("categoria_sugerida") or "").strip()) for item in itens]


def opcoes_para_catalogar(importacao: ImportacaoMemorial):
    """Como `itens_fora_do_catalogo`, com o id da categoria existente que
    casa com a sugestão (sem diferenciar maiúsculas) ou None, que na tela vira
    "nova categoria" já preenchida com o nome sugerido."""
    por_nome = {
        c.nome.casefold(): c.pk
        for c in CategoriaItem.objects.filter(empresa=importacao.empresa, ativo=True)
    }
    return [
        (item, sugerida, por_nome.get(sugerida.casefold()))
        for item, sugerida in itens_fora_do_catalogo(importacao)
    ]


def _categoria(empresa, escolha: Escolha, criadas: dict):
    if escolha.categoria_id:
        return CategoriaItem.objects.filter(
            empresa=empresa, ativo=True, pk=escolha.categoria_id
        ).first()
    nome = " ".join(escolha.categoria_nova.split())[:100]
    if not nome:
        return None
    chave = nome.casefold()
    if chave not in criadas:
        existente = CategoriaItem.objects.filter(empresa=empresa, nome__iexact=nome).first()
        criadas[chave] = existente or CategoriaItem.objects.create(empresa=empresa, nome=nome)
    return criadas[chave]


def _criar_no_catalogo(empresa, item, categoria):
    unidade = item.unidade_medida if item.unidade_medida in UNIDADES_CATALOGO else "un"
    catalogo = ItemCatalogo.objects.create(
        empresa=empresa,
        categoria=categoria,
        nome=item.nome,
        descricao_padrao=item.descricao,
        unidade_medida=unidade,
        valor_unitario_padrao=item.valor_unitario,
        observacoes="Cadastrado a partir de sugestão da IA num memorial descritivo.",
    )
    # update() e não save(): o vínculo não muda subtotal nem código da linha,
    # e o save() do item refaria a validação inteira à toa.
    ItemOrcamento.objects.filter(pk=item.pk).update(item_catalogo=catalogo)


def _marcar_salvos(importacao: ImportacaoMemorial, salvos: set[int]):
    resultado = dict(importacao.resultado or {})
    for sugestao in resultado.get("itens") or []:
        if sugestao.get("item_id") in salvos:
            sugestao["no_catalogo"] = True
            sugestao["salvo_no_catalogo"] = True
    importacao.resultado = resultado
    importacao.save(update_fields=["resultado", "atualizado_em"])


def salvar_no_catalogo(importacao: ImportacaoMemorial, escolhas: list[Escolha]) -> int:
    """Cria os itens de catálogo e vincula as linhas do orçamento a eles.
    Atômico. Devolve quantos itens foram para o catálogo."""
    validos = {item.pk: item for item, _ in itens_fora_do_catalogo(importacao)}
    criadas: dict = {}
    salvos: set[int] = set()
    with transaction.atomic():
        for escolha in escolhas:
            item = validos.get(escolha.item_id)
            categoria = item and _categoria(importacao.empresa, escolha, criadas)
            if item is None or categoria is None:
                continue
            _criar_no_catalogo(importacao.empresa, item, categoria)
            salvos.add(item.pk)
        if salvos:
            _marcar_salvos(importacao, salvos)
    return len(salvos)
