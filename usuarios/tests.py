from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdminPermissaoPerfilTests(TestCase):
    def criar_usuario(self, username, perfil):
        return get_user_model().objects.create_user(
            username=username,
            password="senha-forte-123",
            perfil=perfil,
            is_staff=True,
        )

    def test_admin_tem_acesso_ao_admin_de_usuarios(self):
        user = self.criar_usuario("admin", "admin")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:usuarios_usuario_changelist"))

        self.assertEqual(response.status_code, 200)

    def test_orcamentista_nao_tem_acesso_ao_admin_de_usuarios(self):
        user = self.criar_usuario("orcamentista", "orcamentista")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:usuarios_usuario_changelist"))

        self.assertEqual(response.status_code, 403)

    def test_orcamentista_pode_gerenciar_clientes_no_admin(self):
        user = self.criar_usuario("orc_clientes", "orcamentista")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:clientes_cliente_add"))

        self.assertEqual(response.status_code, 200)

    def test_orcamentista_nao_pode_gerenciar_catalogo_no_admin(self):
        user = self.criar_usuario("orc_catalogo", "orcamentista")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:catalogo_itemcatalogo_add"))

        self.assertEqual(response.status_code, 403)

    def test_visualizador_pode_ver_orcamentos_no_admin_mas_nao_criar(self):
        user = self.criar_usuario("visualizador", "visualizador")
        self.client.force_login(user)

        changelist_response = self.client.get(reverse("admin:orcamentos_orcamento_changelist"))
        add_response = self.client.get(reverse("admin:orcamentos_orcamento_add"))

        self.assertEqual(changelist_response.status_code, 200)
        self.assertEqual(add_response.status_code, 403)


class UsuarioPermissaoPropriedadesTests(TestCase):
    def test_admin_tem_capacidades_de_gestao(self):
        user = get_user_model().objects.create_user(
            username="admin_props",
            password="senha-forte-123",
            perfil="admin",
        )

        self.assertTrue(user.pode_gerenciar_clientes)
        self.assertTrue(user.pode_gerenciar_catalogo)
        self.assertTrue(user.pode_gerenciar_relatorios)
        self.assertTrue(user.pode_gerenciar_orcamentos)

    def test_visualizador_fica_apenas_com_visualizacao(self):
        user = get_user_model().objects.create_user(
            username="vis_props",
            password="senha-forte-123",
            perfil="visualizador",
        )

        self.assertTrue(user.pode_visualizar_clientes)
        self.assertTrue(user.pode_visualizar_catalogo)
        self.assertTrue(user.pode_visualizar_relatorios)
        self.assertTrue(user.pode_visualizar_orcamentos)
        self.assertFalse(user.pode_gerenciar_clientes)
        self.assertFalse(user.pode_gerenciar_catalogo)
        self.assertFalse(user.pode_gerenciar_relatorios)
        self.assertFalse(user.pode_gerenciar_orcamentos)


class UsuarioVisitanteTests(TestCase):
    def test_login_como_visitante_cria_usuario_temporario_e_remove_no_logout(self):
        response = self.client.post(reverse("login"), {"entrar_visitante": "1"})

        self.assertEqual(response.status_code, 302)
        visitante = get_user_model().objects.get(perfil="visitante")
        grupo = visitante.groups.get()
        self.assertTrue(grupo.name.startswith("__visitante__"))

        self.client.post(reverse("logout"))

        self.assertFalse(get_user_model().objects.filter(pk=visitante.pk).exists())
        self.assertFalse(Group.objects.filter(pk=grupo.pk).exists())
