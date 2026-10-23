"""Tela do orçamento em abas e catálogo com categorias, num navegador de verdade.

O test client não executa JavaScript: a troca de abas, o hash na URL, a aba
de erro aberta sozinha e o menu de status só existem aqui. Rodam no job `e2e`.
"""

import pytest

from orcamentos.conftest import entrar

PAINEIS = ("itens", "evento", "comercial", "contrato")


def visiveis(page):
    return [nome for nome in PAINEIS if page.locator(f"#painel-{nome}").is_visible()]


@pytest.mark.e2e
def test_abas_trocam_o_painel_guardam_o_hash_e_respondem_ao_teclado(
    live_server,
    page,
    client,
    cenario,
    sem_aceite,
):
    user, orcamento = cenario
    entrar(page, live_server, user, client)
    erros = []
    page.on("pageerror", lambda erro: erros.append(str(erro)))
    url = f"{live_server.url}/orcamentos/{orcamento.pk}/editar/"
    page.goto(url)

    assert visiveis(page) == ["itens"]

    page.get_by_role("tab", name="Contrato").click()
    assert visiveis(page) == ["contrato"]
    assert page.url.endswith("#contrato")

    page.keyboard.press("ArrowLeft")
    assert visiveis(page) == ["comercial"]
    assert page.evaluate("document.activeElement.id") == "aba-comercial"

    # Recarregar com o hash volta na mesma aba.
    page.goto(f"{url}#evento")
    page.reload()
    assert visiveis(page) == ["evento"]
    assert not erros, erros


@pytest.mark.e2e
def test_campo_preenchido_em_outra_aba_e_salvo_junto(
    live_server,
    page,
    client,
    cenario,
    sem_aceite,
):
    from orcamentos.models import Orcamento

    user, orcamento = cenario
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")

    page.get_by_role("tab", name="Evento").click()
    page.get_by_label("Evento ou projeto").fill("Feira do Livro")
    page.get_by_role("tab", name="Comercial").click()
    page.get_by_label("Condições de pagamento").fill("50% na assinatura")
    page.get_by_role("button", name="Salvar").first.click()
    page.wait_for_load_state()

    orcamento = Orcamento.objects.get(pk=orcamento.pk)
    assert orcamento.evento_nome == "Feira do Livro"
    assert orcamento.condicoes_pagamento == "50% na assinatura"


@pytest.mark.e2e
def test_status_muda_pelo_menu_do_cabecalho_e_fica_na_tela(
    live_server,
    page,
    client,
    cenario,
    sem_aceite,
):
    from orcamentos.models import Orcamento

    user, orcamento = cenario
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")

    page.once("dialog", lambda dialogo: dialogo.accept())
    page.locator(".page-head-meta .status-menu > summary").click()
    page.get_by_role("button", name="Enviar").click()
    page.wait_for_load_state()

    assert f"/orcamentos/{orcamento.pk}/editar/" in page.url
    assert Orcamento.objects.get(pk=orcamento.pk).status == "enviado"


@pytest.mark.e2e
def test_catalogo_filtra_pela_categoria_e_cria_categoria_no_modal(
    live_server,
    page,
    client,
    cenario,
    sem_aceite,
):
    from django.contrib.auth import get_user_model

    from catalogo.models import CategoriaItem, ItemCatalogo

    _, orcamento = cenario
    admin = get_user_model().objects.create_user(
        username="admin_e2e", password="x-Senha-Forte-1", perfil="admin"
    )
    admin.groups.add(orcamento.empresa)
    luz = CategoriaItem.objects.create(nome="Iluminação", empresa=orcamento.empresa)
    som = CategoriaItem.objects.create(nome="Sonorização", empresa=orcamento.empresa)
    ItemCatalogo.objects.create(
        categoria=luz,
        empresa=orcamento.empresa,
        nome="Refletor LED",
        unidade_medida="un",
        valor_unitario_padrao=10,
    )
    ItemCatalogo.objects.create(
        categoria=som,
        empresa=orcamento.empresa,
        nome="Caixa de som",
        unidade_medida="un",
        valor_unitario_padrao=10,
    )
    entrar(page, live_server, admin, client)
    page.goto(f"{live_server.url}/catalogo/itens/")

    page.locator("a.catalogo-categoria", has_text="Iluminação").click()
    page.wait_for_load_state()
    assert page.get_by_text("Refletor LED").first.is_visible()
    assert page.get_by_text("Caixa de som").count() == 0

    page.get_by_role("link", name="+ Categoria").click()
    page.locator("#panel-modal input[name='nome']").fill("Mobiliário")
    page.locator("#panel-modal button[type='submit']").click()
    page.wait_for_function("() => document.body.innerText.includes('Mobiliário')")

    assert CategoriaItem.objects.filter(nome="Mobiliário", empresa=orcamento.empresa).exists()
