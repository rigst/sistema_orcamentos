"""Caminhos de exceção e de retentativa que os testes de fluxo não alcançam.

São três coisas que só acontecem quando algo dá errado — colisão de código
gerado em gravação concorrente, planilha com linha inválida, upload de logo
corrompido. Nenhuma delas aparece num teste de caminho feliz, e todas rodam em
produção no dia em que dois usuários salvam ao mesmo tempo ou alguém arrasta o
arquivo errado.
"""

from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase

from catalogo.models import ItemCatalogo
from catalogo.services import _formatar_erro_validacao
from clientes.models import Cliente
from core.tenancy import VISITOR_GROUP_PREFIX
from core.testing import SENHA_TESTE
from orcamentos.models import Orcamento
from relatorios.forms import ConfiguracaoEmpresaForm
from relatorios.models import ConfiguracaoEmpresa

Usuario = get_user_model()


class CodigoAutomaticoSobColisaoTests(TestCase):
    """O `save()` refaz o código quando dois registros disputam o mesmo número.

    O código é gerado a partir do maior existente, então duas gravações
    simultâneas chegam ao mesmo valor e a constraint de unicidade derruba uma.
    A retentativa existe para isso, e é justamente o trecho que nenhum teste de
    caminho feliz executa.
    """

    def test_item_de_catalogo_tenta_de_novo_apos_colisao(self):
        item = ItemCatalogo(nome="Item", unidade_medida="un", valor_unitario_padrao=Decimal("1.00"))
        chamadas = {"n": 0}
        real = ItemCatalogo.definir_codigo_automatico

        def falhar_na_primeira(self):
            real(self)
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise IntegrityError("itemcatalogo_empresa_codigo_uniq")

        with patch.object(ItemCatalogo, "definir_codigo_automatico", falhar_na_primeira):
            item.save()

        self.assertEqual(chamadas["n"], 2, "a segunda tentativa não aconteceu")
        self.assertTrue(ItemCatalogo.objects.filter(pk=item.pk).exists())

    def test_item_de_catalogo_propaga_erro_de_integridade_alheio(self):
        """Colisão de código se resolve com outra tentativa; o resto, não."""
        item = ItemCatalogo(nome="Item", unidade_medida="un", valor_unitario_padrao=Decimal("1.00"))

        with (
            patch.object(
                ItemCatalogo,
                "definir_codigo_automatico",
                side_effect=IntegrityError("outra constraint qualquer"),
                autospec=True,
            ),
            self.assertRaises(IntegrityError),
        ):
            item.save()

    def test_orcamento_tenta_de_novo_apos_colisao(self):
        usuario = Usuario.objects.create_user(username="autor", password=SENHA_TESTE)
        cliente = Cliente.objects.create(nome_razao_social="Cliente")
        orcamento = Orcamento(
            titulo="Proposta",
            cliente=cliente,
            criado_por=usuario,
            data_emissao=date(2026, 3, 1),
        )
        chamadas = {"n": 0}
        real = Orcamento.definir_numero_automatico

        def falhar_na_primeira(self):
            real(self)
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise IntegrityError("orcamento_empresa_numero_uniq")

        with patch.object(Orcamento, "definir_numero_automatico", falhar_na_primeira):
            orcamento.save()

        self.assertEqual(chamadas["n"], 2)
        self.assertTrue(Orcamento.objects.filter(pk=orcamento.pk).exists())

    def test_item_de_catalogo_desiste_apos_esgotar_as_tentativas(self):
        """Colisão que não passa em cinco tentativas não vira laço infinito."""
        item = ItemCatalogo(nome="Item", unidade_medida="un", valor_unitario_padrao=Decimal("1.00"))

        with (
            patch.object(
                ItemCatalogo,
                "definir_codigo_automatico",
                side_effect=IntegrityError("itemcatalogo_empresa_codigo_uniq"),
                autospec=True,
            ),
            self.assertRaises(IntegrityError),
        ):
            item.save()

    def test_orcamento_desiste_apos_esgotar_as_tentativas(self):
        usuario = Usuario.objects.create_user(username="autor2", password=SENHA_TESTE)
        cliente = Cliente.objects.create(nome_razao_social="Cliente")
        orcamento = Orcamento(
            titulo="Proposta",
            cliente=cliente,
            criado_por=usuario,
            data_emissao=date(2026, 3, 1),
        )

        with (
            patch.object(
                Orcamento,
                "definir_numero_automatico",
                side_effect=IntegrityError("orcamento_empresa_numero_uniq"),
                autospec=True,
            ),
            self.assertRaises(IntegrityError),
        ):
            orcamento.save()

    def test_orcamento_propaga_erro_de_integridade_alheio(self):
        usuario = Usuario.objects.create_user(username="autor3", password=SENHA_TESTE)
        cliente = Cliente.objects.create(nome_razao_social="Cliente")
        orcamento = Orcamento(
            titulo="Proposta",
            cliente=cliente,
            criado_por=usuario,
            data_emissao=date(2026, 3, 1),
        )

        with (
            patch.object(
                Orcamento,
                "definir_numero_automatico",
                side_effect=IntegrityError("outra constraint qualquer"),
                autospec=True,
            ),
            self.assertRaises(IntegrityError),
        ):
            orcamento.save()

    def test_orcamento_de_autor_sem_empresa_cai_na_empresa_padrao(self):
        """Sem empresa o orçamento fica órfão e some de toda listagem por tenant."""
        usuario = Usuario.objects.create_user(username="sem-grupo", password=SENHA_TESTE)
        usuario.groups.clear()  # o signal de criação vincula à padrão; aqui se testa o contrário
        cliente = Cliente.objects.create(nome_razao_social="Cliente")

        orcamento = Orcamento.objects.create(
            titulo="Proposta",
            cliente=cliente,
            criado_por=usuario,
            data_emissao=date(2026, 3, 1),
        )

        self.assertEqual(orcamento.empresa.name, "Empresa padrão")


