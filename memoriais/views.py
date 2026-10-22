from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.permissions import require_capability
from core.tenancy import obter_grupo_empresa_ou_erro, queryset_da_empresa
from orcamentos.models import Orcamento
from orcamentos.views import exigir_orcamento_editavel

from . import services
from .extracao import MemorialInvalido, ler_memorial
from .forms import ImportarMemorialForm
from .models import ImportacaoMemorial


def _orcamento_da_empresa(request, orcamento_pk):
    return get_object_or_404(
        queryset_da_empresa(Orcamento.objects.select_related("cliente"), request.user),
        pk=orcamento_pk,
    )


def _iniciar_importacao(request, form, orcamento, empresa):
    """Lê o arquivo, grava o registro e agenda a IA. Devolve None quando o
    arquivo é recusado, com o erro já anotado no formulário."""
    try:
        memorial = ler_memorial(
            form.cleaned_data.get("arquivo"), form.cleaned_data.get("texto") or ""
        )
    except MemorialInvalido as exc:
        form.add_error("arquivo", str(exc))
        return None
    importacao = ImportacaoMemorial.objects.create(
        orcamento=orcamento,
        empresa=empresa,
        criado_por=request.user,
        arquivo_nome=memorial.nome[:255],
        instrucoes=form.cleaned_data.get("instrucoes") or "",
        incluir_fora_catalogo=form.cleaned_data["incluir_fora_catalogo"],
        preencher_evento=form.cleaned_data["preencher_evento"],
    )
    services.disparar(importacao, memorial)
    return importacao


@require_capability("pode_gerenciar_orcamentos")
@require_http_methods(["GET", "POST"])
def importar(request, orcamento_pk):
    orcamento = _orcamento_da_empresa(request, orcamento_pk)
    exigir_orcamento_editavel(request.user, orcamento)
    if not settings.ANTHROPIC_API_KEY:
        messages.error(request, "A importação com IA não está configurada neste servidor.")
        return redirect("orcamentos:editar", pk=orcamento.pk)
    empresa = obter_grupo_empresa_ou_erro(request.user)
    services.expirar_travadas(orcamento)

    em_andamento = orcamento.importacoes_memorial.filter(
        status__in=ImportacaoMemorial.EM_ANDAMENTO
    ).first()
    if em_andamento is not None:
        return redirect("memoriais:status", orcamento_pk=orcamento.pk, pk=em_andamento.pk)

    limite = services.limite_diario(request.user)
    restantes = max(limite - services.usadas_hoje(empresa), 0)
    catalogo_vazio = not services.catalogo_da_empresa(empresa).exists()
    form = ImportarMemorialForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        if restantes <= 0:
            form.add_error(None, "O limite diário de importações com IA foi atingido.")
        else:
            importacao = _iniciar_importacao(request, form, orcamento, empresa)
            if importacao is not None:
                return redirect("memoriais:status", orcamento_pk=orcamento.pk, pk=importacao.pk)

    return render(
        request,
        "memoriais/importar.html",
        {
            "orcamento": orcamento,
            "form": form,
            "restantes": restantes,
            "limite": limite,
            "catalogo_vazio": catalogo_vazio,
            "anteriores": orcamento.importacoes_memorial.all()[:5],
        },
    )


@require_capability("pode_visualizar_orcamentos")
@require_http_methods(["GET"])
def status(request, orcamento_pk, pk):
    orcamento = _orcamento_da_empresa(request, orcamento_pk)
    importacao = get_object_or_404(ImportacaoMemorial, pk=pk, orcamento=orcamento)
    services.expirar_travadas(orcamento)
    importacao.refresh_from_db()

    if importacao.status == "concluida" and request.GET.get("seguir") == "1":
        messages.success(
            request,
            f"Memorial importado: {importacao.itens_criados} itens adicionados. "
            "Revise quantidades e valores antes de enviar.",
        )
        return redirect("orcamentos:editar", pk=orcamento.pk)

    resultado = importacao.resultado or {}
    itens = resultado.get("itens") or []
    contexto = {
        "orcamento": orcamento,
        "importacao": importacao,
        "itens_sugeridos": itens,
        "fora_catalogo": [
            i for i in itens if i.get("situacao") == "adicionado" and not i.get("no_catalogo")
        ],
        "ignorados": [i for i in itens if i.get("situacao") == "ignorado"],
        "pendencias": resultado.get("pendencias") or [],
    }
    template = (
        "memoriais/partials/status.html"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest"
        else "memoriais/status.html"
    )
    return render(request, template, contexto)
