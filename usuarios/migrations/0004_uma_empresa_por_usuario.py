"""Cada usuário passa a ter uma única empresa.

Quem tinha mais de uma fica com a escolhida abaixo. Na falta de escolha
explícita, fica a empresa em que o usuário mais criou orçamentos e, no empate,
a mais antiga. Os dados das outras empresas não são tocados: só o vínculo do
usuário com elas sai.
"""

from django.db import migrations
from django.db.models import Count

# Decidido com o dono do sistema: o orçamentista "Empresa padrão + E-ventos"
# fica na E-ventos, onde estão o admin e a maior parte dos orçamentos.
ESCOLHAS_POR_NOME = {"E-ventos"}


def manter_uma_empresa(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Orcamento = apps.get_model("orcamentos", "Orcamento")
    com_varias = Usuario.objects.annotate(n=Count("groups")).filter(n__gt=1)
    for usuario in com_varias:
        grupos = list(usuario.groups.order_by("id"))
        escolhido = next((g for g in grupos if g.name in ESCOLHAS_POR_NOME), None)
        if escolhido is None:
            uso = dict(
                Orcamento.objects.filter(criado_por=usuario, empresa__in=grupos)
                .values_list("empresa_id")
                .annotate(n=Count("id"))
            )
            escolhido = max(grupos, key=lambda g: (uso.get(g.pk, 0), -g.pk))
        usuario.groups.set([escolhido])


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0003_bootstrap_empresas"),
        ("orcamentos", "0009_cliente_opcional"),
    ]

    operations = [
        # Irreversível na prática: não há como saber, depois, quais vínculos
        # existiam. Reverter só não falha.
        migrations.RunPython(manter_uma_empresa, migrations.RunPython.noop),
    ]
