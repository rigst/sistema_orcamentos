"""Recuperação de senha por e-mail ("Esqueci minha senha").

Usa o fluxo do Django (token assinado, de uso único, que expira), com três
cuidados a mais:

- só funciona com e-mail configurado (`DJANGO_EMAIL_HOST`); sem ele, a tela
  explica que é preciso falar com o administrador, em vez de fingir que mandou;
- limite de pedidos por IP, para a tela não virar disparador de e-mail;
- contas de visitante ficam de fora (são temporárias e não têm e-mail).

A resposta é sempre a mesma, exista ou não o e-mail informado, para a tela não
revelar quem tem conta no sistema.
"""

from __future__ import annotations

import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from legal.utils import ip_do_request

logger = logging.getLogger(__name__)


def email_configurado() -> bool:
    return bool(getattr(settings, "RECUPERACAO_SENHA_ATIVA", False))


def _limite_pedidos() -> int:
    try:
        return max(int(os.getenv("DJANGO_SENHA_PEDIDOS_POR_HORA", "5")), 1)
    except ValueError:
        return 5


def _excedeu_e_conta(ip: str) -> bool:
    chave = f"senha:pedidos:{ip or 'desconhecido'}"
    if cache.add(chave, 1, timeout=3600):
        return False
    try:
        pedidos = cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, timeout=3600)
        return False
    return pedidos > _limite_pedidos()


class RecuperarSenhaForm(PasswordResetForm):
    def get_users(self, email):
        for usuario in super().get_users(email):
            if getattr(usuario, "eh_visitante", False):
                continue
            yield usuario


class PedirNovaSenhaView(auth_views.PasswordResetView):
    template_name = "registration/senha_pedir.html"
    email_template_name = "registration/senha_email.txt"
    html_email_template_name = "registration/senha_email.html"
    subject_template_name = "registration/senha_email_assunto.txt"
    form_class = RecuperarSenhaForm
    success_url = reverse_lazy("senha_enviada")

    def dispatch(self, request, *args, **kwargs):
        if not email_configurado():
            return render(request, "registration/senha_indisponivel.html", status=503)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if _excedeu_e_conta(ip_do_request(self.request)):
            logger.warning(
                "Limite de pedidos de nova senha excedido",
                extra={"ip": ip_do_request(self.request)},
            )
            messages.error(
                self.request,
                "Muitos pedidos de nova senha em pouco tempo. Aguarde um pouco e tente de novo.",
            )
            return redirect("senha_pedir")
        return super().form_valid(form)


class SenhaEnviadaView(auth_views.PasswordResetDoneView):
    template_name = "registration/senha_enviada.html"


class DefinirNovaSenhaView(auth_views.PasswordResetConfirmView):
    template_name = "registration/senha_definir.html"
    success_url = reverse_lazy("senha_concluida")
    # Depois de trocar, a pessoa entra de novo com a senha nova (sessões antigas
    # caem, porque o hash de sessão muda junto com a senha).
    post_reset_login = False


class SenhaConcluidaView(auth_views.PasswordResetCompleteView):
    template_name = "registration/senha_concluida.html"
