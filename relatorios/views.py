from mimetypes import guess_type

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_safe

from core.permissions import require_capability
from core.tenancy import (
    obter_grupo_empresa_ou_erro,
    obter_grupo_empresa_usuario,
    queryset_da_empresa,
)
from orcamentos.models import Orcamento

from .exporters import (
    gerar_excel_orcamento,
    gerar_pdf_memorial_descritivo,
    gerar_pdf_orcamento,
    gerar_word_memorial_descritivo,
    obter_alerta_status,
)
from .forms import ConfiguracaoEmpresaForm
from .models import ConfiguracaoEmpresa


def obter_configuracao_do_orcamento(orcamento, user):
    """O cadastro que vale para o orçamento: o vinculado a ele (se for da
    empresa do usuário) ou, na falta, o cadastro único da empresa."""
    if getattr(orcamento, "configuracao_empresa_id", None):
        vinculada = (
            queryset_da_empresa(ConfiguracaoEmpresa.objects.all(), user)
            .filter(pk=orcamento.configuracao_empresa_id)
            .first()
        )
        if vinculada:
            return vinculada
    return ConfiguracaoEmpresa.da_empresa(obter_grupo_empresa_usuario(user))


@require_capability("pode_visualizar_relatorios")
def minha_empresa(request):
    """Cadastro único da empresa do usuário: cria na primeira vez, edita nas
    seguintes. Quem só visualiza vê o formulário travado."""
    empresa = obter_grupo_empresa_ou_erro(request.user)
    configuracao = ConfiguracaoEmpresa.da_empresa(empresa)
    pode_editar = request.user.pode_gerenciar_relatorios

    if request.method == "POST":
        if not pode_editar:
            raise PermissionDenied
        form = ConfiguracaoEmpresaForm(request.POST, request.FILES, instance=configuracao)
        if form.is_valid():
            nova = form.save(commit=False)
            nova.empresa = empresa
            nova.ativo = True
            nova.save()
            if configuracao is None:
                # Orçamentos criados antes do cadastro passam a usá-lo.
                Orcamento.objects.filter(empresa=empresa, configuracao_empresa__isnull=True).update(
                    configuracao_empresa=nova
                )
            messages.success(
                request,
                "Dados da empresa salvos. Os relatórios e os orçamentos ainda não enviados "
                "passam a usar essas informações.",
            )
            return redirect("relatorios:minha_empresa")
    else:
        form = ConfiguracaoEmpresaForm(instance=configuracao)

    return render(
        request,
        "relatorios/configuracao_form.html",
        {
            "form": form,
            "titulo": "Minha empresa",
            "configuracao": configuracao,
            "somente_leitura": not pode_editar,
        },
    )


@require_safe
def para_minha_empresa(request, *args, **kwargs):
    """Rotas antigas da lista de configurações. Agora há um cadastro só."""
    return redirect("relatorios:minha_empresa")


@require_capability("pode_visualizar_relatorios")
def configuracao_logo(request, pk):
    configuracao = get_object_or_404(
        queryset_da_empresa(ConfiguracaoEmpresa.objects.all(), request.user),
        pk=pk,
    )
    if not configuracao.logo:
        raise Http404
    try:
        arquivo = configuracao.logo.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc

    tipo_conteudo, _ = guess_type(configuracao.logo.name or "")
    response = FileResponse(arquivo, content_type=tipo_conteudo or "application/octet-stream")
    response["Cache-Control"] = "private, max-age=300"
    return response


@require_capability("pode_visualizar_orcamentos")
def orcamento_relatorio_central(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(
            Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user
        ),
        pk=pk,
    )
    if request.method == "POST":
        if not request.user.pode_gerenciar_orcamentos:
            raise PermissionDenied
        campos_opcoes = [
            "mostrar_ajustes_no_relatorio",
            "mostrar_descricao_inicial_no_relatorio",
            "mostrar_observacoes_gerais_no_relatorio",
            "mostrar_rodape_institucional_no_relatorio",
            "mostrar_contatos_evento_no_memorial",
            "mostrar_financeiro_no_memorial",
            "mostrar_dados_contratuais_no_memorial",
            "mostrar_informacoes_complementares_no_memorial",
        ]
        for campo in campos_opcoes:
            setattr(orcamento, campo, request.POST.get(campo) == "on")
        orcamento.save(update_fields=[*campos_opcoes, "atualizado_em"])
        messages.success(request, "Opções do relatório atualizadas.")
        return redirect("relatorios:orcamento_central", pk=orcamento.pk)
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    alerta_status = obter_alerta_status(orcamento)
    return render(
        request,
        "relatorios/orcamento_central.html",
        {
            "orcamento": orcamento,
            "configuracao": configuracao,
            "alerta_status": alerta_status,
            "subtotais_categoria": orcamento.subtotais_por_categoria(),
        },
    )


@require_capability("pode_visualizar_orcamentos")
def orcamento_exportar_excel(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(
            Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user
        ),
        pk=pk,
    )
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    alerta_status = obter_alerta_status(orcamento)
    conteudo = gerar_excel_orcamento(orcamento, configuracao, alerta_status)

    response = HttpResponse(conteudo, content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = f'attachment; filename="orcamento-{orcamento.numero}.xls"'
    return response


@require_capability("pode_visualizar_orcamentos")
def orcamento_exportar_pdf(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(
            Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user
        ),
        pk=pk,
    )
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    alerta_status = obter_alerta_status(orcamento)
    conteudo = gerar_pdf_orcamento(orcamento, configuracao, alerta_status)

    response = HttpResponse(conteudo, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="orcamento-{orcamento.numero}.pdf"'
    return response


@require_capability("pode_visualizar_orcamentos")
def orcamento_exportar_memorial_pdf(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(
            Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user
        ),
        pk=pk,
    )
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    conteudo = gerar_pdf_memorial_descritivo(orcamento, configuracao)

    response = HttpResponse(conteudo, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="memorial-descritivo-{orcamento.numero}.pdf"'
    )
    return response


@require_capability("pode_visualizar_orcamentos")
def orcamento_exportar_memorial_word(request, pk):
    orcamento = get_object_or_404(
        queryset_da_empresa(
            Orcamento.objects.select_related("cliente", "configuracao_empresa"), request.user
        ),
        pk=pk,
    )
    configuracao = obter_configuracao_do_orcamento(orcamento, request.user)
    conteudo = gerar_word_memorial_descritivo(orcamento, configuracao)

    response = HttpResponse(conteudo, content_type="application/rtf")
    response["Content-Disposition"] = (
        f'attachment; filename="memorial-descritivo-{orcamento.numero}.rtf"'
    )
    return response
