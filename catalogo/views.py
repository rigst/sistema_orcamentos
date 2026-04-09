from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import require_capability
from core.query import paginate_queryset
from .forms import CategoriaItemForm, ItemCatalogoForm
from .models import CategoriaItem, ItemCatalogo


@require_capability("pode_visualizar_catalogo")
def categoria_lista(request):
    busca = request.GET.get("q", "").strip()
    ativo = request.GET.get("ativo", "ativas").strip()
    ordenar = request.GET.get("sort", "nome")

    categorias = CategoriaItem.objects.all()

    if busca:
        categorias = categorias.filter(nome__icontains=busca)

    if ativo != "inativas":
        categorias = categorias.filter(ativo=True)
    else:
        categorias = categorias.filter(ativo=False)

    ordenacoes = {
        "nome": "nome",
        "recentes": "-atualizado_em",
    }
    categorias = categorias.order_by(ordenacoes.get(ordenar, "nome"))
    page_obj = paginate_queryset(request, categorias, per_page=12)

    context = {
        "categorias": page_obj,
        "page_obj": page_obj,
        "busca": busca,
        "ativo": ativo,
        "sort": ordenar,
    }
    return render(request, "catalogo/categoria_lista.html", context)


@require_capability("pode_gerenciar_catalogo")
def categoria_criar(request):
    if request.method == "POST":
        form = CategoriaItemForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("catalogo:categoria_lista")
    else:
        form = CategoriaItemForm()

    return render(
        request,
        "catalogo/categoria_form.html",
        {"form": form, "titulo": "Nova categoria"},
    )


@require_capability("pode_visualizar_catalogo")
def categoria_visualizar(request, pk):
    categoria = get_object_or_404(CategoriaItem, pk=pk)
    form = CategoriaItemForm(instance=categoria)
    return render(
        request,
        "catalogo/categoria_form.html",
        {"form": form, "titulo": "Categoria", "categoria": categoria, "somente_leitura": True},
    )


@require_capability("pode_gerenciar_catalogo")
def categoria_editar(request, pk):
    categoria = get_object_or_404(CategoriaItem, pk=pk)

    if request.method == "POST":
        form = CategoriaItemForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            return redirect("catalogo:categoria_lista")
    else:
        form = CategoriaItemForm(instance=categoria)

    return render(
        request,
        "catalogo/categoria_form.html",
        {"form": form, "titulo": "Editar categoria", "categoria": categoria},
    )


@require_capability("pode_gerenciar_catalogo")
def categoria_excluir(request, pk):
    categoria = get_object_or_404(CategoriaItem, pk=pk)
    acao = "reativar" if not categoria.ativo else "inativar"

    if request.method == "POST":
        categoria.ativo = not categoria.ativo
        categoria.save(update_fields=["ativo", "atualizado_em"])
        if categoria.ativo:
            messages.success(request, "Categoria reativada com sucesso.")
        else:
            messages.success(request, "Categoria inativada com sucesso.")
        return redirect("catalogo:categoria_lista")

    return render(
        request,
        "catalogo/categoria_excluir.html",
        {"categoria": categoria, "acao": acao},
    )


@require_capability("pode_visualizar_catalogo")
def item_lista(request):
    busca = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    ativo = request.GET.get("ativo", "ativos").strip()
    ordenar = request.GET.get("sort", "nome")

    itens = ItemCatalogo.objects.select_related("categoria").all()

    if busca:
        itens = itens.filter(
            Q(codigo__icontains=busca)
            | Q(nome__icontains=busca)
            | Q(descricao_padrao__icontains=busca)
            | Q(categoria__nome__icontains=busca)
        )

    if categoria_id:
        itens = itens.filter(categoria_id=categoria_id)

    if ativo != "inativos":
        itens = itens.filter(ativo=True)
    else:
        itens = itens.filter(ativo=False)

    ordenacoes = {
        "nome": "nome",
        "codigo": "codigo",
        "categoria": "categoria__nome",
        "preco_maior": "-valor_unitario_padrao",
        "preco_menor": "valor_unitario_padrao",
        "recentes": "-atualizado_em",
    }
    itens = itens.order_by(ordenacoes.get(ordenar, "nome"))
    page_obj = paginate_queryset(request, itens, per_page=12)

    context = {
        "itens": page_obj,
        "page_obj": page_obj,
        "busca": busca,
        "categoria": categoria_id,
        "ativo": ativo,
        "sort": ordenar,
        "categorias": CategoriaItem.objects.filter(ativo=True).order_by("nome"),
    }
    return render(request, "catalogo/item_lista.html", context)


@require_capability("pode_gerenciar_catalogo")
def item_criar(request):
    if request.method == "POST":
        form = ItemCatalogoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("catalogo:item_lista")
    else:
        form = ItemCatalogoForm()

    return render(
        request,
        "catalogo/item_form.html",
        {"form": form, "titulo": "Novo item"},
    )


@require_capability("pode_visualizar_catalogo")
def item_visualizar(request, pk):
    item = get_object_or_404(ItemCatalogo, pk=pk)
    form = ItemCatalogoForm(instance=item)
    return render(
        request,
        "catalogo/item_form.html",
        {"form": form, "titulo": "Item do catálogo", "item": item, "somente_leitura": True},
    )


@require_capability("pode_gerenciar_catalogo")
def item_editar(request, pk):
    item = get_object_or_404(ItemCatalogo, pk=pk)

    if request.method == "POST":
        form = ItemCatalogoForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect("catalogo:item_lista")
    else:
        form = ItemCatalogoForm(instance=item)

    return render(
        request,
        "catalogo/item_form.html",
        {"form": form, "titulo": "Editar item", "item": item},
    )


@require_capability("pode_gerenciar_catalogo")
def item_excluir(request, pk):
    item = get_object_or_404(ItemCatalogo, pk=pk)
    acao = "reativar" if not item.ativo else "inativar"

    if request.method == "POST":
        item.ativo = not item.ativo
        item.save(update_fields=["ativo", "atualizado_em"])
        if item.ativo:
            messages.success(request, "Item reativado com sucesso.")
        else:
            messages.success(request, "Item inativado com sucesso.")
        return redirect("catalogo:item_lista")

    return render(
        request,
        "catalogo/item_excluir.html",
        {"item": item, "acao": acao},
    )
