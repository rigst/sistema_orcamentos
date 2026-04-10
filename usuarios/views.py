import secrets

from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse

from core.tenancy import nome_grupo_visitante
from .models import Usuario


class UsuarioLoginView(LoginView):
    template_name = "registration/login.html"

    def post(self, request, *args, **kwargs):
        if "entrar_visitante" in request.POST:
            return self.criar_e_logar_visitante()
        return super().post(request, *args, **kwargs)

    def criar_e_logar_visitante(self):
        token = secrets.token_hex(4)
        username = f"visitante_{token}"
        grupo = Group.objects.create(name=nome_grupo_visitante(username))
        usuario = Usuario.objects.create_user(
            username=username,
            password=secrets.token_urlsafe(24),
            perfil="visitante",
            nome_exibicao=f"Visitante {token.upper()}",
        )
        usuario.groups.add(grupo)
        login(self.request, usuario)
        return redirect(reverse("dashboard"))


class UsuarioLogoutView(LogoutView):
    pass
