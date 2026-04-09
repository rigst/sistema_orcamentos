from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import require_capability
from core.query import paginate_queryset
from .forms import ClienteForm
from .models import Cliente


@require_capability("pode_visualizar_clientes")
def cliente_lista(request):
    busca = request.GET.get("q", "").strip()
    ativo = request.GET.get("ativo", "").strip()
    ordenar = request.GET.get("sort", "nome")

    clientes = Cliente.objects.all()

    if busca:
        clientes = clientes.filter(
            Q(nome_razao_social__icontains=busca)
            | Q(nome_fantasia__icontains=busca)
            | Q(cpf_cnpj__icontains=busca)
            | Q(email__icontains=busca)
        )

    if ativo == "ativos":
        clientes = clientes.filter(ativo=True)
    elif ativo == "inativos":
        clientes = clientes.filter(ativo=False)

    ordenacoes = {
        "nome": "nome_razao_social",
        "tipo": "tipo_pessoa",
        "cidade": "cidade",
        "recentes": "-atualizado_em",
    }
    clientes = clientes.order_by(ordenacoes.get(ordenar, "nome_razao_social"))
    page_obj = paginate_queryset(request, clientes, per_page=12)

    context = {
        "clientes": page_obj,
        "page_obj": page_obj,
        "busca": busca,
        "ativo": ativo,
        "sort": ordenar,
    }
    return render(request, "clientes/lista.html", context)


@require_capability("pode_gerenciar_clientes")
def cliente_criar(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("clientes:lista")
    else:
        form = ClienteForm()

    return render(request, "clientes/form.html", {"form": form, "titulo": "Novo cliente"})


@require_capability("pode_gerenciar_clientes")
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
