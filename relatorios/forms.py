from django import forms

from core.form_fields import configurar_campo_mascarado
from core.formatting import formatar_cep_br, formatar_cpf_cnpj_br, formatar_telefone_br
from core.validators import (
    validar_cep_basico,
    validar_cpf_cnpj_basico,
    validar_telefone_basico,
    validar_uf,
)
from .models import ConfiguracaoEmpresa


class ConfiguracaoEmpresaForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoEmpresa
        fields = [
            "nome_empresa",
            "nome_fantasia",
            "cpf_cnpj",
            "email",
            "telefone",
            "site",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "rodape_relatorio",
            "logo",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ativo"].widget = forms.HiddenInput()
        self.fields["ativo"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativo
        self.fields["nome_empresa"].error_messages["required"] = "Informe o nome da empresa."
        configurar_campo_mascarado(self, "cpf_cnpj", "cpf_cnpj", placeholder="00.000.000/0000-00")
        configurar_campo_mascarado(self, "telefone", "phone", placeholder="(00) 00000-0000")
        configurar_campo_mascarado(self, "cep", "cep", placeholder="00000-000")
        self.fields["estado"].widget.attrs["data-force-uppercase"] = "1"
        self.fields["rodape_relatorio"].widget.attrs["rows"] = 3

    def clean_nome_empresa(self):
        valor = (self.cleaned_data.get("nome_empresa") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome da empresa.")
        return valor

    def clean_cpf_cnpj(self):
        valor = (self.cleaned_data.get("cpf_cnpj") or "").strip()
        validar_cpf_cnpj_basico(valor)
        return formatar_cpf_cnpj_br(valor)

    def clean_telefone(self):
        valor = (self.cleaned_data.get("telefone") or "").strip()
        validar_telefone_basico(valor, campo="Telefone")
        return formatar_telefone_br(valor)

    def clean_cep(self):
        valor = (self.cleaned_data.get("cep") or "").strip()
        validar_cep_basico(valor)
        return formatar_cep_br(valor)

    def clean_estado(self):
        valor = (self.cleaned_data.get("estado") or "").strip().upper()
        validar_uf(valor)
        return valor
