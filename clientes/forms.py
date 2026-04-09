from django import forms
from .models import Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "tipo_pessoa",
            "nome_razao_social",
            "nome_fantasia",
            "cpf_cnpj",
            "email",
            "telefone",
            "celular",
            "contato_responsavel",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "observacoes",
            "ativo",
        ]
