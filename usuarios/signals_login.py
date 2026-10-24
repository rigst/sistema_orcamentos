"""Conta falhas e acertos de login para a trava de tentativas."""

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from legal.utils import ip_do_request

from .protecao_login import limpar_falhas, registrar_falha


@receiver(user_login_failed)
def contar_falha_de_login(sender, credentials, request=None, **kwargs):
    ip = ip_do_request(request) if request is not None else ""
    registrar_falha(credentials.get("username"), ip)


@receiver(user_logged_in)
def zerar_falhas_no_login(sender, request, user, **kwargs):
    if getattr(user, "eh_visitante", False):
        return
    limpar_falhas(user.get_username())
