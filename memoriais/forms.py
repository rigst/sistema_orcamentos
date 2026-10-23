from typing import cast

from django import forms

from .extracao import EXTENSOES_ACEITAS


class ImportarMemorialForm(forms.Form):
    arquivo = forms.FileField(
        required=False,
        label="Arquivo do memorial",
        help_text="PDF, DOCX ou TXT. PDF escaneado também funciona.",
        widget=forms.ClearableFileInput(attrs={"accept": ",".join(EXTENSOES_ACEITAS)}),
    )
    texto = forms.CharField(
        required=False,
        label="Ou cole o texto do memorial",
        widget=forms.Textarea(attrs={"rows": 6, "class": "ds-textarea"}),
    )
    instrucoes = forms.CharField(
        required=False,
        max_length=2000,
        label="Instruções para a IA (opcional)",
        help_text="Ex.: considere só o lote 2; o piso já é fornecido pelo pavilhão.",
        widget=forms.Textarea(attrs={"rows": 3, "class": "ds-textarea"}),
    )
    incluir_fora_catalogo = forms.BooleanField(
        required=False,
        initial=True,
        label="Incluir itens que não estão no catálogo, com valor zero para eu precificar",
    )
    preencher_evento = forms.BooleanField(
        required=False,
        initial=True,
        label="Preencher dados do evento que estiverem em branco",
    )

    def clean(self):
        # `or {}`: Form.clean() é declarado devolvendo dict | None (mesmo caso
        # documentado em core/concurrency.py).
        dados = super().clean() or {}
        if not dados.get("arquivo") and not (dados.get("texto") or "").strip():
            raise forms.ValidationError("Envie o arquivo do memorial ou cole o texto dele.")
        if dados.get("arquivo") and (dados.get("texto") or "").strip():
            raise forms.ValidationError("Use o arquivo ou o texto colado, não os dois.")
        return dados


class NovoOrcamentoMemorialForm(ImportarMemorialForm):
    """Início rápido: memorial e, opcionalmente, o cliente. O resto vem da IA."""

    cliente: forms.ModelChoiceField = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Cliente",
        empty_label="Identificar pelo memorial",
        help_text="Deixe em branco e a IA usa o órgão do edital, cadastrando se for novo.",
    )

    field_order = ["arquivo", "texto", "cliente", "instrucoes"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from clientes.models import Cliente
        from core.tenancy import queryset_da_empresa

        clientes = Cliente.objects.filter(ativo=True).order_by("nome_razao_social")
        if user is not None:
            clientes = queryset_da_empresa(clientes, user)
        else:
            clientes = clientes.none()
        cast("forms.ModelChoiceField", self.fields["cliente"]).queryset = clientes
