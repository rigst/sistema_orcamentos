"""Início pelo memorial (título, cliente e contrato vindos do edital) e a
passagem dos itens novos da IA para o catálogo.

Mesma estratégia de `tests.py`: a API é trocada em `services.obter_cliente`
por um cliente falso, e o resto roda de verdade.
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group
from django.urls import reverse

from catalogo.models import CategoriaItem
from clientes.models import Cliente
from orcamentos.models import Orcamento

from . import services
from .models import ImportacaoMemorial
from .tests import MEMORIAL, BaseMemorialTests, ClienteFalso, resposta_ia, sugestao


def resposta_com_contratante(itens=None, **contratante):
    dados = resposta_ia(itens or [])
    dados["orcamento"].update(
        {
            "titulo": "Estande FENAGRO 2026 - Pregão 087/2026",
            "contratante_nome": "Prefeitura Municipal de Santa Cruz do Sul",
            "contratante_cnpj": "95.440.517/0001-08",
            "contratante_endereco": "Rua Coronel Oscar Jost, 1551",
            "contratante_cidade": "Santa Cruz do Sul/RS",
            **contratante,
        }
    )
    return dados


class NovoComMemorialTests(BaseMemorialTests):
    url = "/orcamentos/novo/memorial/"

    def criar(self, falso, **dados):
        dados.setdefault("texto", MEMORIAL)
        dados.setdefault("incluir_fora_catalogo", "on")
        dados.setdefault("preencher_evento", "on")
        with mock.patch.object(services, "obter_cliente", return_value=falso):
            with self.captureOnCommitCallbacks(execute=True):
                return self.client.post(reverse("memoriais:novo_com_memorial"), dados)

    def test_cria_orcamento_e_ia_preenche_titulo_cliente_e_contrato(self):
        resposta = self.criar(ClienteFalso(resposta_com_contratante([sugestao(self.piso.codigo)])))

        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        importacao = ImportacaoMemorial.objects.get(orcamento=novo)
        self.assertRedirects(resposta, reverse("memoriais:status", args=[novo.pk, importacao.pk]))
        self.assertEqual(importacao.status, "concluida", importacao.erro)
        self.assertEqual(novo.titulo, "Estande FENAGRO 2026 - Pregão 087/2026")
        self.assertEqual(
            novo.cliente.nome_razao_social, "Prefeitura Municipal de Santa Cruz do Sul"
        )
        self.assertEqual(novo.cliente.empresa, self.grupo)
        self.assertEqual(novo.cliente.cpf_cnpj, "95.440.517/0001-08")
        self.assertEqual(novo.cliente.tipo_pessoa, "PJ")
        self.assertEqual(novo.cliente.cidade, "Santa Cruz do Sul")
        self.assertEqual(novo.cliente.estado, "RS")
        self.assertEqual(novo.contrato_razao_social, "Prefeitura Municipal de Santa Cruz do Sul")
        self.assertEqual(novo.contrato_cnpj, "95.440.517/0001-08")
        self.assertEqual(novo.evento_nome, "Feira Estadual de Agricultura")
        self.assertEqual(novo.itens.count(), 1)
        self.assertTrue(importacao.resultado["cliente"]["criado"])

    def test_reaproveita_cliente_existente_pelo_cnpj(self):
        existente = Cliente.objects.create(
            nome_razao_social="Pref. Santa Cruz", cpf_cnpj="95440517000108", empresa=self.grupo
        )
        self.criar(ClienteFalso(resposta_com_contratante()))
        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertEqual(novo.cliente, existente)
        self.assertEqual(Cliente.objects.filter(empresa=self.grupo).count(), 2)

    def test_reaproveita_cliente_existente_pelo_nome(self):
        existente = Cliente.objects.create(
            nome_razao_social="PREFEITURA MUNICIPAL DE SANTA CRUZ DO SUL", empresa=self.grupo
        )
        self.criar(ClienteFalso(resposta_com_contratante(contratante_cnpj="")))
        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertEqual(novo.cliente, existente)

    def test_nunca_vincula_cliente_de_outra_empresa(self):
        outro = Group.objects.create(name="Empresa B")
        alheio = Cliente.objects.create(
            nome_razao_social="Prefeitura Municipal de Santa Cruz do Sul",
            cpf_cnpj="95.440.517/0001-08",
            empresa=outro,
        )
        self.criar(ClienteFalso(resposta_com_contratante()))
        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertNotEqual(novo.cliente, alheio)
        self.assertEqual(novo.cliente.empresa, self.grupo)

    def test_cliente_escolhido_pelo_usuario_prevalece(self):
        self.criar(ClienteFalso(resposta_com_contratante()), cliente=self.cliente_obj.pk)
        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertEqual(novo.cliente, self.cliente_obj)
        self.assertFalse(
            Cliente.objects.filter(nome_razao_social__startswith="Prefeitura Mun").exists()
        )

    def test_memorial_sem_contratante_deixa_sem_cliente(self):
        self.criar(ClienteFalso(resposta_ia([])))
        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertIsNone(novo.cliente_id)
        self.assertEqual(novo.titulo, "Feira Estadual de Agricultura")

    def test_cnpj_invalido_nao_vai_para_o_cadastro(self):
        self.criar(ClienteFalso(resposta_com_contratante(contratante_cnpj="não informado")))
        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertEqual(novo.cliente.cpf_cnpj, "")
        self.assertEqual(novo.contrato_cnpj, "")

    def test_formulario_invalido_nao_cria_orcamento(self):
        resposta = self.criar(ClienteFalso(resposta_ia([])), texto="")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Orcamento.objects.count(), 1)

    def test_falha_da_ia_mantem_orcamento_em_branco_editavel(self):
        self.criar(ClienteFalso(resposta_ia([]), stop_reason="max_tokens"))
        novo = Orcamento.objects.exclude(pk=self.orcamento.pk).get()
        self.assertEqual(novo.titulo, Orcamento.TITULO_GENERICO)
        self.assertEqual(novo.status, "rascunho")

    def test_titulo_ja_escrito_nao_e_sobrescrito_na_importacao(self):
        self.importar(ClienteFalso(resposta_com_contratante()))
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.titulo, "Edital 12/2026")
        self.assertEqual(self.orcamento.cliente, self.cliente_obj)


class SalvarNoCatalogoTests(BaseMemorialTests):
    def setUp(self):
        super().setUp()
        self.user.perfil = "admin"
        self.user.save()

    def importar_com_novos(self):
        dados = resposta_ia(
            [
                sugestao(self.piso.codigo),
                {
                    **sugestao("", nome="Ponto de energia 220V", unidade="un"),
                    "categoria_sugerida": "pisos",
                },
                {
                    **sugestao("", nome="Quadro elétrico", unidade="un"),
                    "categoria_sugerida": "ELÉTRICA",
                },
            ]
        )
        self.importar(ClienteFalso(dados))
        return ImportacaoMemorial.objects.get()

    def url(self, importacao):
        return reverse("memoriais:salvar_catalogo", args=[self.orcamento.pk, importacao.pk])

    def test_tela_lista_so_os_itens_novos_com_a_categoria_sugerida(self):
        importacao = self.importar_com_novos()
        resposta = self.client.get(
            reverse("memoriais:status", args=[self.orcamento.pk, importacao.pk])
        )
        self.assertContains(resposta, "Levar itens novos para o catálogo")
        self.assertContains(resposta, "Ponto de energia 220V")
        self.assertContains(resposta, "Quadro elétrico")
        categoria = CategoriaItem.objects.get(nome="Pisos")
        self.assertContains(
            resposta, f'<option value="{categoria.pk}" selected>Pisos</option>', html=True
        )
        self.assertContains(resposta, 'value="ELÉTRICA"')

    def test_salva_em_categoria_existente_e_nova_com_o_valor_ajustado(self):
        importacao = self.importar_com_novos()
        energia = self.orcamento.itens.get(nome="Ponto de energia 220V")
        quadro = self.orcamento.itens.get(nome="Quadro elétrico")
        energia.valor_unitario = Decimal("180.00")
        energia.save()
        categoria = CategoriaItem.objects.get(nome="Pisos")

        resposta = self.client.post(
            self.url(importacao),
            {
                f"item_{energia.pk}": "on",
                f"categoria_{energia.pk}": str(categoria.pk),
                f"item_{quadro.pk}": "on",
                f"categoria_{quadro.pk}": "nova",
                f"categoria_nova_{quadro.pk}": "  INSTALAÇÕES   ELÉTRICAS ",
            },
        )
        self.assertRedirects(
            resposta, reverse("memoriais:status", args=[self.orcamento.pk, importacao.pk])
        )

        energia.refresh_from_db()
        quadro.refresh_from_db()
        self.assertEqual(energia.item_catalogo.categoria, categoria)
        self.assertEqual(energia.item_catalogo.valor_unitario_padrao, Decimal("180.00"))
        self.assertEqual(energia.item_catalogo.empresa, self.grupo)
        self.assertEqual(quadro.item_catalogo.categoria.nome, "INSTALAÇÕES ELÉTRICAS")
        self.assertEqual(quadro.item_catalogo.categoria.empresa, self.grupo)
        self.assertFalse(energia.diverge_catalogo)

        importacao.refresh_from_db()
        salvos = [i for i in importacao.resultado["itens"] if i.get("salvo_no_catalogo")]
        self.assertEqual(len(salvos), 2)
        tela = self.client.get(reverse("memoriais:status", args=[self.orcamento.pk, importacao.pk]))
        self.assertNotContains(tela, "Levar itens novos para o catálogo")

    def test_so_salva_os_marcados(self):
        importacao = self.importar_com_novos()
        energia = self.orcamento.itens.get(nome="Ponto de energia 220V")
        quadro = self.orcamento.itens.get(nome="Quadro elétrico")
        self.client.post(
            self.url(importacao),
            {
                f"item_{energia.pk}": "on",
                f"categoria_{energia.pk}": "nova",
                f"categoria_nova_{energia.pk}": "ENERGIA",
                f"categoria_{quadro.pk}": "nova",
                f"categoria_nova_{quadro.pk}": "X",
            },
        )
        quadro.refresh_from_db()
        self.assertIsNone(quadro.item_catalogo_id)
        self.assertFalse(CategoriaItem.objects.filter(nome="X").exists())

    def test_mesma_categoria_nova_para_dois_itens_cria_uma_so(self):
        importacao = self.importar_com_novos()
        ids = list(
            self.orcamento.itens.filter(item_catalogo__isnull=True).values_list("pk", flat=True)
        )
        dados = {}
        for pk in ids:
            dados.update(
                {f"item_{pk}": "on", f"categoria_{pk}": "nova", f"categoria_nova_{pk}": "Elétrica"}
            )
        dados[f"categoria_nova_{ids[1]}"] = "ELÉTRICA"
        self.client.post(self.url(importacao), dados)
        self.assertEqual(CategoriaItem.objects.filter(nome__iexact="elétrica").count(), 1)

    def test_categoria_nova_sem_nome_nao_salva(self):
        importacao = self.importar_com_novos()
        energia = self.orcamento.itens.get(nome="Ponto de energia 220V")
        resposta = self.client.post(
            self.url(importacao),
            {
                f"item_{energia.pk}": "on",
                f"categoria_{energia.pk}": "nova",
                f"categoria_nova_{energia.pk}": "  ",
            },
            follow=True,
        )
        self.assertContains(resposta, "Nenhum item foi salvo")
        energia.refresh_from_db()
        self.assertIsNone(energia.item_catalogo_id)

    def test_nao_aceita_item_que_nao_veio_desta_importacao(self):
        importacao = self.importar_com_novos()
        avulso = self.orcamento.itens.create(nome="Avulso", valor_unitario=1, ordem=99)
        self.client.post(
            self.url(importacao),
            {
                f"item_{avulso.pk}": "on",
                f"categoria_{avulso.pk}": "nova",
                f"categoria_nova_{avulso.pk}": "Y",
            },
        )
        avulso.refresh_from_db()
        self.assertIsNone(avulso.item_catalogo_id)

    def test_categoria_de_outra_empresa_e_ignorada(self):
        importacao = self.importar_com_novos()
        outro = Group.objects.create(name="Empresa B")
        alheia = CategoriaItem.objects.create(nome="Da B", empresa=outro)
        energia = self.orcamento.itens.get(nome="Ponto de energia 220V")
        self.client.post(
            self.url(importacao),
            {f"item_{energia.pk}": "on", f"categoria_{energia.pk}": str(alheia.pk)},
        )
        energia.refresh_from_db()
        self.assertIsNone(energia.item_catalogo_id)

    def test_orcamentista_sem_permissao_de_catalogo_nao_ve_nem_salva(self):
        importacao = self.importar_com_novos()
        self.user.perfil = "orcamentista"
        self.user.save()
        self.assertFalse(self.user.pode_gerenciar_catalogo)
        tela = self.client.get(reverse("memoriais:status", args=[self.orcamento.pk, importacao.pk]))
        self.assertNotContains(tela, "Levar itens novos para o catálogo")
        energia = self.orcamento.itens.get(nome="Ponto de energia 220V")
        resposta = self.client.post(self.url(importacao), {f"item_{energia.pk}": "on"})
        self.assertEqual(resposta.status_code, 403)
