from django.contrib import admin
from unfold.admin import ModelAdmin

from core.admin_permissions import PerfilAdminPermissionMixin

from .models import ImportacaoMemorial


@admin.register(ImportacaoMemorial)
class ImportacaoMemorialAdmin(PerfilAdminPermissionMixin, ModelAdmin):
    # Registro de auditoria: só se lê. Quem cria é a tela do orçamento.
    capability_view = "pode_visualizar_orcamentos"
    capability_add = None
    capability_change = None
    capability_delete = "eh_admin_perfil"
    list_display = (
        "orcamento",
        "arquivo_nome",
        "status",
        "itens_criados",
        "tokens_entrada",
        "tokens_saida",
        "criado_por",
        "criado_em",
    )
    list_filter = ("status",)
    search_fields = ("orcamento__numero", "arquivo_nome")
    readonly_fields = ("resultado", "erro", "modelo", "tokens_entrada", "tokens_saida")
