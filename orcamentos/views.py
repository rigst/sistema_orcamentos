from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from catalogo.models import ItemCatalogo
from .forms import OrcamentoForm
from .models import ItemOrcamento, Orcamento


STATUS_PERMITIDOS = {
    "rascunho",
    "em_elaboracao",
    "enviado",
    "aprovado",
    "rejeitado",
    "cancelado",
}


@login_required
def orcamento_lista(request):
    busca = request.GET.get("q", "").strip()

    orcamentos = Orcamento.objects.select_related("cliente").all()

    if busca:
        orcamentos = orcamentos.filter(
            Q(numero__icontains=busca)
            | Q(cliente__nome_razao_social__icontains=busca)
            | Q(titulo__icontains=busca)
        )

    context = {
        "orcamentos": orcamentos,
        "busca": busca,
    }
    return render(request, "orcamentos/lista.html", context)


@login_required
def orcamento_criar(request):
    if request.method == "POST":
        form = OrcamentoForm(request.POST)
        if form.is_valid():
            orcamento = form.save(commit=False)
            orcamento.criado_por = request.user
            orcamento.atualizado_por = request.user
            orcamento.save()
            messages.success(request, "Orçamento criado com sucesso.")
            return redirect("orcamentos:editar", pk=orcamento.pk)
    else:
        form = OrcamentoForm()

    return render(
        request,
        "orcamentos/form.html",
        {"form": form, "titulo": "Novo orçamento"},
    )


@login_required
def orcamento_editar(request, pk):
    orcamento = get_object_or_404(Orcamento, pk=pk)

    if request.method == "POST":
        form = OrcamentoForm(request.POST, instance=orcamento)
        if form.is_valid():
            orcamento = form.save(commit=False)
            orcamento.atualizado_por = request.user
            orcamento.save()
            orcamento.recalcular_totais()
            messages.success(request, "Orçamento atualizado com sucesso.")
            return redirect("orcamentos:editar", pk=orcamento.pk)
    else:
        form = OrcamentoForm(instance=orcamento)

    itens = orcamento.itens.all()
    item_catalogo_choices = ItemCatalogo.objects.filter(ativo=True).select_related("categoria").order_by("nome")

    context = {
        "form": form,
        "titulo": "Editar orçamento",
        "orcamento": orcamento,
        "itens": itens,
        "item_catalogo_choices": item_catalogo_choices,
    }
    return render(request, "orcamentos/form.html", context)


@login_required
def orcamento_excluir(request, pk):
    orcamento = get_object_or_404(Orcamento, pk=pk)

    if request.method == "POST":
        orcamento.delete()
        messages.success(request, "Orçamento excluído com sucesso.")
        return redirect("orcamentos:lista")

    return render(request, "orcamentos/excluir.html", {"orcamento": orcamento})


@login_required
def orcamento_alterar_status(request, pk, novo_status):
    orcamento = get_object_or_404(Orcamento, pk=pk)

    if novo_status in STATUS_PERMITIDOS:
        orcamento.status = novo_status
        orcamento.atualizado_por = request.user
        orcamento.save(update_fields=["status", "atualizado_por", "atualizado_em"])
        messages.success(request, f"Status alterado para {orcamento.get_status_display()}.")

    return redirect("orcamentos:lista")


