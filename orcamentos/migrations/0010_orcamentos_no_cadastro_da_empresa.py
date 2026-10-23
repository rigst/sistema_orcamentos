"""Liga ao cadastro da própria empresa os orçamentos que ficaram sem ele.

Antes o seletor "Empresa do orçamento" podia ficar vazio; agora o cadastro é
um só por empresa e vale sempre. Só preenche o vazio: orçamento que já aponta
para um cadastro continua apontando para ele.
"""

from django.db import migrations


def ligar_ao_cadastro_da_empresa(apps, schema_editor):
    Orcamento = apps.get_model("orcamentos", "Orcamento")
    ConfiguracaoEmpresa = apps.get_model("relatorios", "ConfiguracaoEmpresa")
    pendentes = Orcamento.objects.filter(configuracao_empresa__isnull=True).exclude(
        empresa__isnull=True
    )
    for empresa_id in pendentes.values_list("empresa_id", flat=True).distinct():
        cadastro = (
            ConfiguracaoEmpresa.objects.filter(empresa_id=empresa_id)
            .order_by("-ativo", "-atualizado_em", "-pk")
            .first()
        )
        if cadastro is not None:
            pendentes.filter(empresa_id=empresa_id).update(configuracao_empresa=cadastro)


class Migration(migrations.Migration):
    dependencies = [
        ("orcamentos", "0009_cliente_opcional"),
        ("relatorios", "0005_padroes_comerciais_da_empresa"),
    ]

    operations = [
        # Reverter não desfaz o vínculo: deixar o orçamento sem cadastro de
        # novo não devolveria nada que existisse antes.
        migrations.RunPython(ligar_ao_cadastro_da_empresa, migrations.RunPython.noop),
    ]
