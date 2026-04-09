from django.contrib import admin

from .models import ItemOrcamento, Orcamento


class ItemOrcamentoInline(admin.TabularInline):
    model = ItemOrcamento
    extra = 1


@admin.register(Orcamento)
class OrcamentoAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "cliente",
        "status",
        "data_emissao",
        "validade_em",
        "total_final",
        "mostrar_ajustes_no_relatorio",
    )
    list_filter = ("status", "mostrar_ajustes_no_relatorio", "data_emissao")
    search_fields = ("numero", "cliente__nome_razao_social", "titulo")
    inlines = [ItemOrcamentoInline]


@admin.register(ItemOrcamento)
class ItemOrcamentoAdmin(admin.ModelAdmin):
    list_display = (
        "orcamento",
        "ordem",
        "codigo_item",
        "nome",
        "quantidade",
        "valor_unitario",
        "subtotal",
    )
    list_filter = ("unidade_medida",)
    search_fields = ("orcamento__numero", "codigo_item", "nome")
