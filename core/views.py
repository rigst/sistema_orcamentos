from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from orcamentos.models import Orcamento


@login_required
def dashboard(request):
    ultimos_orcamentos = Orcamento.objects.select_related("cliente").order_by("-criado_em")[:5]

    resumo_status = (
        Orcamento.objects.values("status")
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

    context = {
        "ultimos_orcamentos": ultimos_orcamentos,
        "status_map": status_map,
    }
    return render(request, "core/dashboard.html", context)
