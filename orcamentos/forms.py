from django import forms
from django.core.exceptions import ValidationError
from django.utils.timezone import localdate

from catalogo.models import ItemCatalogo
from core.form_fields import substituir_por_decimal_br
from .models import ItemOrcamento, Orcamento


class OrcamentoForm(forms.ModelForm):
    class Meta:
        model = Orcamento
        fields = [
            "numero",
            "cliente",
            "titulo",
            "descricao_inicial",
            "observacoes_gerais",
            "status",
            "data_emissao",
            "validade_em",
            "desconto_global_valor",
            "desconto_global_percentual",
            "acrescimo_global_valor",
            "acrescimo_global_percentual",
            "mostrar_ajustes_no_relatorio",
        ]
        widgets = {
            "data_emissao": forms.DateInput(attrs={"type": "date"}),
            "validade_em": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        placeholders = {
            "numero": "Gerado automaticamente pelo sistema",
            "titulo": "Ex.: Orçamento de reforma da recepção",
            "descricao_inicial": "Resumo inicial do orçamento",
            "observacoes_gerais": "Observações internas ou gerais",
            "desconto_global_valor": "0.00",
            "desconto_global_percentual": "0.00",
            "acrescimo_global_valor": "0.00",
            "acrescimo_global_percentual": "0.00",
        }

        for nome, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.TextInput, forms.EmailInput, forms.NumberInput, forms.DateInput, forms.Textarea)):
                widget.attrs.setdefault("placeholder", placeholders.get(nome, ""))

        self.fields["numero"].required = False
        self.fields["numero"].widget.attrs.update(
            {
                "readonly": "readonly",
                "tabindex": "-1",
            }
        )

        for nome_campo in [
            "desconto_global_valor",
            "desconto_global_percentual",
            "acrescimo_global_valor",
            "acrescimo_global_percentual",
        ]:
            self.fields[nome_campo].required = False
            substituir_por_decimal_br(self, nome_campo, currency=nome_campo.endswith("_valor"))

        self.fields["mostrar_ajustes_no_relatorio"].required = False
        if not self.instance.pk and not self.is_bound:
            self.fields["data_emissao"].initial = localdate()


class ItemOrcamentoForm(forms.ModelForm):
    class Meta:
        model = ItemOrcamento
        fields = [
            "item_catalogo",
            "ordem",
            "codigo_item",
            "nome",
            "descricao",
            "unidade_medida",
            "quantidade",
            "valor_unitario",
            "desconto_valor",
            "desconto_percentual",
            "acrescimo_valor",
            "acrescimo_percentual",
            "observacoes",
        ]
        widgets = {
            "descricao": forms.Textarea(),
            "observacoes": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item_catalogo"].queryset = ItemCatalogo.objects.filter(ativo=True).select_related("categoria").order_by("nome")
        self.fields["item_catalogo"].required = False
        self.fields["nome"].required = False
        self.fields["unidade_medida"].required = False
        for nome_campo in [
            "quantidade",
            "valor_unitario",
            "desconto_valor",
            "desconto_percentual",
            "acrescimo_valor",
            "acrescimo_percentual",
        ]:
            if nome_campo != "quantidade" and nome_campo != "valor_unitario":
                self.fields[nome_campo].required = False
            substituir_por_decimal_br(self, nome_campo, currency=nome_campo.endswith("_valor") or nome_campo == "valor_unitario")

        self.fields["codigo_item"].required = False
        self.fields["codigo_item"].widget.attrs.update(
            {
                "readonly": "readonly",
                "tabindex": "-1",
                "placeholder": "Gerado automaticamente pelo sistema",
            }
        )

    def aplicar_defaults_catalogo(self, cleaned_data):
        item_catalogo = cleaned_data.get("item_catalogo")

        if item_catalogo:
            if not cleaned_data.get("nome"):
                cleaned_data["nome"] = item_catalogo.nome
            if not cleaned_data.get("descricao"):
                cleaned_data["descricao"] = item_catalogo.descricao_padrao
            if not cleaned_data.get("unidade_medida"):
                cleaned_data["unidade_medida"] = item_catalogo.unidade_medida

            valor_unitario = cleaned_data.get("valor_unitario")
            if valor_unitario in (None, 0):
                cleaned_data["valor_unitario"] = item_catalogo.valor_unitario_padrao

        return cleaned_data

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data = self.aplicar_defaults_catalogo(cleaned_data)

        if not cleaned_data.get("nome"):
            self.add_error("nome", "Este campo é obrigatório.")

        if not cleaned_data.get("unidade_medida"):
            self.add_error("unidade_medida", "Este campo é obrigatório.")

        return cleaned_data

    def construir_item_preview(self, orcamento):
        cleaned_data = self.aplicar_defaults_catalogo(dict(self.cleaned_data))
        item = ItemOrcamento(
            orcamento=orcamento,
            item_catalogo=cleaned_data.get("item_catalogo"),
            ordem=cleaned_data.get("ordem") or 1,
            codigo_item=cleaned_data.get("codigo_item") or "",
            nome=cleaned_data.get("nome") or "Prévia",
            descricao=cleaned_data.get("descricao") or "",
            unidade_medida=cleaned_data.get("unidade_medida") or "un",
            quantidade=cleaned_data.get("quantidade") or 1,
            valor_unitario=cleaned_data.get("valor_unitario") or 0,
            desconto_valor=cleaned_data.get("desconto_valor") or 0,
            desconto_percentual=cleaned_data.get("desconto_percentual") or 0,
            acrescimo_valor=cleaned_data.get("acrescimo_valor") or 0,
            acrescimo_percentual=cleaned_data.get("acrescimo_percentual") or 0,
            observacoes=cleaned_data.get("observacoes") or "",
        )

        erro_validacao = None
        try:
            item.clean()
        except ValidationError as exc:
            if hasattr(exc, "messages"):
                erro_validacao = " ".join(exc.messages)
            else:
                erro_validacao = str(exc)

        item.subtotal = item.calcular_subtotal()
        item.divergencias_catalogo = item.campos_divergentes_catalogo()
        return item, erro_validacao
