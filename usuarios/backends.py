"""Backend de autenticação com a trava de tentativas.

Fica no backend, e não só no formulário da tela de login, para valer em toda
porta de entrada por senha: a tela /login/, o /admin/ e qualquer outra que use
`authenticate()`.
"""

from __future__ import annotations

from django.contrib.auth.backends import ModelBackend

from legal.utils import ip_do_request

from .protecao_login import segundos_de_bloqueio


class BackendComTrava(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(self._campo_usuario())
        ip = ip_do_request(request) if request is not None else ""
        if segundos_de_bloqueio(username, ip):
            # Nem confere a senha: durante o bloqueio, acertar não adianta.
            return None
        return super().authenticate(request, username=username, password=password, **kwargs)

    @staticmethod
    def _campo_usuario() -> str:
        from django.contrib.auth import get_user_model

        return get_user_model().USERNAME_FIELD
