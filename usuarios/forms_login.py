"""Formulário de login que avisa quando o acesso está pausado pela trava."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from legal.utils import ip_do_request

from .protecao_login import mensagem_bloqueio, segundos_de_bloqueio


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Usuário ou senha inválidos.",
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        ip = ip_do_request(self.request) if self.request is not None else ""
        restante = segundos_de_bloqueio(username, ip)
        if restante:
            raise forms.ValidationError(mensagem_bloqueio(restante), code="bloqueado")
        return super().clean()
