"""Tela do orçamento reorganizada: abas, status no cabeçalho, ajustes junto
dos totais, contrato puxado do cliente e padrões comerciais da empresa."""

import importlib
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib.auth.models import Group
from django.urls import reverse

from clientes.models import Cliente
from relatorios.models import ConfiguracaoEmpresa

from .models import Orcamento
from .tests_fluxo import BaseFluxoTests


class TelaEmAbasTests(BaseFluxoTests):
    def test_edicao_abre_com_as_quatro_abas_e_os_itens_primeiro(self):
        orcamento = self.novo_orcamento(cliente=self.cliente)

        conteudo = self.client.get(
            reverse("orcamentos:editar", args=[orcamento.pk])
        ).content.decode()

        for aba in ("aba-itens", "aba-evento", "aba-comercial", "aba-contrato"):
            self.assertIn(f'id="{aba}"', conteudo)
        self.assertIn('id="aba-itens" aria-controls="painel-itens" aria-selected="true"', conteudo)
        self.assertIn("js/orcamento-abas.js", conteudo)
        # O seletor de empresa saiu: o cadastro é um só.
        self.assertNotIn('name="configuracao_empresa"', conteudo)

    def test_ajustes_globais_ficam_junto_dos_totais_ligados_ao_form_principal(self):
        orcamento = self.novo_orcamento()

        conteudo = self.client.get(
            reverse("orcamentos:editar", args=[orcamento.pk])
        ).content.decode()

        self.assertIn("Desconto ou acréscimo no total", conteudo)
        self.assertIn('name="desconto_global_percentual"', conteudo)
        self.assertRegex(
            conteudo, r'name="desconto_global_percentual"[^>]*form="orcamento-main-form"'
        )

    def test_salvar_com_desconto_vindo_de_fora_do_form_aplica_no_total(self):
        orcamento = self.novo_orcamento()
        dados = {
            "titulo": orcamento.titulo,
            "data_emissao": "2026-10-22",
            "desconto_global_valor": "0,00",
            "desconto_global_percentual": "10,00",
            "acrescimo_global_valor": "0,00",
            "acrescimo_global_percentual": "0,00",
            "valor_locacao": "0,00",
            "valor_servico": "0,00",
        }

        resposta = self.client.post(reverse("orcamentos:editar", args=[orcamento.pk]), dados)

        self.assertEqual(resposta.status_code, 302)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.desconto_global_percentual, Decimal("10.00"))

    def test_novo_orcamento_pelo_formulario_completo_nao_mostra_abas(self):
        conteudo = self.client.get(reverse("orcamentos:criar")).content.decode()

        self.assertNotIn("data-orc-abas", conteudo)
        self.assertIn('id="painel-evento"', conteudo)


class StatusNoCabecalhoTests(BaseFluxoTests):
    def test_cabecalho_mostra_o_menu_com_as_transicoes_do_rascunho(self):
        orcamento = self.novo_orcamento()

        resposta = self.client.get(reverse("orcamentos:editar", args=[orcamento.pk]))

        self.assertContains(resposta, 'class="status-menu"')
        self.assertContains(
            resposta, reverse("orcamentos:alterar_status", args=[orcamento.pk, "enviado"])
        )
        self.assertNotContains(
            resposta, reverse("orcamentos:alterar_status", args=[orcamento.pk, "aprovado"])
        )

    def test_trocar_status_pelo_cabecalho_volta_para_a_mesma_tela(self):
        orcamento = self.novo_orcamento()
        tela = reverse("orcamentos:editar", args=[orcamento.pk])

        resposta = self.client.post(
            reverse("orcamentos:alterar_status", args=[orcamento.pk, "enviado"]), {"next": tela}
        )

        self.assertRedirects(resposta, tela, fetch_redirect_response=False)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, "enviado")

    def test_next_para_outro_site_e_ignorado(self):
        orcamento = self.novo_orcamento()

        resposta = self.client.post(
            reverse("orcamentos:alterar_status", args=[orcamento.pk, "enviado"]),
            {"next": "https://malicioso.example/"},
        )

        self.assertRedirects(resposta, reverse("orcamentos:lista"), fetch_redirect_response=False)

    def test_quem_so_visualiza_ve_o_selo_sem_menu(self):
        orcamento = self.novo_orcamento()
        leitor = self.user.__class__.objects.create_user(
            username="leitor", password="x-Senha-Forte-1", perfil="visualizador"
        )
        leitor.groups.add(self.grupo)
        self.client.force_login(leitor)

        resposta = self.client.get(reverse("orcamentos:visualizar", args=[orcamento.pk]))

        self.assertNotContains(resposta, 'class="status-menu"')
        self.assertContains(resposta, "status-rascunho")


