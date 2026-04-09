from django import forms

from core.form_fields import substituir_por_decimal_br
from .models import CategoriaItem, ItemCatalogo


class CategoriaItemForm(forms.ModelForm):
    class Meta:
        model = CategoriaItem
        fields = ["nome", "descricao", "ativo"]

    def clean_nome(self):
        valor = (self.cleaned_data.get("nome") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome da categoria.")
        return valor


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        substituir_por_decimal_br(self, "valor_unitario_padrao", currency=True)
        self.fields["codigo"].help_text = "Obrigatório. Use um código único para localizar o item."
        self.fields["nome"].help_text = "Obrigatório."
        self.fields["valor_unitario_padrao"].help_text = "Obrigatório. Não pode ser negativo."
        self.fields["codigo"].error_messages["required"] = "Informe o código do item."
        self.fields["nome"].error_messages["required"] = "Informe o nome do item."
        self.fields["valor_unitario_padrao"].error_messages["min_value"] = "Informe um valor maior ou igual a zero."

    def clean_codigo(self):
        valor = (self.cleaned_data.get("codigo") or "").strip().upper()
        if not valor:
            raise forms.ValidationError("Informe o código do item.")
        return valor

    def clean_nome(self):
        valor = (self.cleaned_data.get("nome") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome do item.")
        return valor
