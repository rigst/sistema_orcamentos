"""Fixtures dos testes de navegador do app orçamentos (job `e2e`)."""

from datetime import date

import pytest

from core.testing import SENHA_TESTE


@pytest.fixture
def cenario(db):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    from core.models import Empresa
    from orcamentos.models import ItemOrcamento, Orcamento

    grupo = Group.objects.create(name="Empresa E2E")
    Empresa.objects.get_or_create(grupo=grupo, defaults={"nome": "Empresa E2E"})
    user = get_user_model().objects.create_user(
        username="e2e", password=SENHA_TESTE, perfil="orcamentista"
    )
    user.groups.add(grupo)
    orcamento = Orcamento.objects.create(
        empresa=grupo,
        titulo="Teste e2e",
        data_emissao=date(2026, 10, 22),
        criado_por=user,
        atualizado_por=user,
    )
    ItemOrcamento.objects.create(
        orcamento=orcamento, nome="Piso", quantidade=10, valor_unitario=50, ordem=1
    )
    ItemOrcamento.objects.create(
        orcamento=orcamento, nome="Carpete", quantidade=2, valor_unitario=100, ordem=2
    )
    return user, orcamento


def texto(locator):
    """O Intl.NumberFormat do navegador separa "R$" do número com espaço
    inquebrável; o servidor, com espaço comum. A comparação ignora isso."""
    return " ".join(locator.inner_text().replace("\u00a0", " ").split())


def entrar(page, live_server, user, client):
    """Sessão pronta no navegador, sem passar pela tela de aceite dos termos
    (outra suíte cobre o aceite): o cookie vem do test client."""
    client.force_login(user)
    cookie = client.cookies["sessionid"]
    page.context.add_cookies([{"name": "sessionid", "value": cookie.value, "url": live_server.url}])


@pytest.fixture
def sem_aceite(settings):
    settings.MIDDLEWARE = [m for m in settings.MIDDLEWARE if not m.startswith("legal.")]
