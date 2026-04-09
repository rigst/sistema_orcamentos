from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoriaItemForm, ItemCatalogoForm
from .models import CategoriaItem, ItemCatalogo


@login_required
def categoria_lista(request):
    busca = request.GET.get("q", "").strip()

    categorias = CategoriaItem.objects.all()

    if busca:
        categorias = categorias.filter(nome__icontains=busca)

    context = {
        "categorias": categorias,
        "busca": busca,
    }
    return render(request, "catalogo/categoria_lista.html", context)


@login_required
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


@login_required
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


@login_required
def item_lista(request):
    busca = request.GET.get("q", "").strip()

    itens = ItemCatalogo.objects.select_related("categoria").all()

    if busca:
        itens = itens.filter(
            Q(codigo__icontains=busca)
            | Q(nome__icontains=busca)
            | Q(descricao_padrao__icontains=busca)
            | Q(categoria__nome__icontains=busca)
        )

    context = {
        "itens": itens,
        "busca": busca,
    }
    return render(request, "catalogo/item_lista.html", context)


@login_required
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


@login_required
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

# Create your views here.
