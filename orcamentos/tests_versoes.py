"""Salvamento automático, versões com desfazer/refazer e a tela de edição
(fechamento, ordem e itens não registrados)."""

from decimal import Decimal

from django.contrib.auth.models import Group
from django.urls import reverse

from catalogo.models import CategoriaItem, ItemCatalogo
from clientes.models import Cliente

from .models import NAO_REGISTRADO, ItemOrcamento, Orcamento
from .models_versoes import VersaoOrcamento
from .tests_fluxo import BaseFluxoTests
from .versoes import (
    LIMITE_VERSOES,
    desfazer,
    estado_historico,
    refazer,
    registrar_versao,
    retrato,
)


def dados_form(orcamento, **extra):
    """O formulário principal como o navegador manda no salvamento automático."""
    dados = {
        "titulo": orcamento.titulo,
        "data_emissao": orcamento.data_emissao.isoformat(),
        "desconto_global_valor": "0,00",
        "desconto_global_percentual": "0,00",
        "acrescimo_global_valor": "0,00",
        "acrescimo_global_percentual": "0,00",
        "valor_locacao": "0,00",
        "valor_servico": "0,00",
        "concorrencia_atualizado_em": orcamento.atualizado_em.isoformat(timespec="microseconds"),
    }
    dados.update(extra)
    return dados


class VersoesTests(BaseFluxoTests):
    def setUp(self):
        super().setUp()
        self.orcamento = self.novo_orcamento(cliente=self.cliente)
        self.item = ItemOrcamento.objects.create(
            orcamento=self.orcamento, nome="Piso", quantidade=10, valor_unitario=50, ordem=1
        )
        self.orcamento.refresh_from_db()
        registrar_versao(self.orcamento, self.user, "Estado ao abrir")

    def _mudar_quantidade(self, quantidade):
        self.item.quantidade = Decimal(quantidade)
        self.item.save()
        self.orcamento.refresh_from_db()
        registrar_versao(self.orcamento, self.user, f"Alterou {self.item.nome}")

    def test_sem_mudanca_nao_cria_versao(self):
        self.assertIsNone(registrar_versao(self.orcamento, self.user, "Nada"))
        self.assertEqual(self.orcamento.versoes.count(), 1)

    def test_desfazer_e_refazer_voltam_e_reaplicam_a_quantidade_e_o_total(self):
        self._mudar_quantidade("12")
        self.assertEqual(self.orcamento.total_final, Decimal("600.00"))

        self.assertIsNotNone(desfazer(self.orcamento))
        self.item.refresh_from_db()
        self.orcamento.refresh_from_db()
        self.assertEqual(self.item.quantidade, Decimal("10.00"))
        self.assertEqual(self.orcamento.total_final, Decimal("500.00"))

        self.assertIsNotNone(refazer(self.orcamento))
        self.item.refresh_from_db()
        self.orcamento.refresh_from_db()
        self.assertEqual(self.item.quantidade, Decimal("12.00"))
        self.assertEqual(self.orcamento.total_final, Decimal("600.00"))

    def test_nao_desfaz_alem_da_primeira_versao(self):
        self.assertIsNone(desfazer(self.orcamento))
        self.assertFalse(estado_historico(self.orcamento)["pode_desfazer"])

    def test_alteracao_nova_depois_de_desfazer_apaga_o_refazer(self):
        self._mudar_quantidade("12")
        desfazer(self.orcamento)
        self.assertTrue(estado_historico(self.orcamento)["pode_refazer"])

        self._mudar_quantidade("15")

        self.assertFalse(estado_historico(self.orcamento)["pode_refazer"])
        self.assertIsNone(refazer(self.orcamento))

    def test_desfazer_exclusao_traz_o_item_de_volta(self):
        self.item.delete()
        self.orcamento.refresh_from_db()
        registrar_versao(self.orcamento, self.user, "Excluiu Piso")
        self.assertEqual(self.orcamento.itens.count(), 0)

        desfazer(self.orcamento)

        self.assertEqual(list(self.orcamento.itens.values_list("nome", flat=True)), ["Piso"])
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.total_final, Decimal("500.00"))

    def test_desfazer_inclusao_tira_o_item(self):
        ItemOrcamento.objects.create(
            orcamento=self.orcamento, nome="Carpete", quantidade=1, valor_unitario=10, ordem=2
        )
        self.orcamento.refresh_from_db()
        registrar_versao(self.orcamento, self.user, "Adicionou Carpete")

        desfazer(self.orcamento)

        self.assertEqual(list(self.orcamento.itens.values_list("nome", flat=True)), ["Piso"])

    def test_desfazer_dados_gerais_e_cliente(self):
        outro = Cliente.objects.create(nome_razao_social="Outro", empresa=self.grupo)
        self.orcamento.titulo = "Título novo"
        self.orcamento.cliente = outro
        self.orcamento.save()
        registrar_versao(self.orcamento, self.user, "Editou título")

        desfazer(self.orcamento)

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.titulo, "Edital")
        self.assertEqual(self.orcamento.cliente, self.cliente)

    def test_restaurar_com_item_de_catalogo_que_sumiu_nao_quebra(self):
        categoria = CategoriaItem.objects.create(nome="Piso", empresa=self.grupo)
        catalogo = ItemCatalogo.objects.create(
            categoria=categoria,
            empresa=self.grupo,
            nome="Piso",
            unidade_medida="un",
            valor_unitario_padrao=50,
        )
        self.item.item_catalogo = catalogo
        self.item.save()
        self.orcamento.refresh_from_db()
        registrar_versao(self.orcamento, self.user, "Ligou ao catálogo")
        self._mudar_quantidade("20")
        self.item.item_catalogo = None
        self.item.save()
        catalogo.delete()

        desfazer(self.orcamento)

        self.item.refresh_from_db()
        self.assertIsNone(self.item.item_catalogo_id)
        self.assertEqual(self.item.quantidade, Decimal("10.00"))

    def test_guarda_no_maximo_o_limite_de_versoes(self):
        for n in range(LIMITE_VERSOES + 5):
            self._mudar_quantidade(str(11 + n))
        self.assertEqual(self.orcamento.versoes.count(), LIMITE_VERSOES)

    def test_retrato_nao_guarda_numero_status_nem_totais(self):
        dados = retrato(self.orcamento)["orcamento"]
        for campo in ("numero", "status", "empresa_id", "total_final", "subtotal_itens"):
            self.assertNotIn(campo, dados)


