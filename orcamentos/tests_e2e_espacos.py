"""Espaçamentos que só o navegador mede: conteúdo das abas da edição e a
pílula do cabeçalho no celular."""

import pytest

from orcamentos.conftest import entrar

# Distância entre a linha das abas e o primeiro conteúdo do painel aberto.
MEDIR_ABA = """
() => {
  const barra = document.querySelector('.orc-abas-barra').getBoundingClientRect();
  const painel = [...document.querySelectorAll('.orc-painel')].find(p => !p.hidden);
  return Math.round(painel.getBoundingClientRect().top - barra.bottom);
}
"""

# Folga entre a borda da pílula e o conteúdo visível, em cima e embaixo.
MEDIR_PILULA = """
() => {
  const nav = document.querySelector('.nav');
  const b = nav.getBoundingClientRect();
  const r = [...nav.querySelectorAll('*')].map(e => e.getBoundingClientRect()).filter(x => x.height > 0);
  return [Math.round(Math.min(...r.map(x => x.top)) - b.top), Math.round(b.bottom - Math.max(...r.map(x => x.bottom)))];
}
"""


@pytest.mark.e2e
@pytest.mark.parametrize("largura", [1280, 390])
def test_todas_as_abas_comecam_com_o_mesmo_respiro(
    live_server, page, client, cenario, sem_aceite, largura
):
    from clientes.models import Cliente

    user, orcamento = cenario
    # Com cliente aparece o botão "Copiar do cadastro do cliente", cujo form
    # escondido somava espaço só na aba Itens.
    orcamento.cliente = Cliente.objects.create(
        nome_razao_social="Cliente", empresa=orcamento.empresa
    )
    orcamento.save()
    page.set_viewport_size({"width": largura, "height": 860})
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")

    distancias = {}
    for aba in ("itens", "evento", "comercial", "contrato"):
        page.click(f"[role=tab][data-aba={aba}]")
        distancias[aba] = page.evaluate(MEDIR_ABA)

    assert min(distancias.values()) >= 16, distancias  # nada grudado nas abas
    assert len(set(distancias.values())) == 1, distancias  # e igual em todas


@pytest.mark.e2e
def test_botao_copiar_do_cliente_continua_enviando_o_form_escondido(
    live_server, page, client, cenario, sem_aceite
):
    from clientes.models import Cliente

    user, orcamento = cenario
    orcamento.cliente = Cliente.objects.create(
        nome_razao_social="Razão do Cliente", empresa=orcamento.empresa
    )
    orcamento.save()
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/{orcamento.pk}/editar/")
    page.click("[role=tab][data-aba=contrato]")
    page.once("dialog", lambda dialogo: dialogo.accept())
    page.click("button[form=form-contrato-do-cliente]")
    page.wait_for_load_state("networkidle")

    orcamento.refresh_from_db()
    assert orcamento.contrato_razao_social == "Razão do Cliente"


@pytest.mark.e2e
def test_pilula_do_cabecalho_no_celular_tem_folga_igual_em_cima_e_embaixo(
    live_server, page, client, cenario, sem_aceite
):
    user, _ = cenario
    page.set_viewport_size({"width": 390, "height": 860})
    entrar(page, live_server, user, client)
    page.goto(f"{live_server.url}/orcamentos/")

    cima, baixo = page.evaluate(MEDIR_PILULA)
    assert abs(cima - baixo) <= 2, (cima, baixo)

    page.click(".js-nav-toggle")
    cima, baixo = page.evaluate(MEDIR_PILULA)
    assert abs(cima - baixo) <= 2, ("menu aberto", cima, baixo)