class ContratoDoClienteTests(BaseFluxoTests):
    def setUp(self):
        super().setUp()
        self.cliente.cpf_cnpj = "12.345.678/0001-90"
        self.cliente.logradouro = "Rua A"
        self.cliente.numero = "10"
        self.cliente.cidade = "Porto Alegre"
        self.cliente.estado = "RS"
        self.cliente.email = "compras@prefeitura.example"
        self.cliente.save()

    def test_escolher_o_cliente_preenche_os_dados_contratuais_vazios(self):
        orcamento = self.novo_orcamento(cliente=self.cliente)

        self.assertEqual(orcamento.contrato_razao_social, "Prefeitura")
        self.assertEqual(orcamento.contrato_cnpj, "12.345.678/0001-90")
        self.assertEqual(orcamento.contrato_endereco, "Rua A, 10")
        self.assertEqual(orcamento.contrato_cidade, "Porto Alegre/RS")
        self.assertEqual(orcamento.contrato_email, "compras@prefeitura.example")

    def test_o_que_foi_digitado_no_contrato_nao_e_sobrescrito(self):
        orcamento = self.novo_orcamento(contrato_razao_social="Consórcio Específico")
        orcamento.cliente = self.cliente
        orcamento.save()

        orcamento.refresh_from_db()
        self.assertEqual(orcamento.contrato_razao_social, "Consórcio Específico")
        self.assertEqual(orcamento.contrato_cnpj, "12.345.678/0001-90")

    def test_botao_copiar_do_cliente_sobrescreve_tudo(self):
        orcamento = self.novo_orcamento(cliente=self.cliente)
        Orcamento.objects.filter(pk=orcamento.pk).update(contrato_razao_social="Antigo")

        resposta = self.client.post(reverse("orcamentos:contrato_do_cliente", args=[orcamento.pk]))

        self.assertRedirects(
            resposta,
            f"{reverse('orcamentos:editar', args=[orcamento.pk])}#contrato",
            fetch_redirect_response=False,
        )
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.contrato_razao_social, "Prefeitura")

    def test_copiar_sem_diferenca_avisa_e_nao_salva(self):
        orcamento = self.novo_orcamento(cliente=self.cliente)
        antes = orcamento.atualizado_em

        resposta = self.client.post(
            reverse("orcamentos:contrato_do_cliente", args=[orcamento.pk]), follow=True
        )

        self.assertContains(resposta, "já estão iguais ao cadastro do cliente")
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.atualizado_em, antes)

    def test_copiar_exige_post_e_orcamento_editavel(self):
        orcamento = self.novo_orcamento(cliente=self.cliente, status="enviado")
        url = reverse("orcamentos:contrato_do_cliente", args=[orcamento.pk])

        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertIn(self.client.post(url).status_code, (302, 403))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, "enviado")

    def test_copiar_de_outra_empresa_da_404(self):
        outra = Group.objects.create(name="Outra")
        cliente = Cliente.objects.create(nome_razao_social="Alheio", empresa=outra)
        alheio = self.novo_orcamento(empresa=outra, cliente=cliente)

        resposta = self.client.post(reverse("orcamentos:contrato_do_cliente", args=[alheio.pk]))

        self.assertEqual(resposta.status_code, 404)


