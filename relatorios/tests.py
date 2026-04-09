from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from decimal import Decimal

from clientes.models import Cliente
from orcamentos.models import ItemOrcamento, Orcamento
from .models import ConfiguracaoEmpresa


class RelatoriosPermissaoTests(TestCase):
    def test_orcamentista_nao_pode_criar_configuracao_empresa(self):
        user = get_user_model().objects.create_user(
            username="orcamentista",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("relatorios:configuracao_criar"))

        self.assertEqual(response.status_code, 403)

    def test_visualizador_pode_visualizar_configuracao(self):
        user = get_user_model().objects.create_user(
            username="visualizador_empresa",
            password="senha-forte-123",
            perfil="visualizador",
        )
        configuracao = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Visivel")
        self.client.force_login(user)

        response = self.client.get(reverse("relatorios:configuracao_visualizar", args=[configuracao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Empresa Visivel")


class RelatoriosExportacaoTests(TestCase):
    def gerar_logo_teste(self):
        buffer = BytesIO()
        Image.new("RGB", (180, 60), color=(80, 140, 220)).save(buffer, format="PNG")
        return SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="orcamentista_export",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(self.user)

        self.cliente = Cliente.objects.create(nome_razao_social="Cliente Exportacao")
        self.orcamento = Orcamento.objects.create(
            numero="ORC-REL-0001",
            cliente=self.cliente,
            titulo="Relatorio profissional",
            status="rascunho",
            data_emissao="2026-04-09",
            criado_por=self.user,
            atualizado_por=self.user,
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            ordem=1,
            codigo_item="REL-1",
            nome="Servico relatorio",
            unidade_medida="un",
            quantidade=Decimal("1"),
            valor_unitario=Decimal("15000.00"),
        )
        self.orcamento.refresh_from_db()
        ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa Exemplo",
            logo=self.gerar_logo_teste(),
        )

    def test_central_de_relatorio_mostra_alerta_de_status(self):
        response = self.client.get(reverse("relatorios:orcamento_central", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Orçamento em rascunho")
        self.assertContains(response, "Logo da empresa")
        self.assertContains(response, "R$ 15.000,00")

    def test_exportacao_excel_retorna_arquivo(self):
        response = self.client.get(reverse("relatorios:orcamento_excel", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.ms-excel")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(b"Or\xc3\xa7amento em rascunho", response.content)

    def test_exportacao_pdf_retorna_arquivo(self):
        response = self.client.get(reverse("relatorios:orcamento_pdf", args=[self.orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Subtype /Image", response.content)


class RelatoriosValidacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_relatorios",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_configuracao_empresa_invalida_exibe_erros(self):
        response = self.client.post(
            reverse("relatorios:configuracao_criar"),
            {
                "nome_empresa": "",
                "cpf_cnpj": "123",
                "telefone": "9999",
                "cep": "123",
                "estado": "XX",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe o nome da empresa.")
        self.assertContains(response, "Informe um CPF com 11 dígitos ou um CNPJ com 14 dígitos.")
        self.assertContains(response, "Telefone deve ter 10 ou 11 dígitos, incluindo DDD.")
        self.assertContains(response, "CEP deve ter 8 dígitos.")
        self.assertContains(response, "Informe uma UF válida com duas letras.")

    def test_configuracao_empresa_aceita_campos_com_mascara(self):
        response = self.client.post(
            reverse("relatorios:configuracao_criar"),
            {
                "nome_empresa": "Empresa Formatada",
                "cpf_cnpj": "12.345.678/0001-90",
                "telefone": "(11) 4002-8922",
                "cep": "01310-100",
                "estado": "SP",
            },
        )

        self.assertEqual(response.status_code, 302)
        configuracao = ConfiguracaoEmpresa.objects.get(nome_empresa="Empresa Formatada")
        self.assertEqual(configuracao.cpf_cnpj, "12.345.678/0001-90")
        self.assertEqual(configuracao.telefone, "(11) 4002-8922")
        self.assertEqual(configuracao.cep, "01310-100")


class RelatoriosListaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_lista_rel",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)
        ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa B", cidade="Rio de Janeiro")
        ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa A", cidade="Campinas")

    def test_lista_filtra_por_nome(self):
        response = self.client.get(reverse("relatorios:configuracao_lista"), {"q": "Empresa B"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Empresa B")
        self.assertNotContains(response, "Empresa A")

    def test_lista_ordena_por_nome(self):
        response = self.client.get(reverse("relatorios:configuracao_lista"), {"sort": "nome"})

        self.assertEqual(response.status_code, 200)
        configuracoes = list(response.context["configuracoes"])
        self.assertEqual(configuracoes[0].nome_empresa, "Empresa A")

    def test_lista_de_configuracoes_e_paginada(self):
        for indice in range(11):
            ConfiguracaoEmpresa.objects.create(nome_empresa=f"Empresa Extra {indice:02d}")

        response = self.client.get(reverse("relatorios:configuracao_lista"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_previous())
        self.assertContains(response, "Empresa Extra 00")


class RelatoriosInativacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_toggle_empresa",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_configuracao_pode_ser_inativada(self):
        configuracao = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Toggle")

        response = self.client.post(reverse("relatorios:configuracao_excluir", args=[configuracao.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Configuração inativada com sucesso.")
        configuracao.refresh_from_db()
        self.assertFalse(configuracao.ativo)


class RelatoriosAtualizacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_edita_empresa",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_formulario_de_edicao_exibe_aviso_sobre_orcamentos_nao_enviados(self):
        configuracao = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Base")

        response = self.client.get(reverse("relatorios:configuracao_editar", args=[configuracao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "orçamentos ainda não enviados")

    def test_edicao_de_configuracao_exibe_mensagem_de_propagacao(self):
        configuracao = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa Base")

        response = self.client.post(
            reverse("relatorios:configuracao_editar", args=[configuracao.pk]),
            {
                "nome_empresa": "Empresa Atualizada",
                "nome_fantasia": configuracao.nome_fantasia,
                "cpf_cnpj": configuracao.cpf_cnpj,
                "email": configuracao.email,
                "telefone": configuracao.telefone,
                "site": configuracao.site,
                "cep": configuracao.cep,
                "logradouro": configuracao.logradouro,
                "numero": configuracao.numero,
                "complemento": configuracao.complemento,
                "bairro": configuracao.bairro,
                "cidade": configuracao.cidade,
                "estado": configuracao.estado,
                "rodape_relatorio": configuracao.rodape_relatorio,
                "ativo": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Os relatórios e os orçamentos ainda não enviados passam a usar essas informações.",
        )