class ConfiguracaoPadraoDoOrcamentoTests(TestCase):
    def test_orcamento_adota_a_configuracao_ativa_da_empresa(self):
        """Sem isto o PDF sai sem cabeçalho: é a configuração que traz os dados."""
        empresa = Group.objects.create(name="Empresa A")
        usuario = Usuario.objects.create_user(username="dono", password=SENHA_TESTE)
        usuario.groups.add(empresa)
        configuracao = ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa A", empresa=empresa, ativo=True
        )
        ConfiguracaoEmpresa.objects.create(nome_empresa="Antiga", empresa=empresa, ativo=False)
        cliente = Cliente.objects.create(nome_razao_social="Cliente", empresa=empresa)

        orcamento = Orcamento.objects.create(
            titulo="Proposta",
            cliente=cliente,
            criado_por=usuario,
            data_emissao=date(2026, 3, 1),
        )

        self.assertEqual(orcamento.empresa, empresa)
        self.assertEqual(orcamento.configuracao_empresa, configuracao)


class FormatacaoDeErroDeImportacaoTests(TestCase):
    """A planilha reporta a linha e o campo; o usuário corrige sem adivinhar."""

    def test_erro_com_dicionario_de_campos_vira_texto_legivel(self):
        exc = ValidationError({"valor_unitario_padrao": ["Informe um número."]})

        self.assertEqual(_formatar_erro_validacao(exc), "valor unitario padrao: Informe um número.")

    def test_erro_sem_campo_usa_a_lista_de_mensagens(self):
        self.assertEqual(_formatar_erro_validacao(ValidationError(["Falhou."])), "Falhou.")

    def test_erro_que_nao_e_de_validacao_vira_str(self):
        self.assertEqual(_formatar_erro_validacao(ValueError("qualquer coisa")), "qualquer coisa")