class AutosalvarTests(BaseFluxoTests):
    def setUp(self):
        super().setUp()
        self.orcamento = self.novo_orcamento()
        self.url = reverse("orcamentos:autosalvar", args=[self.orcamento.pk])
        # Abrir o editor registra a versão base.
        self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))
        self.orcamento.refresh_from_db()

    def test_salva_campo_e_registra_versao_com_descricao(self):
        resposta = self.client.post(self.url, dados_form(self.orcamento, evento_nome="Expointer"))

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["salvo"])
        self.assertTrue(dados["historico"]["pode_desfazer"])
        self.assertIn("evento", dados["historico"]["desfazer_rotulo"].lower())
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.evento_nome, "Expointer")
        self.assertEqual(
            dados["concorrencia"], self.orcamento.atualizado_em.isoformat(timespec="microseconds")
        )

    def test_sem_mudanca_nao_cria_versao(self):
        antes = self.orcamento.versoes.count()
        resposta = self.client.post(self.url, dados_form(self.orcamento))
        self.assertFalse(resposta.json()["salvo"])
        self.assertEqual(self.orcamento.versoes.count(), antes)

    def test_desconto_global_atualiza_os_totais_devolvidos(self):
        ItemOrcamento.objects.create(
            orcamento=self.orcamento, nome="Piso", quantidade=10, valor_unitario=50, ordem=1
        )
        self.orcamento.refresh_from_db()

        resposta = self.client.post(
            self.url, dados_form(self.orcamento, desconto_global_percentual="10,00")
        )

        self.assertIn("450,00", resposta.json()["totais_html"])
        self.assertIn("Desconto de", resposta.json()["totais_html"])

    def test_erro_de_validacao_volta_por_campo_e_nao_salva(self):
        resposta = self.client.post(
            self.url, dados_form(self.orcamento, contrato_cnpj="123", titulo="Não pode salvar")
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("contrato_cnpj", resposta.json()["erros"])
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.titulo, "Edital")

    def test_versao_antiga_de_concorrencia_e_recusada(self):
        resposta = self.client.post(
            self.url, dados_form(self.orcamento, concorrencia_atualizado_em="2000-01-01T00:00:00")
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("__all__", resposta.json()["erros"])

    def test_exige_post_rascunho_e_empresa_certa(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

        enviado = self.novo_orcamento(status="enviado")
        url_enviado = reverse("orcamentos:autosalvar", args=[enviado.pk])
        self.assertIn(self.client.post(url_enviado, dados_form(enviado)).status_code, (302, 403))

        outra = Group.objects.create(name="Outra")
        alheio = self.novo_orcamento(empresa=outra)
        url_alheio = reverse("orcamentos:autosalvar", args=[alheio.pk])
        self.assertEqual(self.client.post(url_alheio, dados_form(alheio)).status_code, 404)

    def test_desfazer_e_refazer_pelas_rotas(self):
        self.client.post(self.url, dados_form(self.orcamento, titulo="Mudado"))

        resposta = self.client.post(reverse("orcamentos:desfazer", args=[self.orcamento.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Desfeito", resposta.json()["mensagem"])
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.titulo, "Edital")

        resposta = self.client.post(reverse("orcamentos:refazer", args=[self.orcamento.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.titulo, "Mudado")

        sem_nada = self.client.post(reverse("orcamentos:refazer", args=[self.orcamento.pk]))
        self.assertEqual(sem_nada.status_code, 409)

    def test_editar_na_linha_entra_no_historico(self):
        item = ItemOrcamento.objects.create(
            orcamento=self.orcamento, nome="Piso", quantidade=10, valor_unitario=50, ordem=1
        )
        self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))

        resposta = self.client.post(
            reverse("orcamentos:item_edicao_rapida", args=[self.orcamento.pk, item.pk]),
            {"quantidade": "12"},
        )

        self.assertEqual(resposta.json()["historico"]["desfazer_rotulo"], "Alterou Piso")
        self.client.post(reverse("orcamentos:desfazer", args=[self.orcamento.pk]))
        item.refresh_from_db()
        self.assertEqual(item.quantidade, Decimal("10.00"))

    def test_mudanca_feita_fora_do_editor_vira_versao_ao_abrir(self):
        ItemOrcamento.objects.create(
            orcamento=self.orcamento, nome="Vindo da IA", quantidade=1, valor_unitario=0, ordem=1
        )

        self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))

        ultima = self.orcamento.versoes.order_by("-id").first()
        self.assertEqual(ultima.descricao, "Alterações fora do editor")

    def test_visualizacao_nao_cria_versao(self):
        VersaoOrcamento.objects.all().delete()
        self.client.get(reverse("orcamentos:visualizar", args=[self.orcamento.pk]))
        self.assertFalse(VersaoOrcamento.objects.exists())


class TelaDeEdicaoTests(BaseFluxoTests):
    def setUp(self):
        super().setUp()
        self.orcamento = self.novo_orcamento()
        categoria = CategoriaItem.objects.create(
            nome="Estrutura", empresa=self.grupo, cor="#2563EB"
        )
        catalogo = ItemCatalogo.objects.create(
            categoria=categoria,
            empresa=self.grupo,
            nome="Piso",
            unidade_medida="un",
            valor_unitario_padrao=50,
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            item_catalogo=catalogo,
            nome="Piso",
            quantidade=6,
            valor_unitario=50,
            ordem=1,
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            nome="Painel especial",
            quantidade=1,
            valor_unitario=100,
            ordem=2,
        )
        self.orcamento.refresh_from_db()

    def _tela(self):
        return self.client.get(
            reverse("orcamentos:editar", args=[self.orcamento.pk])
        ).content.decode()

    def test_item_fora_do_catalogo_aparece_como_nao_registrado(self):
        conteudo = self._tela()
        self.assertIn("Não registrado", conteudo)
        self.assertNotIn("Sem ajuste", conteudo)

    def test_subtotais_separam_nao_registrado_e_mostram_percentual(self):
        grupos = self.orcamento.subtotais_por_categoria(NAO_REGISTRADO)

        self.assertEqual([g["categoria_nome"] for g in grupos], ["Estrutura", NAO_REGISTRADO])
        self.assertEqual(grupos[0]["percentual"], Decimal("75.00"))
        self.assertEqual(grupos[1]["quantidade_itens"], 1)

    def test_relatorio_do_cliente_continua_com_sem_categoria(self):
        nomes = [g["categoria_nome"] for g in self.orcamento.subtotais_por_categoria()]
        self.assertEqual(nomes, ["Estrutura", "Sem categoria"])

    def test_fechamento_mostra_ajustes_mesmo_zerados(self):
        conteudo = self._tela()
        self.assertIn("Subtotal dos itens", conteudo)
        # Zerados aparecem (apagados), para mostrar que dá para usar.
        self.assertIn("Desconto em valor", conteudo)
        self.assertIn("Acréscimo de 0", conteudo)
        self.assertIn("fechamento-linha--zero", conteudo)

        Orcamento.objects.filter(pk=self.orcamento.pk).update(desconto_global_percentual=10)
        self.orcamento.refresh_from_db()
        self.orcamento.recalcular_totais()
        conteudo = self._tela()
        self.assertIn("Desconto de 10", conteudo)
        self.assertIn("40,00", conteudo)

    def test_setas_de_ordem_ficam_na_primeira_coluna_e_somem_nas_pontas(self):
        conteudo = self._tela()
        self.assertEqual(conteudo.count('class="ordem-seta"'), 4)
        self.assertEqual(conteudo.count('title="Subir item" aria-label="Subir Piso" disabled'), 1)
        self.assertIn('aria-label="Descer Painel especial" disabled', conteudo)

    def test_sem_barra_flutuante_nem_titulos_repetidos_nas_abas(self):
        conteudo = self._tela()
        self.assertNotIn("ledger-bar", conteudo)
        self.assertNotIn('orc-painel-titulo">Evento ou projeto', conteudo)
        self.assertNotIn('orc-painel-titulo">Dados contratuais', conteudo)
        self.assertNotIn("Itens do orçamento</h3>", conteudo)

    def test_cabecalho_tem_desfazer_refazer_e_status_do_salvamento(self):
        conteudo = self._tela()
        self.assertIn("data-desfazer", conteudo)
        self.assertIn("data-refazer", conteudo)
        self.assertIn("Tudo salvo", conteudo)
        self.assertIn("js/orcamento-autosave.js", conteudo)

    def test_menu_tem_orcamentos_uma_vez_so(self):
        conteudo = self.client.get(reverse("orcamentos:lista")).content.decode()
        menu = conteudo.split("<header")[1].split("</header>")[0]
        self.assertEqual(menu.count("Orçamentos"), 1)
        self.assertIn("favicon.svg", conteudo)
