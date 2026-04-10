from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from urllib.parse import urlencode

from core.permissions import require_capability
from core.query import paginate_queryset
from core.tenancy import obter_grupo_empresa_ou_erro, queryset_da_empresa
from catalogo.models import CategoriaItem
from .forms import ItemOrcamentoForm, OrcamentoForm
from .models import ItemOrcamento, Orcamento


STATUS_PERMITIDOS = {
    "rascunho",
    "em_elaboracao",
    "enviado",
    "aprovado",
    "rejeitado",
    "cancelado",
}

ITEM_SORT_MAP = {
    "ordem": ("ordem", "id"),
    "nome": ("nome", "id"),
    "categoria": ("item_catalogo__categoria__nome", "nome", "id"),
    "preco_maior": ("-valor_unitario", "nome", "id"),
    "preco_menor": ("valor_unitario", "nome", "id"),
    "subtotal_maior": ("-subtotal", "nome", "id"),
    "subtotal_menor": ("subtotal", "nome", "id"),
}


def normalizar_ordens_itens(orcamento):
    itens = list(orcamento.itens.all().order_by("ordem", "id"))
    for ordem, item in enumerate(itens, start=1):
        if item.ordem != ordem:
            ItemOrcamento.objects.filter(pk=item.pk).update(ordem=ordem)


def obter_item_em_edicao(request, orcamento, modo_somente_leitura):
    item_edit_pk = request.GET.get("item_edit")
    if not item_edit_pk or modo_somente_leitura:
        return None, None

    item = get_object_or_404(ItemOrcamento, pk=item_edit_pk, orcamento=orcamento)
    return item, ItemOrcamentoForm(instance=item, user=request.user)


def obter_estado_itens(request, orcamento):
    origem = request.POST if request.method == "POST" else request.GET
    busca = (origem.get("item_q") or "").strip()
    categoria = (origem.get("item_categoria") or "").strip()
    ordenacao = (origem.get("item_sort") or "ordem").strip()

    itens = orcamento.itens.select_related("item_catalogo__categoria")
    if busca:
        itens = itens.filter(
            Q(nome__icontains=busca)
            | Q(codigo_item__icontains=busca)
            | Q(descricao__icontains=busca)
        )
    if categoria:
        itens = itens.filter(item_catalogo__categoria_id=categoria)

    itens = itens.order_by(*ITEM_SORT_MAP.get(ordenacao, ITEM_SORT_MAP["ordem"]))
    categorias = (
        queryset_da_empresa(CategoriaItem.objects.filter(itens__itens_em_orcamentos__orcamento=orcamento), request.user)
        .distinct()
        .order_by("nome")
    )
    return {
        "item_q": busca,
        "item_categoria": categoria,
        "item_sort": ordenacao,
        "categorias_item": categorias,
        "itens": itens,
    }


def montar_url_edicao_orcamento(request, orcamento_pk, *, item_edit=None):
    origem = request.POST if request.method == "POST" else request.GET
    params = []
    for chave in ("item_q", "item_categoria", "item_sort"):
        valor = (origem.get(chave) or "").strip()
        if valor:
            params.append((chave, valor))
    if item_edit:
        params.append(("item_edit", str(item_edit)))
    query = urlencode(params)
    url = reverse("orcamentos:editar", kwargs={"pk": orcamento_pk})
    return f"{url}?{query}" if query else url


def renderizar_editor_orcamento(
    request,
    orcamento,
    form,
    item_form,
    modo_somente_leitura,
    *,
    titulo="Editar orçamento",
    item_editando_override=None,
    item_form_edicao_override=None,
):
    itens = orcamento.itens.all()
    item_editando, item_form_edicao = obter_item_em_edicao(request, orcamento, modo_somente_leitura)
    if item_editando_override is not None:
        item_editando = item_editando_override
        item_form_edicao = item_form_edicao_override

    context = {
        "form": form,
        "titulo": titulo,
        "orcamento": orcamento,
        "item_form": item_form,
        "item_editando": item_editando,
        "item_form_edicao": item_form_edicao,
        "modo_somente_leitura": modo_somente_leitura,
    }
    context.update(obter_estado_itens(request, orcamento))
    return render(request, "orcamentos/form.html", context)


