from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from orcamentos.models import Orcamento
from .models import Cliente


class ClientePermissaoTests(TestCase):
    def test_visualizador_nao_pode_criar_cliente(self):
        user = get_user_model().objects.create_user(
            username="visualizador",
            password="senha-forte-123",
            perfil="visualizador",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("clientes:criar"))

        self.assertEqual(response.status_code, 403)

    def test_visualizador_nao_pode_excluir_cliente(self):
        user = get_user_model().objects.create_user(
            username="visualizador_delete",
            password="senha-forte-123",
            perfil="visualizador",
        )
        cliente = Cliente.objects.create(nome_razao_social="Cliente Bloqueado")
        self.client.force_login(user)

        response = self.client.get(reverse("clientes:excluir", args=[cliente.pk]))

        self.assertEqual(response.status_code, 403)


class ClienteValidacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="orc_clientes",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(self.user)

    def test_cliente_invalido_exibe_erros_amigaveis(self):
        response = self.client.post(
            reverse("clientes:criar"),
            {
                "tipo_pessoa": "PF",
                "nome_razao_social": "",
                "cpf_cnpj": "123",
                "telefone": "9999",
                "celular": "8888",
                "cep": "123",
                "estado": "XX",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe o nome ou razão social.")
        self.assertContains(response, "Informe um CPF com 11 dígitos ou um CNPJ com 14 dígitos.")
        self.assertContains(response, "Telefone deve ter 10 ou 11 dígitos, incluindo DDD.")
        self.assertContains(response, "Celular deve ter 10 ou 11 dígitos, incluindo DDD.")
        self.assertContains(response, "CEP deve ter 8 dígitos.")
        self.assertContains(response, "Informe uma UF válida com duas letras.")
        self.assertEqual(Cliente.objects.count(), 0)

    def test_cliente_aceita_campos_com_mascara_e_salva_formatado(self):
        response = self.client.post(
            reverse("clientes:criar"),
            {
                "tipo_pessoa": "PJ",
                "nome_razao_social": "Cliente Mascara",
                "cpf_cnpj": "12.345.678/0001-90",
                "telefone": "(11) 3333-4444",
                "celular": "(11) 98888-7777",
                "cep": "01310-100",
                "estado": "SP",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        cliente = Cliente.objects.get(nome_razao_social="Cliente Mascara")
        self.assertEqual(cliente.cpf_cnpj, "12.345.678/0001-90")
        self.assertEqual(cliente.telefone, "(11) 3333-4444")
        self.assertEqual(cliente.celular, "(11) 98888-7777")
        self.assertEqual(cliente.cep, "01310-100")


class ClienteListaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="lista_clientes",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(self.user)
        Cliente.objects.create(nome_razao_social="Cliente Ativo", cidade="Sao Paulo", ativo=True)
        Cliente.objects.create(nome_razao_social="Cliente Inativo", cidade="Campinas", ativo=False)

    def test_lista_filtra_por_status_ativo(self):
        response = self.client.get(reverse("clientes:lista"), {"ativo": "ativos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente Ativo")
        self.assertNotContains(response, "Cliente Inativo")

    def test_lista_ordena_por_cidade(self):
        response = self.client.get(reverse("clientes:lista"), {"sort": "cidade"})

        self.assertEqual(response.status_code, 200)
        clientes = list(response.context["clientes"])
        self.assertEqual(clientes[0].cidade, "Campinas")

    def test_lista_de_clientes_e_paginada(self):
        for indice in range(13):
            Cliente.objects.create(nome_razao_social=f"Cliente Extra {indice:02d}")

        response = self.client.get(reverse("clientes:lista"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_previous())
        self.assertContains(response, "Cliente Extra 12")


class ClienteExclusaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="gerente_clientes",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(self.user)

    def test_cliente_pode_ser_inativado_por_orcamentista(self):
        cliente = Cliente.objects.create(nome_razao_social="Cliente Excluir")

        response = self.client.post(reverse("clientes:excluir", args=[cliente.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente inativado com sucesso.")
        cliente.refresh_from_db()
        self.assertFalse(cliente.ativo)

    def test_cliente_pode_ser_reativado(self):
        cliente = Cliente.objects.create(nome_razao_social="Cliente Vinculado")
        Orcamento.objects.create(
            numero="ORC-CLI-0001",
            cliente=cliente,
            titulo="Orçamento vinculado",
            data_emissao="2026-04-09",
            criado_por=self.user,
            atualizado_por=self.user,
        )

        response = self.client.post(reverse("clientes:excluir", args=[cliente.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        cliente.refresh_from_db()
        self.assertFalse(cliente.ativo)

        response = self.client.post(reverse("clientes:excluir", args=[cliente.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente reativado com sucesso.")
        cliente.refresh_from_db()
        self.assertTrue(cliente.ativo)
