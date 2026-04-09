from django import forms

from core.form_fields import substituir_por_decimal_br
from .models import CategoriaItem, ItemCatalogo


class CategoriaItemForm(forms.ModelForm):
    class Meta:
        model = CategoriaItem
        fields = ["nome", "descricao", "cor", "ativo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ativo"].widget = forms.HiddenInput()
        self.fields["ativo"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativo
        self.fields["descricao"].widget.attrs["rows"] = 3

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
        self.fields["ativo"].widget = forms.HiddenInput()
        self.fields["ativo"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativo
        substituir_por_decimal_br(self, "valor_unitario_padrao", currency=True)
        self.fields["nome"].error_messages["required"] = "Informe o nome do item."
        self.fields["valor_unitario_padrao"].error_messages["min_value"] = "Informe um valor maior ou igual a zero."
        self.fields["codigo"].required = False
        self.fields["codigo"].widget.attrs.update(
            {
                "readonly": "readonly",
                "tabindex": "-1",
                "placeholder": "Gerado automaticamente pelo sistema",
            }
        )
        self.fields["descricao_padrao"].widget.attrs["rows"] = 3
        self.fields["observacoes"].widget.attrs["rows"] = 3

    def clean_codigo(self):
        if self.instance.pk:
            return self.instance.codigo
        return (self.cleaned_data.get("codigo") or "").strip().upper()

    def clean_nome(self):
        valor = (self.cleaned_data.get("nome") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome do item.")
        return valor