def responder_ajax_item(request, orcamento, *, item_form=None, item_editando=None, item_form_edicao=None, mensagem=None):
    context_base = {
        "orcamento": orcamento,
        "item_editando": item_editando,
        "item_form_edicao": item_form_edicao,
    }
    context_base.update(obter_estado_itens(request, orcamento))
    payload = {
        "itens_html": render_to_string("orcamentos/partials/itens_tabela.html", context_base, request=request),
        "totais_html": render_to_string("orcamentos/partials/totais_card.html", {"orcamento": orcamento}, request=request),
        "flash_html": render_to_string("orcamentos/partials/item_feedback.html", {"mensagem": mensagem}, request=request),
    }

    if item_form is not None:
        contexto_novo_item = dict(context_base)
        contexto_novo_item["item_form"] = item_form
        payload["novo_item_html"] = render_to_string(
            "orcamentos/partials/item_create_panel.html",
            contexto_novo_item,
            request=request,
        )

    return JsonResponse(payload)


@require_capability("pode_visualizar_orcamentos")
def orcamento_lista(request):
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    ativo = request.GET.get("ativo", "ativos").strip()
    ordenar = request.GET.get("sort", "recentes")

    orcamentos = queryset_da_empresa(Orcamento.objects.select_related("cliente").all(), request.user)

    if busca:
        orcamentos = orcamentos.filter(
            Q(numero__icontains=busca)
            | Q(cliente__nome_razao_social__icontains=busca)
            | Q(titulo__icontains=busca)
        )

    if status:
        orcamentos = orcamentos.filter(status=status)

    if ativo != "inativos":
        orcamentos = orcamentos.filter(ativo=True)
    else:
        orcamentos = orcamentos.filter(ativo=False)

    ordenacoes = {
        "recentes": "-criado_em",
        "numero": "numero",
        "cliente": "cliente__nome_razao_social",
        "data": "-data_emissao",
        "valor_maior": "-total_final",
        "valor_menor": "total_final",
    }
    orcamentos = orcamentos.order_by(ordenacoes.get(ordenar, "-criado_em"))
    page_obj = paginate_queryset(request, orcamentos, per_page=12)

    context = {
        "orcamentos": page_obj,
        "page_obj": page_obj,
        "busca": busca,
        "status": status,
        "ativo": ativo,
        "sort": ordenar,
        "status_choices": Orcamento.STATUS_CHOICES,
    }
    return render(request, "orcamentos/lista.html", context)


@require_capability("pode_gerenciar_orcamentos")
def orcamento_criar(request):
    if request.method == "POST":
        form = OrcamentoForm(request.POST, user=request.user)
        if form.is_valid():
            orcamento = form.save(commit=False)
            orcamento.empresa = obter_grupo_empresa_ou_erro(request.user)
            orcamento.criado_por = request.user
            orcamento.atualizado_por = request.user
            orcamento.save()
            messages.success(request, "Orçamento criado com sucesso.")
            return redirect("orcamentos:editar", pk=orcamento.pk)
    else:
        form = OrcamentoForm(user=request.user)

    return render(
        request,
        "orcamentos/form.html",
        {"form": form, "titulo": "Novo orçamento"},
    )


@require_capability("pode_visualizar_orcamentos")
def orcamento_editar(request, pk):
    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=pk)
    modo_somente_leitura = not request.user.pode_gerenciar_orcamentos

    if request.method == "POST":
        if modo_somente_leitura:
            raise PermissionDenied

        form = OrcamentoForm(request.POST, instance=orcamento, user=request.user)
        if form.is_valid():
            orcamento = form.save(commit=False)
            orcamento.atualizado_por = request.user
            orcamento.save()
            orcamento.recalcular_totais()
            messages.success(request, "Orçamento atualizado com sucesso.")
            return redirect("orcamentos:editar", pk=orcamento.pk)
    else:
        form = OrcamentoForm(instance=orcamento, user=request.user)

    item_form = ItemOrcamentoForm(user=request.user)
    return renderizar_editor_orcamento(
        request,
        orcamento,
        form,
        item_form,
        modo_somente_leitura,
    )


