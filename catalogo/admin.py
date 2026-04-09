from django.contrib import admin

from .models import CategoriaItem, ItemCatalogo


@admin.register(CategoriaItem)
class CategoriaItemAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "criado_em")
    list_filter = ("ativo",)
    search_fields = ("nome",)
    ordering = ("nome",)


@admin.register(ItemCatalogo)
class ItemCatalogoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nome",
        "categoria",
        "unidade_medida",
        "valor_unitario_padrao",
        "ativo",
    )
    list_filter = ("ativo", "categoria", "unidade_medida")
    search_fields = ("codigo", "nome", "descricao_padrao")
    ordering = ("nome",)
