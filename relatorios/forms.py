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
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome_empresa"].error_messages["required"] = "Informe o nome da empresa."
        self.fields["nome_empresa"].help_text = "Obrigatório."
        self.fields["cpf_cnpj"].help_text = "Opcional. Se informado, use CPF ou CNPJ em formato básico."
        self.fields["telefone"].help_text = "Opcional. Informe com DDD."
        self.fields["cep"].help_text = "Opcional. Informe 8 dígitos."
        self.fields["estado"].help_text = "Opcional. Use a sigla da UF."
        configurar_campo_mascarado(self, "cpf_cnpj", "cpf_cnpj", placeholder="00.000.000/0000-00")
        configurar_campo_mascarado(self, "telefone", "phone", placeholder="(00) 00000-0000")
        configurar_campo_mascarado(self, "cep", "cep", placeholder="00000-000")

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
