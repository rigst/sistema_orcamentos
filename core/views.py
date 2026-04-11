from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import render

from core.tenancy import queryset_da_empresa
from orcamentos.models import Orcamento


@login_required
def dashboard(request):
    periodo = request.GET.get("periodo", "30")
    ultimos_orcamentos = queryset_da_empresa(
        Orcamento.objects.select_related("cliente")
        .filter(ativo=True)
        .exclude(status__in=["rejeitado", "cancelado"])
        .order_by("-criado_em"),
        request.user,
    )
    orcamentos = queryset_da_empresa(Orcamento.objects.filter(ativo=True), request.user)

    if periodo != "todos":
        try:
            dias = int(periodo)
        except (TypeError, ValueError):
            dias = 30
        from django.utils import timezone

        inicio = timezone.localdate() - timedelta(days=dias)
        orcamentos = orcamentos.filter(data_emissao__gte=inicio)
        ultimos_orcamentos = ultimos_orcamentos.filter(data_emissao__gte=inicio)

    resumo_status = (
        orcamentos.values("status")
        .annotate(total=Count("id"))
    )

    status_map = {
        "rascunho": 0,
        "em_elaboracao": 0,
        "enviado": 0,
        "aprovado": 0,
    }

    for item in resumo_status:
        if item["status"] in status_map:
            status_map[item["status"]] = item["total"]

    indicadores = orcamentos.aggregate(
        total_orcamentos=Count("id"),
        valor_total=Coalesce(Sum("total_final"), Value(0), output_field=DecimalField(max_digits=14, decimal_places=2)),
    )
    indicadores["valor_aprovado"] = orcamentos.filter(status="aprovado").aggregate(
        total=Coalesce(Sum("total_final"), Value(0), output_field=DecimalField(max_digits=14, decimal_places=2))
    )["total"]
    indicadores["pendentes"] = orcamentos.filter(status__in=["rascunho", "em_elaboracao", "enviado"]).count()
    ultimos_orcamentos = ultimos_orcamentos[:5]

    context = {
        "ultimos_orcamentos": ultimos_orcamentos,
        "status_map": status_map,
        "indicadores": indicadores,
        "periodo": periodo,
        "saudacao_dashboard": f"Bom ter você por aqui, {request.user}.",
    }
    return render(request, "core/dashboard.html", context)


@login_required
def manual(request):
    perfis = [
        {
            "nome": "Administrador",
            "descricao": "Acompanha o sistema inteiro e gerencia clientes, catálogo, empresa, orçamentos e usuários.",
        },
        {
            "nome": "Orçamentista",
            "descricao": "Trabalha com clientes e orçamentos, consulta catálogo e empresa, e acompanha relatórios.",
        },
        {
            "nome": "Visualizador",
            "descricao": "Consulta informações do sistema sem editar cadastros nem movimentar orçamentos.",
        },
    ]
    return render(
        request,
        "core/manual.html",
        {
            "perfis_manual": perfis,
        },
    )
