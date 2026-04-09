from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ConfiguracaoEmpresaForm
from .models import ConfiguracaoEmpresa


@login_required
def configuracao_lista(request):
    configuracoes = ConfiguracaoEmpresa.objects.all()
    return render(
        request,
        "relatorios/configuracao_lista.html",
        {"configuracoes": configuracoes},
    )


@login_required
def configuracao_criar(request):
    if request.method == "POST":
        form = ConfiguracaoEmpresaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("relatorios:configuracao_lista")
    else:
        form = ConfiguracaoEmpresaForm()

    return render(
        request,
        "relatorios/configuracao_form.html",
        {"form": form, "titulo": "Nova configuração da empresa"},
    )


@login_required
def configuracao_editar(request, pk):
    configuracao = get_object_or_404(ConfiguracaoEmpresa, pk=pk)

    if request.method == "POST":
        form = ConfiguracaoEmpresaForm(request.POST, request.FILES, instance=configuracao)
        if form.is_valid():
            form.save()
            return redirect("relatorios:configuracao_lista")
    else:
        form = ConfiguracaoEmpresaForm(instance=configuracao)

    return render(
        request,
        "relatorios/configuracao_form.html",
        {"form": form, "titulo": "Editar configuração da empresa", "configuracao": configuracao},
    )