class PadroesDaEmpresaTests(BaseFluxoTests):
    def test_orcamento_novo_herda_validade_e_condicoes_do_cadastro(self):
        ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa A",
            empresa=self.grupo,
            validade_padrao_proposta="15 dias",
            condicoes_pagamento_padrao="À vista",
            servicos_taxas_inclusos_padrao="Frete",
        )

        orcamento = self.novo_orcamento()

        self.assertEqual(str(orcamento.validade_em), "2026-11-06")
        self.assertEqual(orcamento.condicoes_pagamento, "À vista")
        self.assertEqual(orcamento.servicos_taxas_inclusos, "Frete")

    def test_o_que_veio_preenchido_nao_e_trocado_pelo_padrao(self):
        ConfiguracaoEmpresa.objects.create(
            nome_empresa="Empresa A", empresa=self.grupo, condicoes_pagamento_padrao="À vista"
        )

        orcamento = self.novo_orcamento(condicoes_pagamento="30/60/90")

        self.assertEqual(orcamento.condicoes_pagamento, "30/60/90")

    def test_cadastro_com_varios_legados_vale_o_ativo_mais_recente(self):
        ConfiguracaoEmpresa.objects.create(nome_empresa="Velho", empresa=self.grupo, ativo=False)
        atual = ConfiguracaoEmpresa.objects.create(nome_empresa="Atual", empresa=self.grupo)

        self.assertEqual(ConfiguracaoEmpresa.da_empresa(self.grupo), atual)
        self.assertIsNone(ConfiguracaoEmpresa.da_empresa(None))


class MigracoesDeDadosTests(BaseFluxoTests):
    """As funções das migrações de dados rodam contra os modelos atuais (o
    esquema é o mesmo), para garantir o efeito sem montar um banco antigo."""

    def test_orcamento_sem_cadastro_e_ligado_ao_da_propria_empresa(self):
        migracao = importlib.import_module(
            "orcamentos.migrations.0010_orcamentos_no_cadastro_da_empresa"
        )
        cadastro = ConfiguracaoEmpresa.objects.create(nome_empresa="Empresa A", empresa=self.grupo)
        orcamento = self.novo_orcamento()
        Orcamento.objects.filter(pk=orcamento.pk).update(configuracao_empresa=None)
        outro = ConfiguracaoEmpresa.objects.create(
            nome_empresa="Outro", empresa=self.grupo, ativo=False
        )
        ja_ligado = self.novo_orcamento()
        Orcamento.objects.filter(pk=ja_ligado.pk).update(configuracao_empresa=outro)

        migracao.ligar_ao_cadastro_da_empresa(django_apps, None)

        orcamento.refresh_from_db()
        ja_ligado.refresh_from_db()
        self.assertEqual(orcamento.configuracao_empresa, cadastro)
        self.assertEqual(ja_ligado.configuracao_empresa, outro)

    def test_usuario_com_duas_empresas_fica_com_a_escolhida(self):
        migracao = importlib.import_module("usuarios.migrations.0004_uma_empresa_por_usuario")
        eventos = Group.objects.create(name="E-ventos")
        through = self.user.groups.through
        # Vínculo duplo gravado direto, como estava antes da regra existir.
        through.objects.create(usuario_id=self.user.pk, group_id=eventos.pk)
        self.assertEqual(self.user.groups.count(), 2)

        migracao.manter_uma_empresa(django_apps, None)

        self.assertEqual(list(self.user.groups.values_list("name", flat=True)), ["E-ventos"])

    def test_sem_escolha_fica_a_empresa_com_mais_orcamentos_do_usuario(self):
        migracao = importlib.import_module("usuarios.migrations.0004_uma_empresa_por_usuario")
        outra = Group.objects.create(name="Outra")
        self.user.groups.through.objects.create(usuario_id=self.user.pk, group_id=outra.pk)
        self.novo_orcamento(empresa=outra)
        self.novo_orcamento(empresa=outra)
        self.novo_orcamento()

        migracao.manter_uma_empresa(django_apps, None)

        self.assertEqual(list(self.user.groups.values_list("name", flat=True)), ["Outra"])
