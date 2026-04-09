from django import forms

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