@require_capability("pode_gerenciar_orcamentos")
def orcamento_excluir(request, pk):
    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=pk)
    acao = "reativar" if not orcamento.ativo else "inativar"

    if request.method == "POST":
        orcamento.ativo = not orcamento.ativo
        orcamento.save(update_fields=["ativo", "atualizado_em"])
        if orcamento.ativo:
            messages.success(request, "Orçamento reativado com sucesso.")
        else:
            messages.success(request, "Orçamento inativado com sucesso.")
        return redirect("orcamentos:lista")

    return render(request, "orcamentos/excluir.html", {"orcamento": orcamento, "acao": acao})


@require_capability("pode_gerenciar_orcamentos")
@require_POST
def orcamento_alterar_status(request, pk, novo_status):
    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=pk)

    if novo_status in STATUS_PERMITIDOS:
        orcamento.status = novo_status
        orcamento.atualizado_por = request.user
        orcamento.save(update_fields=["status", "atualizado_por", "atualizado_em"])
        messages.success(request, f"Status alterado para {orcamento.get_status_display()}.")
    else:
        messages.error(request, "Status solicitado é inválido.")

    return redirect("orcamentos:lista")


@require_capability("pode_gerenciar_orcamentos")
def item_orcamento_criar(request, orcamento_pk):
    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=orcamento_pk)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == "POST":
        form = ItemOrcamentoForm(request.POST, user=request.user)
        if form.is_valid():
            item = form.save(commit=False)
            item.orcamento = orcamento
            item.ordem = orcamento.itens.count() + 1
            item.save()
            normalizar_ordens_itens(orcamento)
            mensagem = f"Item '{item.nome}' adicionado."
            if is_ajax:
                return responder_ajax_item(
                    request,
                    orcamento,
                    item_form=ItemOrcamentoForm(user=request.user),
                    mensagem=mensagem,
                )

            messages.success(request, mensagem)
            return redirect(montar_url_edicao_orcamento(request, orcamento.pk))

        if is_ajax:
            return responder_ajax_item(
                request,
                orcamento,
                item_form=form,
            )

        return renderizar_editor_orcamento(
            request,
            orcamento,
            OrcamentoForm(instance=orcamento, user=request.user),
            form,
            False,
        )

    return redirect("orcamentos:editar", pk=orcamento.pk)


@require_capability("pode_gerenciar_orcamentos")
def item_orcamento_editar(request, orcamento_pk, item_pk):
    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=orcamento_pk)
    item = get_object_or_404(ItemOrcamento, pk=item_pk, orcamento=orcamento)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == "POST":
        form = ItemOrcamentoForm(request.POST, instance=item, user=request.user)
        if form.is_valid():
            item = form.save()
            normalizar_ordens_itens(orcamento)
            mensagem = f"Item '{item.nome}' atualizado."
            if is_ajax:
                return responder_ajax_item(
                    request,
                    orcamento,
                    item_form=ItemOrcamentoForm(user=request.user),
                    mensagem=mensagem,
                )

            messages.success(request, mensagem)
            return redirect(montar_url_edicao_orcamento(request, orcamento.pk))

        if is_ajax:
            return responder_ajax_item(
                request,
                orcamento,
                item_form=ItemOrcamentoForm(user=request.user),
                item_editando=item,
                item_form_edicao=form,
            )

        return renderizar_editor_orcamento(
            request,
            orcamento,
            OrcamentoForm(instance=orcamento, user=request.user),
            ItemOrcamentoForm(user=request.user),
            False,
            item_editando_override=item,
            item_form_edicao_override=form,
        )

    return redirect(f"{montar_url_edicao_orcamento(request, orcamento.pk, item_edit=item.pk)}#painel-item-edicao")


@require_capability("pode_gerenciar_orcamentos")
def item_orcamento_excluir(request, orcamento_pk, item_pk):
    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=orcamento_pk)
    item = get_object_or_404(ItemOrcamento, pk=item_pk, orcamento=orcamento)

    if request.method == "POST":
        nome_item = item.nome
        item.delete()
        normalizar_ordens_itens(orcamento)
        messages.success(request, f"Item '{nome_item}' excluído.")
        return redirect(montar_url_edicao_orcamento(request, orcamento.pk))

    return render(
        request,
        "orcamentos/item_excluir.html",
        {
            "orcamento": orcamento,
            "item": item,
            "retorno_edicao_url": montar_url_edicao_orcamento(request, orcamento.pk),
        },
    )


