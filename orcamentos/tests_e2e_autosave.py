"""Salvamento automático e desfazer/refazer, num navegador de verdade."""

from decimal import Decimal

import pytest

from orcamentos.conftest import entrar, texto


def esperar_salvo(page):
    page.wait_for_function(
        "() => document.querySelector('[data-autosave-status]').dataset.tipo === 'ok'"
        " && document.querySelector('[data-autosave-status]').textContent.includes('salvo')"
    )


@pytest.mark.e2e
def test_campo_salva_sozinho_e_desfazer_refazer_voltam_o_valor(
    live_server, page, client, cenario, sem_aceite
):
    from orcamentos.models import Orcamento

    user, orcamento = cenario
    entrar(page, live_server, user, client)
    erros = []
    page.on("pageerror", lambda erro: erros.append(str(erro)))
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")

    desfazer = page.locator("[data-desfazer]")
    assert desfazer.is_disabled()

    page.get_by_label("Título").fill("Estande Expointer")
    page.wait_for_function(
        "() => document.querySelector('[data-autosave-status]').dataset.tipo === 'pendente'"
        " || document.querySelector('[data-autosave-status]').dataset.tipo === 'salvando'"
        " || !document.querySelector('[data-desfazer]').disabled"
    )
    esperar_salvo(page)
    assert Orcamento.objects.get(pk=orcamento.pk).titulo == "Estande Expointer"
    assert desfazer.is_enabled()
    assert "título" in desfazer.get_attribute("title").lower()

    desfazer.click()
    page.wait_for_load_state()
    page.wait_for_function(
        "() => document.querySelector('[data-autosave-status]').textContent.includes('Desfeito')"
    )
    assert page.get_by_label("Título").input_value() == "Teste e2e"
    assert Orcamento.objects.get(pk=orcamento.pk).titulo == "Teste e2e"

    page.locator("[data-refazer]").click()
    page.wait_for_load_state()
    page.wait_for_function(
        "() => document.querySelector('[data-autosave-status]').textContent.includes('Refeito')"
    )
    assert page.get_by_label("Título").input_value() == "Estande Expointer"
    assert not erros, erros


@pytest.mark.e2e
def test_desconto_salva_sozinho_e_fechamento_mostra_a_linha(
    live_server, page, client, cenario, sem_aceite
):
    user, orcamento = cenario
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")

    page.locator(".orc-ajustes > summary").click()
    campo = page.get_by_label("Desconto (%)")
    campo.fill("10")
    campo.press("Tab")
    page.wait_for_function(
        "() => document.querySelector('#totais-card-region [data-total-final]')"
        ".textContent.includes('630,00')"
    )
    assert "Desconto de 10" in texto(page.locator("#totais-card-region"))


@pytest.mark.e2e
def test_ctrl_z_desfaz_a_edicao_na_linha(live_server, page, client, cenario, sem_aceite):
    from orcamentos.models import ItemOrcamento

    user, orcamento = cenario
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")

    qtd = page.locator("tr[data-linha-rapida]").first.locator("[data-campo-rapido='quantidade']")
    qtd.fill("12")
    qtd.press("Tab")
    page.wait_for_function("() => !document.querySelector('[data-desfazer]').disabled")
    assert ItemOrcamento.objects.get(orcamento=orcamento, nome="Piso").quantidade == Decimal(
        "12.00"
    )

    # Fora de campo de texto, Ctrl+Z é o desfazer do orçamento.
    page.locator("body").click(position={"x": 5, "y": 5})
    page.keyboard.press("Control+z")
    page.wait_for_function(
        "() => document.querySelector('[data-autosave-status]').textContent.includes('Desfeito')"
    )
    assert ItemOrcamento.objects.get(orcamento=orcamento, nome="Piso").quantidade == Decimal(
        "10.00"
    )


@pytest.mark.e2e
def test_setas_de_ordem_na_primeira_coluna_movem_o_item(
    live_server, page, client, cenario, sem_aceite
):
    user, orcamento = cenario
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")

    primeira = page.locator("tr[data-linha-rapida]").first
    primeira.hover()
    seta = primeira.get_by_role("button", name="Descer Piso")
    seta.click()
    page.wait_for_function(
        "() => document.querySelector('tr[data-linha-rapida] strong').textContent.includes('Carpete')"
    )
    page.wait_for_function("() => !document.querySelector('[data-desfazer]').disabled")
