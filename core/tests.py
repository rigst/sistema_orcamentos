from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from orcamentos.models import Orcamento


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dashboard_user",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)
        self.cliente = Cliente.objects.create(nome_razao_social="Cliente Dashboard")

        Orcamento.objects.create(
            numero="ORC-DASH-1",
            cliente=self.cliente,
            titulo="Aprovado recente",
            status="aprovado",
            data_emissao=timezone.localdate(),
            total_final=Decimal("1200.00"),
            criado_por=self.user,
            atualizado_por=self.user,
        )
        Orcamento.objects.create(
            numero="ORC-DASH-2",
            cliente=self.cliente,
            titulo="Rascunho antigo",
            status="rascunho",
            data_emissao=timezone.localdate() - timedelta(days=45),
            total_final=Decimal("800.00"),
            criado_por=self.user,
            atualizado_por=self.user,
        )

    def test_dashboard_filtra_periodo_e_exibe_indicadores(self):
        response = self.client.get(reverse("dashboard"), {"periodo": "30"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R$ 1.200,00")
        self.assertContains(response, "Últimos 30 dias")
        self.assertNotContains(response, "Rascunho antigo")

    def test_manual_do_sistema_esta_disponivel(self):
        response = self.client.get(reverse("manual"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manual do sistema")
        self.assertContains(response, "Perfis e autorizações")


class InfraestruturaTests(TestCase):
    def test_workflow_de_ci_existe_e_executa_check_e_test(self):
        workflow = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "django.yml"

        self.assertTrue(workflow.exists())
        conteudo = workflow.read_text(encoding="utf-8")
        self.assertIn("python manage.py check", conteudo)
        self.assertIn("python manage.py test", conteudo)