@require_capability("pode_gerenciar_orcamentos")
@require_POST
def item_orcamento_duplicar(request, orcamento_pk, item_pk):
    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=orcamento_pk)
    item = get_object_or_404(ItemOrcamento, pk=item_pk, orcamento=orcamento)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    with transaction.atomic():
        (
            ItemOrcamento.objects.filter(orcamento=orcamento, ordem__gt=item.ordem)
            .update(ordem=models.F("ordem") + 1)
        )

        item.pk = None
        item.ordem = item.ordem + 1
        item.save()

    normalizar_ordens_itens(orcamento)
    mensagem = f"Item '{item.nome}' duplicado."
    if is_ajax:
        return responder_ajax_item(
            request,
            orcamento,
            item_form=ItemOrcamentoForm(user=request.user),
            mensagem=mensagem,
        )
    messages.success(request, mensagem)
    return redirect(montar_url_edicao_orcamento(request, orcamento.pk))


@require_capability("pode_gerenciar_orcamentos")
@require_POST
def item_orcamento_duplicar_editar(request, orcamento_pk, item_pk):
    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=orcamento_pk)
    item = get_object_or_404(ItemOrcamento, pk=item_pk, orcamento=orcamento)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    with transaction.atomic():
        (
            ItemOrcamento.objects.filter(orcamento=orcamento, ordem__gt=item.ordem)
            .update(ordem=models.F("ordem") + 1)
        )

        item.pk = None
        item.ordem = item.ordem + 1
        item.save()

    normalizar_ordens_itens(orcamento)
    mensagem = f"Item '{item.nome}' duplicado para edição."
    if is_ajax:
        return responder_ajax_item(
            request,
            orcamento,
            item_form=ItemOrcamentoForm(user=request.user),
            item_editando=item,
            item_form_edicao=ItemOrcamentoForm(instance=item, user=request.user),
            mensagem=mensagem,
        )
    messages.success(request, mensagem)
    return redirect(f"{montar_url_edicao_orcamento(request, orcamento.pk, item_edit=item.pk)}#painel-item-edicao")


@require_capability("pode_gerenciar_orcamentos")
@require_POST
def item_orcamento_mover(request, orcamento_pk, item_pk, direcao):
    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=orcamento_pk)
    item = get_object_or_404(ItemOrcamento, pk=item_pk, orcamento=orcamento)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    itens = list(orcamento.itens.all().order_by("ordem", "id"))
    indice_atual = next((indice for indice, atual in enumerate(itens) if atual.pk == item.pk), None)

    if indice_atual is None:
        return redirect(montar_url_edicao_orcamento(request, orcamento.pk))

    deslocamento = -1 if direcao == "cima" else 1 if direcao == "baixo" else 0
    novo_indice = indice_atual + deslocamento

    if deslocamento == 0 or novo_indice < 0 or novo_indice >= len(itens):
        return redirect(montar_url_edicao_orcamento(request, orcamento.pk))

    itens[indice_atual], itens[novo_indice] = itens[novo_indice], itens[indice_atual]

    with transaction.atomic():
        for ordem, atual in enumerate(itens, start=1):
            if atual.ordem != ordem:
                ItemOrcamento.objects.filter(pk=atual.pk).update(ordem=ordem)

    mensagem = f"Item '{item.nome}' movido."
    if is_ajax:
        return responder_ajax_item(
            request,
            orcamento,
            item_form=ItemOrcamentoForm(user=request.user),
            mensagem=mensagem,
        )
    messages.success(request, mensagem)
    return redirect(montar_url_edicao_orcamento(request, orcamento.pk))


@require_capability("pode_gerenciar_orcamentos")
def item_orcamento_preview(request, orcamento_pk):
    if request.method != "GET":
        return HttpResponseBadRequest("Método inválido.")

    orcamento = get_object_or_404(queryset_da_empresa(Orcamento.objects.all(), request.user), pk=orcamento_pk)
    form = ItemOrcamentoForm(request.GET, user=request.user)
    form.is_valid()
    item_preview, erro_validacao = form.construir_item_preview(orcamento)

    return render(request, "orcamentos/partials/item_preview_card.html", {
        "item_preview": item_preview,
        "erro_validacao_preview": erro_validacao,
    })
