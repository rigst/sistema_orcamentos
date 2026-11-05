"""Sonda /healthz/: toca banco e cache e responde 200 ou 503 (RUNBOOK 7.8)."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.testing import SENHA_TESTE
from legal.models import DocumentoLegal, TipoDocumento

TOKEN = "segredo-monitoramento"


class HealthzTests(TestCase):
    def test_tudo_ok_responde_200(self):
        resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 200)
        self.assertJSONEqual(resposta.content, {"status": "ok"})
        self.assertIn("no-cache", resposta.headers.get("Cache-Control", ""))

    def test_banco_fora_responde_503(self):
        with (
            mock.patch("core.views.connection.cursor", side_effect=OperationalError("banco fora")),
            self.assertLogs("core.views", level="ERROR") as logs,
        ):
            resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 503)
        self.assertJSONEqual(resposta.content, {"status": "indisponivel"})
        self.assertIn("banco", logs.output[0])

    def test_cache_fora_responde_503(self):
        with (
            mock.patch("core.views.cache.set", side_effect=ConnectionError("redis fora")),
            self.assertLogs("core.views", level="ERROR") as logs,
        ):
            resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 503)
        self.assertIn("cache", logs.output[0])

    def test_cache_que_nao_guarda_responde_503(self):
        with (
            mock.patch("core.views.cache.get", return_value=None),
            self.assertLogs("core.views", level="ERROR"),
        ):
            resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 503)

    @override_settings(HEALTHZ_TOKEN=TOKEN)
    def test_token_continua_exigido_antes_das_checagens(self):
        with mock.patch("core.views.connection.cursor") as cursor:
            sem_token = self.client.get(reverse("healthz"))
            token_errado = self.client.get(reverse("healthz"), HTTP_X_HEALTHZ_TOKEN="errado")
        cursor.assert_not_called()

        com_token = self.client.get(reverse("healthz"), HTTP_X_HEALTHZ_TOKEN=TOKEN)

        self.assertEqual(sem_token.status_code, 404)
        self.assertEqual(token_errado.status_code, 404)
        self.assertEqual(com_token.status_code, 200)
        self.assertJSONEqual(com_token.content, {"status": "ok"})

    def test_aceite_de_termos_pendente_nao_intercepta(self):
        """Sessão com termos pendentes não pode virar 302 para /legal/reaceite/."""
        documento = DocumentoLegal.objects.create(
            tipo=TipoDocumento.TERMOS,
            versao="1.0",
            titulo="Termos",
            corpo_md="# T\n",
            material=True,
        )
        documento.publicar()
        usuario = get_user_model().objects.create_user(username="ana", password=SENHA_TESTE)
        self.client.force_login(usuario)

        resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 200)

    def test_head_tambem_responde(self):
        self.assertEqual(self.client.head(reverse("healthz")).status_code, 200)
