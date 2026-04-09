from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ClienteForm
from .models import Cliente


@login_required
def cliente_lista(request):
    busca = request.GET.get("q", "").strip()

    clientes = Cliente.objects.all()

    if busca:
        clientes = clientes.filter(
            Q(nome_razao_social__icontains=busca)
            | Q(nome_fantasia__icontains=busca)
            | Q(cpf_cnpj__icontains=busca)
            | Q(email__icontains=busca)
        )

    context = {
        "clientes": clientes,
        "busca": busca,
    }
    return render(request, "clientes/lista.html", context)


@login_required
def cliente_criar(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("clientes:lista")
    else:
        form = ClienteForm()

    return render(request, "clientes/form.html", {"form": form, "titulo": "Novo cliente"})


@login_required
def cliente_editar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect("clientes:lista")
    else:
        form = ClienteForm(instance=cliente)

    return render(
        request,
        "clientes/form.html",
        {"form": form, "titulo": "Editar cliente", "cliente": cliente},
    )

# Create your views here.
