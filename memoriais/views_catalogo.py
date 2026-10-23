"""Tela que leva os itens novos sugeridos pela IA para o catálogo."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.permissions import require_capability
from orcamentos.views import exigir_orcamento_editavel

from .catalogo import Escolha, salvar_no_catalogo
from .models import ImportacaoMemorial
from .views import ROTA_STATUS, _orcamento_da_empresa


def _escolhas_do_post(post):
    """Lê `item_<id>` (checkbox), `categoria_<id>` (id existente ou "nova")
    e `categoria_nova_<id>` (texto)."""
    escolhas = []
    for chave in post:
        if not chave.startswith("item_"):
            continue
        try:
            item_id = int(chave.removeprefix("item_"))
        except ValueError:
            continue
        categoria = (post.get(f"categoria_{item_id}") or "").strip()
        categoria_id = int(categoria) if categoria.isdigit() else None
        nova = "" if categoria_id else (post.get(f"categoria_nova_{item_id}") or "")
        escolhas.append(Escolha(item_id=item_id, categoria_id=categoria_id, categoria_nova=nova))
    return escolhas


@require_capability("pode_gerenciar_catalogo")
@require_POST
def salvar_catalogo(request, orcamento_pk, pk):
    orcamento = _orcamento_da_empresa(request, orcamento_pk)
    exigir_orcamento_editavel(request.user, orcamento)
    importacao = get_object_or_404(
        ImportacaoMemorial, pk=pk, orcamento=orcamento, status="concluida"
    )
    escolhas = _escolhas_do_post(request.POST)
    if not escolhas:
        messages.error(request, "Marque ao menos um item para levar ao catálogo.")
        return redirect(ROTA_STATUS, orcamento_pk=orcamento.pk, pk=importacao.pk)

    salvos = salvar_no_catalogo(importacao, escolhas)
    if salvos:
        messages.success(
            request,
            f"{salvos} item{'s' if salvos != 1 else ''} salvo{'s' if salvos != 1 else ''} "
            "no catálogo com o valor que está no orçamento.",
        )
    else:
        messages.error(request, "Nenhum item foi salvo. Escolha a categoria de cada item marcado.")
    return redirect(ROTA_STATUS, orcamento_pk=orcamento.pk, pk=importacao.pk)
