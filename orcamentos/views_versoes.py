"""Salvamento automático do orçamento e desfazer/refazer.

Tudo que altera o orçamento pelo editor registra uma versão
(`versoes.registrar_versao`). Estas views cuidam do que é só delas: o
salvamento automático dos dados gerais e a navegação entre versões.
"""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from core.permissions import require_capability
from core.tenancy import queryset_da_empresa

from .forms import OrcamentoForm
from .models import NAO_REGISTRADO, Orcamento
from .versoes import desfazer, estado_historico, refazer, registrar_versao, retrato


def _orcamento_editavel(request, pk):
    from .views import exigir_orcamento_editavel

    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=pk)
    exigir_orcamento_editavel(request.user, orcamento)
    return orcamento


def _concorrencia(orcamento):
    return orcamento.atualizado_em.isoformat(timespec="microseconds")


def resposta_estado(request, orcamento, **extra):
    """Totais, versão de concorrência e botões do histórico, depois de mudar."""
    orcamento.refresh_from_db()
    return JsonResponse(
        {
            "concorrencia": _concorrencia(orcamento),
            "historico": estado_historico(orcamento),
            "totais_html": render_to_string(
                "orcamentos/partials/totais_card.html",
                {
                    "orcamento": orcamento,
                    "subtotais_categoria": orcamento.subtotais_por_categoria(NAO_REGISTRADO),
                },
                request=request,
            ),
            **extra,
        }
    )


@require_capability("pode_gerenciar_orcamentos")
@require_POST
def orcamento_autosalvar(request, pk):
    """Recebe o formulário principal inteiro, como o botão Salvar enviaria."""
    orcamento = _orcamento_editavel(request, pk)
    # O form valida e escreve no próprio objeto: o "antes" sai já, do banco.
    antes = retrato(orcamento)["orcamento"]
    form = OrcamentoForm(request.POST, instance=orcamento, user=request.user)
    if not form.is_valid():
        erros = {campo: [str(e) for e in lista] for campo, lista in form.errors.items()}
        return JsonResponse({"erros": erros}, status=400)
    # `has_changed` compara texto do POST com o valor do banco ("0,00" × 0)
    # e acusa mudança que não houve: compara o retrato antes e depois.
    orcamento = form.save(commit=False)
    depois = retrato(orcamento)["orcamento"]
    alterados = [campo for campo in depois if depois[campo] != antes[campo]]
    if alterados:
        orcamento.atualizado_por = request.user
        orcamento.save()
        orcamento.recalcular_totais()
        registrar_versao(orcamento, request.user, _descrever(form, alterados))
    return resposta_estado(request, orcamento, salvo=bool(alterados))


def _descrever(form, alterados):
    rotulos = []
    for campo in alterados:
        nome = campo.removesuffix("_id")
        rotulo = form.fields[nome].label if nome in form.fields else None
        rotulos.append(str(rotulo or nome.replace("_", " ")).lower())
    extra = f" e mais {len(rotulos) - 2}" if len(rotulos) > 2 else ""
    return "Editou " + ", ".join(rotulos[:2]) + extra


@require_capability("pode_gerenciar_orcamentos")
@require_POST
def orcamento_desfazer(request, pk):
    orcamento = _orcamento_editavel(request, pk)
    versao = desfazer(orcamento)
    if versao is None:
        return JsonResponse({"erro": "Nada para desfazer."}, status=409)
    return resposta_estado(request, orcamento, mensagem=f"Desfeito: {versao.descricao}")


@require_capability("pode_gerenciar_orcamentos")
@require_POST
def orcamento_refazer(request, pk):
    orcamento = _orcamento_editavel(request, pk)
    versao = refazer(orcamento)
    if versao is None:
        return JsonResponse({"erro": "Nada para refazer."}, status=409)
    return resposta_estado(request, orcamento, mensagem=f"Refeito: {versao.descricao}")
