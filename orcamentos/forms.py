from django import forms

from .models import Orcamento


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
            "numero": "Ex.: ORC-2026-0001",
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

        self.fields["mostrar_ajustes_no_relatorio"].required = False
