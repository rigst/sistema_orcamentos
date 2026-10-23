from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from catalogo.models import CategoriaItem
from core.permissions import require_capability
from core.tenancy import obter_grupo_empresa_ou_erro, queryset_da_empresa
from orcamentos.models import Orcamento
from orcamentos.views import exigir_orcamento_editavel, orcamento_bloqueado_para_edicao

from . import services
from .catalogo import opcoes_para_catalogar
from .extracao import MemorialInvalido, ler_memorial
from .forms import ImportarMemorialForm, NovoOrcamentoMemorialForm
from .models import ImportacaoMemorial

ROTA_STATUS = "memoriais:status"


def _orcamento_da_empresa(request, orcamento_pk):
    return get_object_or_404(
        queryset_da_empresa(Orcamento.objects.select_related("cliente"), request.user),
        pk=orcamento_pk,
    )


def _ler_ou_anotar(form):
    """O memorial pronto, ou None com o erro já no formulário."""
    try:
        return ler_memorial(form.cleaned_data.get("arquivo"), form.cleaned_data.get("texto") or "")
    except MemorialInvalido as exc:
        form.add_error("arquivo", str(exc))
        return None


def _registrar_e_disparar(request, form, orcamento, empresa, memorial):
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


def _cota(request, empresa):
    limite = services.limite_diario(request.user)
    return limite, max(limite - services.usadas_hoje(empresa), 0)


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
        return redirect(ROTA_STATUS, orcamento_pk=orcamento.pk, pk=em_andamento.pk)

    limite, restantes = _cota(request, empresa)
    form = ImportarMemorialForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        if restantes <= 0:
            form.add_error(None, "O limite diário de importações com IA foi atingido.")
        elif (memorial := _ler_ou_anotar(form)) is not None:
            importacao = _registrar_e_disparar(request, form, orcamento, empresa, memorial)
            return redirect(ROTA_STATUS, orcamento_pk=orcamento.pk, pk=importacao.pk)

    return render(
        request,
        "memoriais/importar.html",
        {
            "orcamento": orcamento,
            "form": form,
            "restantes": restantes,
            "limite": limite,
            "catalogo_vazio": not services.catalogo_da_empresa(empresa).exists(),
            "anteriores": orcamento.importacoes_memorial.all()[:5],
        },
    )


@require_capability("pode_gerenciar_orcamentos")
@require_POST
def novo_com_memorial(request):
    """Cria o orçamento e já dispara a leitura do memorial. O orçamento nasce
    com título genérico e, se o usuário não escolheu cliente, sem cliente: a
    IA preenche os dois a partir do edital."""
    if not settings.ANTHROPIC_API_KEY:
        messages.error(request, "A importação com IA não está configurada neste servidor.")
        return redirect("orcamentos:criar")
    empresa = obter_grupo_empresa_ou_erro(request.user)
    form = NovoOrcamentoMemorialForm(request.POST, request.FILES, user=request.user)
    _limite, restantes = _cota(request, empresa)

    if form.is_valid():
        if restantes <= 0:
            form.add_error(None, "O limite diário de importações com IA foi atingido.")
        elif (memorial := _ler_ou_anotar(form)) is not None:
            with transaction.atomic():
                orcamento = Orcamento.objects.create(
                    empresa=empresa,
                    cliente=form.cleaned_data.get("cliente"),
                    titulo=Orcamento.TITULO_GENERICO,
                    criado_por=request.user,
                    atualizado_por=request.user,
                )
                importacao = _registrar_e_disparar(request, form, orcamento, empresa, memorial)
            return redirect(ROTA_STATUS, orcamento_pk=orcamento.pk, pk=importacao.pk)

    from orcamentos.views import renderizar_inicio_rapido

    return renderizar_inicio_rapido(request, memorial_form=form, status=400)


@require_capability("pode_visualizar_orcamentos")
@require_http_methods(["GET"])
def status(request, orcamento_pk, pk):
    orcamento = _orcamento_da_empresa(request, orcamento_pk)
    importacao = get_object_or_404(ImportacaoMemorial, pk=pk, orcamento=orcamento)
    services.expirar_travadas(orcamento)
    importacao.refresh_from_db()
    orcamento.refresh_from_db()

    if importacao.status == "concluida" and request.GET.get("seguir") == "1":
        messages.success(
            request,
            f"Memorial importado: {importacao.itens_criados} itens adicionados. "
            "Revise quantidades e valores direto na tabela.",
        )
        return redirect("orcamentos:editar", pk=orcamento.pk)

    resultado = importacao.resultado or {}
    itens = resultado.get("itens") or []
    pode_catalogar = (
        request.user.pode_gerenciar_catalogo
        and importacao.status == "concluida"
        and not orcamento_bloqueado_para_edicao(orcamento)
    )
    contexto = {
        "orcamento": orcamento,
        "importacao": importacao,
        "itens_sugeridos": itens,
        "fora_catalogo": [
            i for i in itens if i.get("situacao") == "adicionado" and not i.get("no_catalogo")
        ],
        "salvos_no_catalogo": [i for i in itens if i.get("salvo_no_catalogo")],
        "ignorados": [i for i in itens if i.get("situacao") == "ignorado"],
        "pendencias": resultado.get("pendencias") or [],
        "cliente_ia": resultado.get("cliente") or {},
        "pode_catalogar": pode_catalogar,
        "para_catalogar": opcoes_para_catalogar(importacao) if pode_catalogar else [],
        "categorias": CategoriaItem.objects.filter(empresa=importacao.empresa, ativo=True).order_by(
            "nome"
        ),
    }
    template = (
        "memoriais/partials/status.html"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest"
        else "memoriais/status.html"
    )
    return render(request, template, contexto)
