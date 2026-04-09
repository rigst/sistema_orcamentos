from django import forms

from .models import CategoriaItem, ItemCatalogo


class CategoriaItemForm(forms.ModelForm):
    class Meta:
        model = CategoriaItem
        fields = ["nome", "descricao", "ativo"]


class ItemCatalogoForm(forms.ModelForm):
    class Meta:
        model = ItemCatalogo
        fields = [
            "codigo",
            "nome",
            "descricao_padrao",
            "categoria",
            "unidade_medida",
            "valor_unitario_padrao",
            "observacoes",
            "ativo",
        ]
