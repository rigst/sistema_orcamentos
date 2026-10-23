from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from core.testing import SENHA_TESTE
from orcamentos.models import Orcamento


class PaginaInicialTests(TestCase):
    """A raiz é a lista de orçamentos, com os mexidos por último em cima."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="inicio_user",
            password=SENHA_TESTE,
        )
        self.client.force_login(self.user)
        self.cliente = Cliente.objects.create(nome_razao_social="Cliente Inicio")

    def _orcamento(self, titulo, **extra):
        return Orcamento.objects.create(
            cliente=self.cliente,
            titulo=titulo,
            data_emissao=timezone.localdate(),
            total_final=Decimal("100.00"),
            criado_por=self.user,
            atualizado_por=self.user,
            **extra,
        )

    def test_raiz_leva_para_a_lista_de_orcamentos(self):
        self.assertRedirects(self.client.get("/"), reverse("orcamentos:lista"))

    def test_login_cai_na_lista_de_orcamentos(self):
        self.client.logout()
        response = self.client.post(
            reverse("login"), {"username": "inicio_user", "password": SENHA_TESTE}
        )
        self.assertRedirects(response, reverse("orcamentos:lista"), fetch_redirect_response=False)

    def test_recentes_ignoram_cancelados_rejeitados_e_inativos(self):
        self._orcamento("Aprovado recente", status="aprovado")
        self._orcamento("Rejeitado recente", status="rejeitado")
        self._orcamento("Cancelado recente", status="cancelado")
        self._orcamento("Inativo recente", status="aprovado", ativo=False)

        response = self.client.get(reverse("orcamentos:lista"))

        titulos = [o.titulo for o in response.context["recentes"]]
        self.assertEqual(titulos, ["Aprovado recente"])
        self.assertContains(response, "Continuar de onde parou")

    def test_recentes_somem_ao_buscar_ou_filtrar(self):
        self._orcamento("Qualquer")
        response = self.client.get(reverse("orcamentos:lista"), {"q": "Qualquer"})
        self.assertEqual(response.context["recentes"], [])
        self.assertNotContains(response, "Continuar de onde parou")

    def test_recentes_mostram_no_maximo_quatro(self):
        for indice in range(6):
            self._orcamento(f"Orc {indice}")
        response = self.client.get(reverse("orcamentos:lista"))
        self.assertEqual(len(response.context["recentes"]), 4)


class InfraestruturaTests(TestCase):
    def test_workflow_de_ci_chama_o_pipeline_compartilhado(self):
        # O pipeline vive em github.com/rigst/ci; o arquivo local só declara os
        # parâmetros do projeto. O que este teste protege é o encanamento: que
        # o repositório continue ligado ao CI compartilhado.
        #
        # A referência é um SHA de 40 caracteres, e não a tag `v1`: tag é
        # ponteiro móvel, e quem puder reescrevê-la passa a rodar código
        # arbitrário com os secrets deste repositório. Por isso o teste casa
        # com o formato do SHA em vez de um valor fixo — prender o SHA aqui
        # faria toda subida do pipeline compartilhado quebrar a suíte, que é
        # exatamente o trabalho que o Dependabot existe para fazer.
        workflow = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"

        self.assertTrue(workflow.exists())
        conteudo = workflow.read_text(encoding="utf-8")
        self.assertRegex(
            conteudo,
            r"rigst/ci/\.github/workflows/python-django\.yml@[0-9a-f]{40}\b",
        )

    def test_healthz_retorna_ok_sem_autenticacao(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    @override_settings(HEALTHZ_TOKEN="segredo-monitoramento")
    def test_healthz_com_token_requer_cabecalho_correto(self):
        response_sem_token = self.client.get(reverse("healthz"))
        response_token_invalido = self.client.get(
            reverse("healthz"),
            HTTP_X_HEALTHZ_TOKEN="token-incorreto",
        )
        response_token_valido = self.client.get(
            reverse("healthz"),
            HTTP_X_HEALTHZ_TOKEN="segredo-monitoramento",
        )

        self.assertEqual(response_sem_token.status_code, 404)
        self.assertEqual(response_token_invalido.status_code, 404)
        self.assertEqual(response_token_valido.status_code, 200)
        self.assertJSONEqual(response_token_valido.content, {"status": "ok"})


class UmaEmpresaPorUsuarioTests(TestCase):
    def setUp(self):
        self.empresa_a = Group.objects.create(name="Empresa A")
        self.empresa_b = Group.objects.create(name="Empresa B")
        self.user = get_user_model().objects.create_user(
            username="usuario_empresa_unica",
            password=SENHA_TESTE,
            perfil="admin",
        )

    def _empresas(self):
        return set(self.user.groups.values_list("name", flat=True))

    def test_entrar_numa_empresa_tira_da_anterior(self):
        self.user.groups.add(self.empresa_a)
        self.user.groups.add(self.empresa_b)

        self.assertEqual(self._empresas(), {"Empresa B"})

    def test_adicionar_pelo_lado_da_empresa_tambem_move(self):
        self.user.groups.add(self.empresa_a)
        self.empresa_b.user_set.add(self.user)

        self.assertEqual(self._empresas(), {"Empresa B"})

    def test_duas_empresas_de_uma_vez_e_recusado(self):
        with self.assertRaises(ValidationError):
            self.user.groups.set([self.empresa_a, self.empresa_b])

    def test_header_mostra_a_empresa_sem_seletor(self):
        self.user.groups.set([self.empresa_a])
        Cliente.objects.create(nome_razao_social="Cliente A", empresa=self.empresa_a)
        Cliente.objects.create(nome_razao_social="Cliente B", empresa=self.empresa_b)
        self.client.force_login(self.user)

        response = self.client.get(reverse("clientes:lista"))

        self.assertNotContains(response, 'name="empresa_id"', html=False)
        self.assertContains(response, "Cliente A")
        self.assertNotContains(response, "Cliente B")

    def test_rota_de_troca_de_empresa_nao_existe_mais(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/empresa/alternar/").status_code, 404)


class GuardaDeTesteTests(SimpleTestCase):
    def test_is_test_fecha_tambem_com_python_m_pytest(self):
        # `Path(sys.argv[0]).name` vira `__main__.py` quando a suíte roda como
        # `python -m pytest`, e o prefixo não bate: IS_TEST ficava False e a
        # suíte rodava com o SECURE_SSL_REDIRECT de produção — 301 em todo
        # request do test client — além do hasher lento e do Sentry ligado.
        self.assertTrue(settings.IS_TEST)

    def test_a_suite_nao_grava_na_midia_de_producao(self):
        # IS_TEST trocava hasher e mailer, mas não o MEDIA_ROOT: a suíte
        # gravava uploads de verdade na mídia compartilhada do servidor.
        self.assertIn("sistema-orcamentos-test-media-", str(settings.MEDIA_ROOT))
