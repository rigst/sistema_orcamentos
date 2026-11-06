"""Cabeçalho Permissions-Policy em todas as respostas (site e admin)."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.testing import SENHA_TESTE

POLITICA_PADRAO = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"
CABECALHO = "Permissions-Policy"


class PermissionsPolicyTests(TestCase):
    def test_rota_publica_tem_o_cabecalho(self):
        resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers.get(CABECALHO), POLITICA_PADRAO)

    def test_login_do_admin_tem_o_cabecalho(self):
        resposta = self.client.get("/admin/login/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers.get(CABECALHO), POLITICA_PADRAO)

    def test_admin_logado_tem_o_cabecalho(self):
        usuario = get_user_model().objects.create_superuser(
            username="admin-pp", email="admin-pp@example.com", password=SENHA_TESTE
        )
        self.client.force_login(usuario)

        resposta = self.client.get("/admin/")

        self.assertEqual(resposta.headers.get(CABECALHO), POLITICA_PADRAO)

    @override_settings(ENABLE_CSP=False)
    def test_independe_da_csp(self):
        resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.headers.get(CABECALHO), POLITICA_PADRAO)

    @override_settings(PERMISSIONS_POLICY="")
    def test_valor_vazio_desliga_o_cabecalho(self):
        resposta = self.client.get(reverse("healthz"))

        self.assertNotIn(CABECALHO, resposta.headers)