class ValidacaoDeLogoTests(TestCase):
    """O upload de logo aceita três formatos e recusa o resto.

    Vale como teste de segurança, não só de usabilidade: o arquivo é aberto
    pelo Pillow e servido de volta para todo mundo que abrir o PDF.
    """

    def _enviar(self, arquivo):
        form = ConfiguracaoEmpresaForm(
            data={"nome_empresa": "Empresa", "ativo": "on"}, files={"logo": arquivo}
        )
        form.is_valid()
        return form

    def _png(self, tamanho=(10, 10)):
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", tamanho, "white").save(buffer, format="PNG")
        return SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")

    def test_png_valido_e_aceito(self):
        self.assertNotIn("logo", self._enviar(self._png()).errors)

    def test_arquivo_que_nao_e_imagem_e_recusado(self):
        arquivo = SimpleUploadedFile("logo.png", b"isto nao e uma imagem", content_type="image/png")

        self.assertIn("logo", self._enviar(arquivo).errors)

    def test_formato_fora_da_lista_e_recusado(self):
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (10, 10), "white").save(buffer, format="BMP")
        arquivo = SimpleUploadedFile("logo.bmp", buffer.getvalue(), content_type="image/bmp")

        form = self._enviar(arquivo)

        self.assertIn("logo", form.errors)
        self.assertIn("PNG, JPEG ou WEBP", str(form.errors["logo"]))


class AdminDeUsuarioTests(TestCase):
    """No admin, o campo de empresa não pode oferecer a empresa dos outros."""

    def setUp(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from usuarios.admin import UsuarioAdmin

        self.empresa = Group.objects.create(name="Empresa A")
        Group.objects.create(name="Empresa B")
        Group.objects.create(name=f"{VISITOR_GROUP_PREFIX}temporario")
        self.admin = UsuarioAdmin(Usuario, AdminSite())
        self.factory = RequestFactory()

    def _pedido(self, usuario):
        pedido = self.factory.get("/admin/")
        pedido.user = usuario
        return pedido

    def test_gestor_so_enxerga_a_propria_empresa(self):
        gestor = Usuario.objects.create_user(username="gestor", password=SENHA_TESTE, is_staff=True)
        gestor.groups.add(self.empresa)

        queryset = self.admin.grupos_empresa_queryset(self._pedido(gestor))

        self.assertEqual(list(queryset.values_list("name", flat=True)), ["Empresa A"])

    def test_usuario_sem_vinculo_explicito_cai_na_empresa_padrao(self):
        """O signal de pós-criação vincula todo usuário novo à empresa padrão.

        Vale registrar aqui: sem esse vínculo o seletor viria vazio, e o teste
        anterior — o do gestor — só passa porque o `groups.add` explícito
        acontece antes de o signal ter o que fazer.
        """
        avulso = Usuario.objects.create_user(username="avulso", password=SENHA_TESTE, is_staff=True)

        nomes = list(
            self.admin.grupos_empresa_queryset(self._pedido(avulso)).values_list("name", flat=True)
        )

        self.assertEqual(nomes, ["Empresa padrão"])

    def test_superusuario_enxerga_todas_menos_as_de_visitante(self):
        """Grupo de visitante é detalhe de implementação da sessão anônima.

        Ele existe como Group para carregar o isolamento por empresa, mas
        oferecê-lo no seletor faria um usuário real ser vinculado a uma empresa
        descartável.
        """
        raiz = Usuario.objects.create_superuser(username="raiz", password=SENHA_TESTE)

        nomes = list(
            self.admin.grupos_empresa_queryset(self._pedido(raiz)).values_list("name", flat=True)
        )

        self.assertIn("Empresa A", nomes)
        self.assertIn("Empresa B", nomes)
        self.assertNotIn(f"{VISITOR_GROUP_PREFIX}temporario", nomes)

    def test_form_do_admin_rotula_o_campo_de_grupos_como_empresa(self):
        raiz = Usuario.objects.create_superuser(username="raiz", password=SENHA_TESTE)

        form = self.admin.get_form(self._pedido(raiz), obj=raiz, change=True)

        campo = form.base_fields["groups"]
        self.assertEqual(campo.label, "Empresa")
        self.assertIn("apenas à empresa permitida", campo.help_text)
        self.assertNotIn(
            f"{VISITOR_GROUP_PREFIX}temporario",
            list(campo.queryset.values_list("name", flat=True)),
        )
