"""Trava de login, recuperação de senha e limpeza de visitantes."""

from __future__ import annotations

import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.testing import SENHA_TESTE
from orcamentos.models import Orcamento

from . import protecao_login
from .visitantes import limpar_visitantes_expirados

ERRADA = SENHA_TESTE + "-errada"


class TravaDeLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = get_user_model().objects.create_user(
            username="maria", password=SENHA_TESTE, email="maria@exemplo.com"
        )

    def _tentar(self, senha, username="maria", ip="203.0.113.10"):
        return self.client.post(
            reverse("login"),
            {"username": username, "password": senha},
            REMOTE_ADDR=ip,
        )

    def test_bloqueia_a_conta_depois_de_cinco_erros_mesmo_com_a_senha_certa(self):
        for _ in range(5):
            self._tentar(ERRADA)
        resposta = self._tentar(SENHA_TESTE)
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(resposta, "Muitas tentativas de login sem sucesso")

    def test_quatro_erros_ainda_deixam_entrar_e_o_acerto_zera_a_contagem(self):
        for _ in range(4):
            self._tentar(ERRADA)
        self.assertEqual(self._tentar(SENHA_TESTE).status_code, 302)
        self.client.logout()
        for _ in range(4):
            self._tentar(ERRADA)
        self.assertEqual(self._tentar(SENHA_TESTE).status_code, 302)

    def test_trava_por_usuario_vale_de_outro_ip_e_ignora_maiusculas(self):
        for n in range(5):
            self._tentar(ERRADA, username="MARIA", ip=f"198.51.100.{n}")
        resposta = self._tentar(SENHA_TESTE, ip="192.0.2.99")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(resposta, "Muitas tentativas")

    def test_trava_por_ip_segura_quem_testa_varios_usuarios(self):
        for n in range(20):
            self._tentar(ERRADA, username=f"chute{n}")
        resposta = self._tentar(SENHA_TESTE)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(resposta, "Muitas tentativas")
        # Outro IP entra normalmente.
        self.assertEqual(self._tentar(SENHA_TESTE, ip="192.0.2.50").status_code, 302)

    def test_bloqueio_expira_e_nao_se_estende_com_novas_tentativas(self):
        agora = 1_000_000.0
        with mock.patch.object(protecao_login.time, "time", return_value=agora):
            for _ in range(8):
                self._tentar(ERRADA)
        with mock.patch.object(protecao_login.time, "time", return_value=agora + 600):
            self._tentar(ERRADA)  # durante o bloqueio
            self.assertGreater(protecao_login.segundos_de_bloqueio("maria", "203.0.113.10"), 0)
        with mock.patch.object(protecao_login.time, "time", return_value=agora + 901):
            self.assertEqual(protecao_login.segundos_de_bloqueio("maria", "203.0.113.10"), 0)

    def test_trava_vale_tambem_para_authenticate_direto_como_no_admin(self):
        for _ in range(5):
            self.assertIsNone(authenticate(username="maria", password=ERRADA))
        self.assertIsNone(authenticate(username="maria", password=SENHA_TESTE))

    def test_mensagem_de_bloqueio_em_minutos(self):
        self.assertIn("1 minuto", protecao_login.mensagem_bloqueio(30))
        self.assertIn("15 minutos", protecao_login.mensagem_bloqueio(900))


class RecuperacaoDeSenhaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = get_user_model().objects.create_user(
            username="joao", password=SENHA_TESTE, email="joao@exemplo.com"
        )

    def test_login_mostra_o_link_de_esqueci_a_senha(self):
        resposta = self.client.get(reverse("login"))
        self.assertContains(resposta, reverse("senha_pedir"))

    @override_settings(RECUPERACAO_SENHA_ATIVA=False)
    def test_sem_email_configurado_a_tela_avisa_e_o_link_some(self):
        self.assertNotContains(self.client.get(reverse("login")), reverse("senha_pedir"))
        resposta = self.client.get(reverse("senha_pedir"))
        self.assertEqual(resposta.status_code, 503)
        self.assertContains(resposta, "fale com o administrador", status_code=503)

    def test_fluxo_completo_troca_a_senha_e_derruba_a_sessao_antiga(self):
        antiga = self.client_class()
        antiga.force_login(self.usuario)

        resposta = self.client.post(reverse("senha_pedir"), {"email": "JOAO@exemplo.com"})
        self.assertRedirects(resposta, reverse("senha_enviada"))
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["joao@exemplo.com"])
        self.assertIn("Nova senha", email.subject)
        self.assertTrue(email.alternatives)  # versão em HTML junto do texto
        link = re.search(r"https?://[^/]+(/senha/nova/\S+)", email.body).group(1)

        tela = self.client.get(link, follow=True)
        self.assertContains(tela, "Crie uma senha nova")
        nova = "Montagem-de-estande-2026"
        resposta = self.client.post(
            tela.redirect_chain[-1][0],
            {"new_password1": nova, "new_password2": nova},
        )
        self.assertRedirects(resposta, reverse("senha_concluida"))

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(nova))
        # Sessão aberta com a senha antiga cai.
        self.assertNotEqual(antiga.get(reverse("orcamentos:lista")).status_code, 200)
        # O link não funciona de novo.
        self.assertContains(self.client.get(link, follow=True), "Link expirado")

    def test_email_desconhecido_tem_a_mesma_resposta_e_nao_envia_nada(self):
        resposta = self.client.post(reverse("senha_pedir"), {"email": "ninguem@exemplo.com"})
        self.assertRedirects(resposta, reverse("senha_enviada"))
        self.assertEqual(mail.outbox, [])

    def test_visitante_nao_recebe_link(self):
        get_user_model().objects.create_user(
            username="visitante_ab", password=SENHA_TESTE, email="v@exemplo.com", perfil="visitante"
        )
        self.client.post(reverse("senha_pedir"), {"email": "v@exemplo.com"})
        self.assertEqual(mail.outbox, [])

    def test_limite_de_pedidos_por_ip(self):
        for _ in range(5):
            self.client.post(reverse("senha_pedir"), {"email": "joao@exemplo.com"})
        resposta = self.client.post(
            reverse("senha_pedir"), {"email": "joao@exemplo.com"}, follow=True
        )
        self.assertContains(resposta, "Muitos pedidos de nova senha")
        self.assertEqual(len(mail.outbox), 5)


class LimpezaDeVisitantesTests(TestCase):
    def _visitante(self, nome, horas_atras):
        from core.tenancy import nome_grupo_visitante

        usuario = get_user_model().objects.create_user(
            username=nome, password=SENHA_TESTE, perfil="visitante"
        )
        grupo = Group.objects.create(name=nome_grupo_visitante(nome))
        usuario.groups.set([grupo])
        get_user_model().objects.filter(pk=usuario.pk).update(
            criado_em=timezone.now() - timedelta(hours=horas_atras)
        )
        Orcamento.objects.create(
            titulo=f"Orçamento de {nome}",
            empresa=grupo,
            criado_por=usuario,
            atualizado_por=usuario,
        )
        return usuario, grupo

    def test_comando_apaga_so_os_vencidos_com_tudo_o_que_criaram(self):
        velho, grupo_velho = self._visitante("visitante_velho", 30)
        novo, grupo_novo = self._visitante("visitante_novo", 2)

        call_command("limpar_visitantes_expirados", stdout=mock.MagicMock())

        usuarios = get_user_model().objects
        self.assertFalse(usuarios.filter(pk=velho.pk).exists())
        self.assertFalse(Group.objects.filter(pk=grupo_velho.pk).exists())
        self.assertFalse(Orcamento.objects.filter(empresa_id=grupo_velho.pk).exists())
        self.assertTrue(usuarios.filter(pk=novo.pk).exists())
        self.assertTrue(Orcamento.objects.filter(empresa=grupo_novo).exists())

    def test_um_visitante_com_erro_nao_impede_os_outros(self):
        primeiro, _ = self._visitante("visitante_a", 30)
        segundo, _ = self._visitante("visitante_b", 31)
        original = __import__("usuarios.visitantes", fromlist=["x"]).limpar_dados_visitante

        def falha_no_b(usuario):
            if usuario.username == "visitante_b":
                raise RuntimeError("dado travado")
            original(usuario)

        with (
            mock.patch("usuarios.visitantes.limpar_dados_visitante", side_effect=falha_no_b),
            self.assertLogs("usuarios.visitantes", level="ERROR"),
        ):
            total = limpar_visitantes_expirados()

        self.assertEqual(total, 1)
        self.assertFalse(get_user_model().objects.filter(pk=primeiro.pk).exists())
        # O que falhou continua inteiro (a transação dele voltou atrás).
        self.assertTrue(get_user_model().objects.filter(pk=segundo.pk).exists())
        self.assertTrue(Orcamento.objects.filter(criado_por=segundo).exists())

    def test_usuario_normal_antigo_nunca_e_apagado(self):
        normal = get_user_model().objects.create_user(username="dono", password=SENHA_TESTE)
        get_user_model().objects.filter(pk=normal.pk).update(
            criado_em=timezone.now() - timedelta(days=400)
        )
        limpar_visitantes_expirados()
        self.assertTrue(get_user_model().objects.filter(pk=normal.pk).exists())
