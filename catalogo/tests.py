from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CategoriaItem, ItemCatalogo


class CatalogoPermissaoTests(TestCase):
    def test_orcamentista_nao_pode_criar_item_catalogo(self):
        user = get_user_model().objects.create_user(
            username="orcamentista",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("catalogo:item_criar"))

        self.assertEqual(response.status_code, 403)

    def test_admin_pode_criar_item_catalogo(self):
        user = get_user_model().objects.create_user(
            username="admin",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("catalogo:item_criar"))

        self.assertEqual(response.status_code, 200)

    def test_visualizador_pode_visualizar_item_catalogo(self):
        user = get_user_model().objects.create_user(
            username="visualizador_catalogo",
            password="senha-forte-123",
            perfil="visualizador",
        )
        item = ItemCatalogo.objects.create(
            codigo="VIS-01",
            nome="Item visivel",
            unidade_medida="un",
            valor_unitario_padrao="10.00",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("catalogo:item_visualizar", args=[item.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Item visivel")


class CatalogoValidacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_catalogo",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_item_catalogo_invalido_exibe_erros(self):
        response = self.client.post(
            reverse("catalogo:item_criar"),
            {
                "codigo": "",
                "nome": "",
                "unidade_medida": "un",
                "valor_unitario_padrao": "-1",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe o código do item.")
        self.assertContains(response, "Informe o nome do item.")
        self.assertContains(response, "Informe um valor maior ou igual a zero.")
        self.assertEqual(ItemCatalogo.objects.count(), 0)

    def test_item_catalogo_aceita_valor_formatado_em_pt_br(self):
        response = self.client.post(
            reverse("catalogo:item_criar"),
            {
                "codigo": "SERV-150",
                "nome": "Servico premium",
                "unidade_medida": "un",
                "valor_unitario_padrao": "R$ 15.000,00",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        item = ItemCatalogo.objects.get(codigo="SERV-150")
        self.assertEqual(str(item.valor_unitario_padrao), "15000.00")


class CatalogoListaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="lista_catalogo",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)
        categoria_a = CategoriaItem.objects.create(nome="Categoria A")
        categoria_b = CategoriaItem.objects.create(nome="Categoria B")
        ItemCatalogo.objects.create(
            codigo="B-01",
            nome="Item caro",
            categoria=categoria_b,
            unidade_medida="un",
            valor_unitario_padrao="100.00",
            ativo=True,
        )
        ItemCatalogo.objects.create(
            codigo="A-01",
            nome="Item barato",
            categoria=categoria_a,
            unidade_medida="un",
            valor_unitario_padrao="10.00",
            ativo=False,
        )

    def test_lista_filtra_por_categoria_e_ativo(self):
        categoria = CategoriaItem.objects.get(nome="Categoria B")
        response = self.client.get(
            reverse("catalogo:item_lista"),
            {"categoria": categoria.pk, "ativo": "ativos"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Item caro")
        self.assertNotContains(response, "Item barato")

    def test_lista_ordena_por_preco_maior(self):
        response = self.client.get(reverse("catalogo:item_lista"), {"sort": "preco_maior"})

        self.assertEqual(response.status_code, 200)
        itens = list(response.context["itens"])
        self.assertEqual(itens[0].nome, "Item caro")

    def test_lista_de_itens_e_paginada(self):
        categoria = CategoriaItem.objects.get(nome="Categoria A")
        for indice in range(13):
            ItemCatalogo.objects.create(
                codigo=f"EXTRA-{indice:02d}",
                nome=f"Extra {indice:02d}",
                categoria=categoria,
                unidade_medida="un",
                valor_unitario_padrao="1.00",
            )

        response = self.client.get(reverse("catalogo:item_lista"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_previous())
        self.assertContains(response, "Extra 12")


class CatalogoInativacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_toggle_catalogo",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_item_pode_ser_inativado(self):
        item = ItemCatalogo.objects.create(
            codigo="INAT-01",
            nome="Item ativo",
            unidade_medida="un",
            valor_unitario_padrao="15.00",
        )

        response = self.client.post(reverse("catalogo:item_excluir", args=[item.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Item inativado com sucesso.")
        item.refresh_from_db()
        self.assertFalse(item.ativo)

    def test_categoria_pode_ser_inativada(self):
        categoria = CategoriaItem.objects.create(nome="Categoria ativa")

        response = self.client.post(reverse("catalogo:categoria_excluir", args=[categoria.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Categoria inativada com sucesso.")
        categoria.refresh_from_db()
        self.assertFalse(categoria.ativo)
