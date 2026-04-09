from django.contrib import admin

from .models import ConfiguracaoEmpresa


@admin.register(ConfiguracaoEmpresa)
class ConfiguracaoEmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome_empresa", "email", "telefone", "cidade", "estado", "atualizado_em")
    search_fields = ("nome_empresa", "nome_fantasia", "cpf_cnpj", "email")