@login_required
def item_orcamento_criar(request, orcamento_pk):
    orcamento = get_object_or_404(Orcamento, pk=orcamento_pk)

    if request.method == "POST":
        item_catalogo_id = request.POST.get("item_catalogo")
        item_catalogo = None
        if item_catalogo_id:
            item_catalogo = ItemCatalogo.objects.filter(pk=item_catalogo_id).first()

        codigo_item = request.POST.get("codigo_item", "").strip()
        nome = request.POST.get("nome", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        unidade_medida = request.POST.get("unidade_medida", "un")
        observacoes = request.POST.get("observacoes", "").strip()

        ordem = int(request.POST.get("ordem") or 1)
        quantidade = Decimal(request.POST.get("quantidade") or "1")
        valor_unitario = Decimal(request.POST.get("valor_unitario") or "0")
        desconto_valor = Decimal(request.POST.get("desconto_valor") or "0")
        desconto_percentual = Decimal(request.POST.get("desconto_percentual") or "0")
        acrescimo_valor = Decimal(request.POST.get("acrescimo_valor") or "0")
        acrescimo_percentual = Decimal(request.POST.get("acrescimo_percentual") or "0")

        if item_catalogo:
            if not codigo_item:
                codigo_item = item_catalogo.codigo
            if not nome:
                nome = item_catalogo.nome
            if not descricao:
                descricao = item_catalogo.descricao_padrao
            if not unidade_medida:
                unidade_medida = item_catalogo.unidade_medida
            if valor_unitario == 0:
                valor_unitario = item_catalogo.valor_unitario_padrao

        item = ItemOrcamento.objects.create(
            orcamento=orcamento,
            item_catalogo=item_catalogo,
            ordem=ordem,
            codigo_item=codigo_item,
            nome=nome,
            descricao=descricao,
            unidade_medida=unidade_medida,
            quantidade=quantidade,
            valor_unitario=valor_unitario,
            desconto_valor=desconto_valor,
            desconto_percentual=desconto_percentual,
            acrescimo_valor=acrescimo_valor,
            acrescimo_percentual=acrescimo_percentual,
            observacoes=observacoes,
        )
        orcamento.recalcular_totais()
        messages.success(request, f"Item '{item.nome}' adicionado.")
        return redirect("orcamentos:editar", pk=orcamento.pk)

    return redirect("orcamentos:editar", pk=orcamento.pk)


@login_required
def item_orcamento_editar(request, orcamento_pk, item_pk):
    orcamento = get_object_or_404(Orcamento, pk=orcamento_pk)
    item = get_object_or_404(ItemOrcamento, pk=item_pk, orcamento=orcamento)

    if request.method == "POST":
        item_catalogo_id = request.POST.get("item_catalogo")
        item_catalogo = None
        if item_catalogo_id:
            item_catalogo = ItemCatalogo.objects.filter(pk=item_catalogo_id).first()

        item.item_catalogo = item_catalogo
        item.ordem = int(request.POST.get("ordem") or 1)
        item.codigo_item = request.POST.get("codigo_item", "").strip()
        item.nome = request.POST.get("nome", "").strip()
        item.descricao = request.POST.get("descricao", "").strip()
        item.unidade_medida = request.POST.get("unidade_medida", "un")
        item.quantidade = Decimal(request.POST.get("quantidade") or "1")
        item.valor_unitario = Decimal(request.POST.get("valor_unitario") or "0")
        item.desconto_valor = Decimal(request.POST.get("desconto_valor") or "0")
        item.desconto_percentual = Decimal(request.POST.get("desconto_percentual") or "0")
        item.acrescimo_valor = Decimal(request.POST.get("acrescimo_valor") or "0")
        item.acrescimo_percentual = Decimal(request.POST.get("acrescimo_percentual") or "0")
        item.observacoes = request.POST.get("observacoes", "").strip()

        if item_catalogo:
            if not item.codigo_item:
                item.codigo_item = item_catalogo.codigo
            if not item.nome:
                item.nome = item_catalogo.nome
            if not item.descricao:
                item.descricao = item_catalogo.descricao_padrao

        item.save()
        orcamento.recalcular_totais()
        messages.success(request, f"Item '{item.nome}' atualizado.")
        return redirect("orcamentos:editar", pk=orcamento.pk)

    item_catalogo_choices = ItemCatalogo.objects.filter(ativo=True).order_by("nome")
    return render(
        request,
        "orcamentos/item_inline_form.html",
        {
            "orcamento": orcamento,
            "item": item,
            "item_catalogo_choices": item_catalogo_choices,
            "titulo": f"Editar item de {orcamento.numero}",
        },
    )


@login_required
def item_orcamento_excluir(request, orcamento_pk, item_pk):
    orcamento = get_object_or_404(Orcamento, pk=orcamento_pk)
    item = get_object_or_404(ItemOrcamento, pk=item_pk, orcamento=orcamento)

    if request.method == "POST":
        nome_item = item.nome
        item.delete()
        orcamento.recalcular_totais()
        messages.success(request, f"Item '{nome_item}' excluído.")
        return redirect("orcamentos:editar", pk=orcamento.pk)

    return render(
        request,
        "orcamentos/item_excluir.html",
        {
            "orcamento": orcamento,
            "item": item,
        },
    )
