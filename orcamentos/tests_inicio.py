"""Página inicial (saudação, frase, cor por orçamento, linha clicável),
cabeçalho, ícones das categorias e conferência dos totais."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.urls import reverse

from catalogo.icones import ICONES, icone_sugerido, svg_icone
from catalogo.models import CategoriaItem, ItemCatalogo
from core.testing import SENHA_TESTE

from .models import NAO_REGISTRADO, ItemOrcamento, Orcamento
from .saudacao import FRASES, frase_do_momento, saudacao
from .tests_fluxo import BaseFluxoTests

SP = ZoneInfo("America/Sao_Paulo")


class SaudacaoTests(BaseFluxoTests):
    def test_saudacao_pela_hora(self):
        self.assertEqual(saudacao(datetime(2026, 10, 23, 8, tzinfo=SP)), "Bom dia")
        self.assertEqual(saudacao(datetime(2026, 10, 23, 14, tzinfo=SP)), "Boa tarde")
        self.assertEqual(saudacao(datetime(2026, 10, 23, 21, tzinfo=SP)), "Boa noite")
        self.assertEqual(saudacao(datetime(2026, 10, 23, 3, tzinfo=SP)), "Boa noite")

    def test_frase_vem_da_lista_e_varia(self):
        textos = {frase_do_momento(semente)["texto"] for semente in range(len(FRASES))}
        # Todas aparecem e sementes seguidas trocam a frase.
        self.assertEqual(len(textos), len(FRASES))
        self.assertNotEqual(frase_do_momento(1)["texto"], frase_do_momento(2)["texto"])
        self.assertTrue(textos <= {t for t, _ in FRASES})

    def test_inicio_saluda_pelo_primeiro_nome_com_frase_e_foto(self):
        self.user.nome_exibicao = "rodrigo stolben"
        self.user.save()

        conteudo = self.client.get(reverse("orcamentos:lista")).content.decode()

        self.assertRegex(conteudo, r"(Bom dia|Boa tarde|Boa noite), Rodrigo\.")
        self.assertIn('class="inicio-frase"', conteudo)
        self.assertIn("inicio-fundo.webp", conteudo)
        self.assertIn("Jeremy Yap", conteudo)

    def test_sem_nome_a_saudacao_fica_sem_virgula(self):
        self.user.nome_exibicao = ""
        self.user.first_name = ""
        self.user.username = ""
        self.assertEqual(self.user.primeiro_nome, "")


class ListaTests(BaseFluxoTests):
    def test_cada_orcamento_tem_cor_fixa_e_linha_clicavel(self):
        a = self.novo_orcamento(titulo="A")
        b = self.novo_orcamento(titulo="B")

        conteudo = self.client.get(reverse("orcamentos:lista")).content.decode()

        self.assertNotEqual(a.cor_identificacao, b.cor_identificacao)
        self.assertIn(f"--orc-cor: {a.cor_identificacao}", conteudo)
        self.assertIn(f'data-href="{reverse("orcamentos:editar", args=[a.pk])}"', conteudo)
        self.assertIn("js/lista-orcamentos.js", conteudo)

    def test_linha_de_orcamento_enviado_abre_a_visualizacao(self):
        enviado = self.novo_orcamento(status="enviado")
        conteudo = self.client.get(reverse("orcamentos:lista")).content.decode()
        self.assertIn(
            f'data-href="{reverse("orcamentos:visualizar", args=[enviado.pk])}"', conteudo
        )

    def test_cabecalho_so_com_o_nome_e_sem_ola(self):
        self.user.nome_exibicao = "Rod"
        self.user.save()
        menu = self.client.get(reverse("orcamentos:lista")).content.decode().split("<header")[1]
        menu = menu.split("</header>")[0]
        self.assertIn('class="header-user-nome"', menu)
        self.assertNotIn("Olá", menu)
        self.assertLess(menu.index("Catálogo"), menu.index("header-user-nome"))

    def test_novo_orcamento_sem_contagem_de_importacoes(self):
        conteudo = self.client.get(reverse("orcamentos:novo")).content.decode()
        self.assertNotIn("restantes", conteudo)


class IconesTests(BaseFluxoTests):
    def test_icone_sugerido_pelo_nome_das_categorias_reais(self):
        casos = {
            "PISO": "piso",
            "PAREDES": "parede",
            "FORROS E COBERTURAS": "forro",
            "INSTALAÇÕES ELÉTRICAS": "eletrica",
            "MOBILIÁRIOS": "movel",
            "EQUIPAMENTOS": "equipamento",
            "COMUNICAÇÃO VISUAL": "comunicacao",
            "OUTROS ITENS DE MONTAGEM": "ferramenta",
            "Qualquer coisa": "caixa",
        }
        for nome, esperado in casos.items():
            with self.subTest(nome=nome):
                self.assertEqual(icone_sugerido(nome), esperado)

    def test_icone_escolhido_tem_prioridade(self):
        categoria = CategoriaItem.objects.create(nome="PISO", empresa=self.grupo, icone="luz")
        self.assertEqual(categoria.icone_efetivo, "luz")

    def test_svg_e_so_traco_sem_script(self):
        for chave in ICONES:
            svg = str(svg_icone(chave, rotulo="Rótulo <b>"))
            self.assertTrue(svg.startswith("<svg"))
            self.assertNotIn("<script", svg)
            self.assertIn("Rótulo &lt;b&gt;", svg)

    def test_tabela_mostra_icone_na_cor_e_nao_o_nome_da_categoria(self):
        orcamento = self.novo_orcamento()
        categoria = CategoriaItem.objects.create(
            nome="MOBILIÁRIOS", empresa=self.grupo, cor="#7C3AED"
        )
        catalogo = ItemCatalogo.objects.create(
            categoria=categoria,
            empresa=self.grupo,
            nome="Cadeira",
            unidade_medida="un",
            valor_unitario_padrao=30,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            item_catalogo=catalogo,
            nome="Cadeira",
            quantidade=2,
            valor_unitario=30,
            ordem=1,
        )

        conteudo = self.client.get(
            reverse("orcamentos:editar", args=[orcamento.pk])
        ).content.decode()
        tabela = conteudo.split('id="itens-tabela-region"')[1].split("</table>")[0]

        self.assertIn('class="item-icone" style="--category-color: #7C3AED;"', tabela)
        self.assertIn('aria-label="MOBILIÁRIOS"', tabela)
        self.assertNotIn("category-chip", tabela)

    def test_formulario_de_categoria_oferece_os_icones(self):
        admin = self.user.__class__.objects.create_user(
            username="adm_icones", password=SENHA_TESTE, perfil="admin"
        )
        admin.groups.add(self.grupo)
        self.client.force_login(admin)
        conteudo = self.client.get(reverse("catalogo:categoria_criar")).content.decode()
        self.assertIn('name="icone" value="piso"', conteudo)
        self.assertIn('name="icone" value=""', conteudo)


class TotaisConferidosTests(BaseFluxoTests):
    """A conta da tela bate com a refeita item a item, com ajustes por item e globais."""

    def test_subtotais_e_total_com_ajustes_por_item_e_globais(self):
        orcamento = self.novo_orcamento(
            desconto_global_valor=Decimal("15.00"),
            desconto_global_percentual=Decimal("5.00"),
            acrescimo_global_valor=Decimal("7.50"),
            acrescimo_global_percentual=Decimal("2.50"),
        )
        categoria = CategoriaItem.objects.create(nome="PISO", empresa=self.grupo)
        catalogo = ItemCatalogo.objects.create(
            categoria=categoria,
            empresa=self.grupo,
            nome="Piso",
            unidade_medida="m2",
            valor_unitario_padrao=Decimal("85.90"),
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            item_catalogo=catalogo,
            nome="Piso",
            quantidade=Decimal("12.5"),
            valor_unitario=Decimal("85.90"),
            desconto_percentual=Decimal("10"),
            ordem=1,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            nome="Painel",
            quantidade=Decimal("3"),
            valor_unitario=Decimal("199.99"),
            acrescimo_valor=Decimal("20"),
            ordem=2,
        )
        orcamento.refresh_from_db()

        # 12,5 × 85,90 = 1073,75 − 10% (107,38) = 966,37
        # 3 × 199,99 = 599,97 + 20 = 619,97
        self.assertEqual(orcamento.subtotal_itens, Decimal("1586.34"))
        # 1586,34 − 15 − 79,32 + 7,50 + 39,66 = 1539,18
        self.assertEqual(orcamento.valor_desconto_percentual_global, Decimal("79.32"))
        self.assertEqual(orcamento.valor_acrescimo_percentual_global, Decimal("39.66"))
        self.assertEqual(orcamento.total_final, Decimal("1539.18"))

        grupos = orcamento.subtotais_por_categoria(NAO_REGISTRADO)
        self.assertEqual(sum(g["subtotal"] for g in grupos), orcamento.subtotal_itens)
        self.assertEqual([g["subtotal"] for g in grupos], [Decimal("966.37"), Decimal("619.97")])

        tela = self.client.get(reverse("orcamentos:editar", args=[orcamento.pk])).content.decode()
        for valor in ("1.586,34", "79,32", "39,66", "1.539,18", "966,37", "619,97"):
            self.assertIn(valor, tela)

    def test_orcamento_cor_identificacao_e_estavel(self):
        orcamento = self.novo_orcamento()
        mesmo = Orcamento.objects.get(pk=orcamento.pk)
        self.assertEqual(orcamento.cor_identificacao, mesmo.cor_identificacao)
