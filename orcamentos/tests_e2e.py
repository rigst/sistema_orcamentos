"""Edição na linha e criação rápida, num navegador de verdade.

O test client não executa JavaScript: a conta ao vivo, o salvamento ao sair do
campo e a troca dos totais só existem aqui. Rodam no job `e2e` do CI.
"""

from decimal import Decimal

import pytest

from orcamentos.conftest import entrar, texto


@pytest.mark.e2e
def test_editar_quantidade_e_valor_na_linha_atualiza_total(
    live_server, page, client, cenario, sem_aceite
):
    from orcamentos.models import Orcamento

    user, orcamento = cenario
    entrar(page, live_server, user, client)
    erros = []
    page.on("pageerror", lambda erro: erros.append(str(erro)))
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")

    total = page.locator("#totais-card-region .totals-card-emphasis strong")
    assert texto(total) == "R$ 700,00"

    linha = page.locator("tr[data-linha-rapida]").first
    qtd = linha.locator("[data-campo-rapido='quantidade']")
    qtd.fill("12")
    # Prévia local, antes de qualquer ida ao servidor.
    assert texto(linha.locator("[data-linha-subtotal]")) == "R$ 600,00"

    valor = linha.locator("[data-campo-rapido='valor_unitario']")
    valor.fill("75,50")
    valor.press("Tab")
    page.wait_for_function(
        "() => document.querySelector('#totais-card-region .totals-card-emphasis strong')"
        ".textContent.includes('1.106,00')"
    )
    assert "Salvo" in linha.locator("[data-linha-status]").inner_text()
    assert texto(page.locator("[data-ledger-total]")) == "R$ 1.106,00"

    orcamento = Orcamento.objects.get(pk=orcamento.pk)
    item = orcamento.itens.get(nome="Piso")
    assert item.quantidade == Decimal("12.00")
    assert item.valor_unitario == Decimal("75.50")
    assert orcamento.total_final == Decimal("1106.00")
    assert not erros, erros


@pytest.mark.e2e
def test_enter_desce_para_a_linha_de_baixo_e_erro_aparece_na_linha(
    live_server, page, client, cenario, sem_aceite
):
    user, orcamento = cenario
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")

    linhas = page.locator("tr[data-linha-rapida]")
    primeira = linhas.nth(0).locator("[data-campo-rapido='quantidade']")
    primeira.fill("0")
    primeira.press("Enter")
    focado = page.evaluate("document.activeElement.id")
    assert focado == linhas.nth(1).locator("[data-campo-rapido='quantidade']").get_attribute("id")

    status = linhas.nth(0).locator("[data-linha-status]")
    page.wait_for_function("el => el.dataset.tipo === 'erro'", arg=status.element_handle())
    assert primeira.get_attribute("aria-invalid") == "true"


@pytest.mark.e2e
def test_criar_orcamento_em_branco_sem_preencher_nada(
    live_server, page, client, cenario, sem_aceite
):
    from orcamentos.models import Orcamento

    user, _ = cenario
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/novo/")
    page.get_by_role("button", name="Criar orçamento").click()
    page.wait_for_url("**/editar/")

    novo = Orcamento.objects.order_by("-pk").first()
    assert novo.titulo == Orcamento.TITULO_GENERICO
    assert novo.cliente_id is None
    assert Orcamento.SEM_CLIENTE in page.content()
