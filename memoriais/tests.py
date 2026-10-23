"""Testes da importação de memorial com IA.

A API da Anthropic é trocada no ponto mais externo (`services.obter_cliente`)
por um cliente falso que devolve JSON fixo. O resto roda de verdade:
extração do arquivo, validação, preço vindo do catálogo, transação, tenancy e
as telas.
"""

import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest import mock
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from catalogo.models import CategoriaItem, ItemCatalogo
from clientes.models import Cliente
from core.models import Empresa
from core.testing import SENHA_TESTE
from orcamentos.models import Orcamento

from . import services
from .extracao import MemorialInvalido, ler_memorial
from .models import ImportacaoMemorial

MEMORIAL = (
    "MEMORIAL DESCRITIVO. Montagem de 3 estandes de 3x3 m para a Feira Estadual "
    "de Agricultura, no Parque de Exposições de Esteio, de 10 a 14/11/2026. "
    "Cada estande com piso elevado e carpete cinza."
)


def resposta_ia(itens, pendencias=None, orcamento=None):
    return {
        "orcamento": orcamento
        or {
            "titulo": "Feira Estadual de Agricultura",
            "evento_nome": "Feira Estadual de Agricultura",
            "evento_local": "Parque de Exposições de Esteio",
            "evento_periodo": "10 a 14/11/2026",
            "evento_area": "27 m2",
            "descricao_inicial": "Montagem de 3 estandes de 3x3 m.",
            "contratante_nome": "",
            "contratante_cnpj": "",
            "contratante_endereco": "",
            "contratante_cidade": "",
        },
        "itens": itens,
        "pendencias": pendencias or [],
    }


def sugestao(
    codigo="", nome="Piso elevado", quantidade: object = 27, unidade="m2", confianca="alta"
):
    return {
        "catalogo_codigo": codigo,
        "nome": nome,
        "descricao": f"{nome} conforme memorial",
        "unidade": unidade,
        "quantidade": quantidade,
        "justificativa": "3 estandes de 3x3 m = 27 m2",
        "trecho_memorial": "item 2.1",
        "confianca": confianca,
        "categoria_sugerida": "",
    }


class ClienteFalso:
    """Imita `client.messages.stream(...)` como context manager."""

    def __init__(self, dados=None, *, stop_reason="end_turn", erro=None):
        self.dados = dados
        self.stop_reason = stop_reason
        self.erro = erro
        self.chamadas = []
        self.messages = self

    def stream(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.erro is not None:
            raise self.erro
        mensagem = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(self.dados))],
            stop_reason=self.stop_reason,
            model="claude-sonnet-5",
            usage=SimpleNamespace(input_tokens=1200, output_tokens=800),
        )
        fluxo = mock.MagicMock()
        fluxo.__enter__.return_value.get_final_message.return_value = mensagem
        return fluxo


def docx_com(paragrafos, tabela=None):
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    corpo = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragrafos)
    if tabela:
        linhas = "".join(
            "<w:tr>"
            + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in linha)
            + "</w:tr>"
            for linha in tabela
        )
        corpo += f"<w:tbl>{linhas}</w:tbl>"
    xml = f'<?xml version="1.0"?><w:document {ns}><w:body>{corpo}</w:body></w:document>'
    buffer = BytesIO()
    with ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("word/document.xml", xml)
    return buffer.getvalue()


@override_settings(ANTHROPIC_API_KEY="chave-de-teste", MEMORIAL_IA_ASSINCRONO=False)
class BaseMemorialTests(TestCase):
    def setUp(self):
        self.grupo = Group.objects.create(name="Empresa A")
        Empresa.objects.get_or_create(grupo=self.grupo, defaults={"nome": "Empresa A"})
        self.user = get_user_model().objects.create_user(
            username="orcamentista", password=SENHA_TESTE, perfil="orcamentista"
        )
        self.user.groups.add(self.grupo)
        self.client.force_login(self.user)

        categoria = CategoriaItem.objects.create(nome="Pisos", empresa=self.grupo)
        self.piso = ItemCatalogo.objects.create(
            nome="Piso elevado",
            categoria=categoria,
            unidade_medida="m2",
            valor_unitario_padrao=Decimal("85.50"),
            empresa=self.grupo,
        )
        self.carpete = ItemCatalogo.objects.create(
            nome="Carpete",
            categoria=categoria,
            unidade_medida="m2",
            valor_unitario_padrao=Decimal("32.00"),
            empresa=self.grupo,
        )
        self.cliente_obj = Cliente.objects.create(
            nome_razao_social="Prefeitura", empresa=self.grupo
        )
        self.orcamento = Orcamento.objects.create(
            cliente=self.cliente_obj,
            titulo="Edital 12/2026",
            data_emissao=date(2026, 10, 22),
            empresa=self.grupo,
            criado_por=self.user,
            atualizado_por=self.user,
        )
        self.url_importar = reverse("memoriais:importar", args=[self.orcamento.pk])

    def importar(self, cliente_falso, **dados):
        dados.setdefault("texto", MEMORIAL)
        dados.setdefault("incluir_fora_catalogo", "on")
        dados.setdefault("preencher_evento", "on")
        with mock.patch.object(services, "obter_cliente", return_value=cliente_falso):
            with self.captureOnCommitCallbacks(execute=True):
                resposta = self.client.post(self.url_importar, dados)
        return resposta


class ImportacaoFluxoTests(BaseMemorialTests):
    def test_cria_itens_com_preco_do_catalogo_e_nao_da_ia(self):
        falso = ClienteFalso(
            resposta_ia(
                [
                    sugestao(self.piso.codigo, quantidade=27),
                    sugestao(self.carpete.codigo, nome="Carpete", quantidade="27.4"),
                ]
            )
        )
        resposta = self.importar(falso)

        importacao = ImportacaoMemorial.objects.get()
        self.assertRedirects(
            resposta, reverse("memoriais:status", args=[self.orcamento.pk, importacao.pk])
        )
        self.assertEqual(importacao.status, "concluida", importacao.erro)
        self.assertEqual(importacao.itens_criados, 2)
        self.assertEqual(importacao.tokens_entrada, 1200)

        itens = list(self.orcamento.itens.order_by("ordem"))
        self.assertEqual([i.item_catalogo_id for i in itens], [self.piso.pk, self.carpete.pk])
        self.assertEqual(itens[0].valor_unitario, Decimal("85.50"))
        self.assertEqual(itens[0].quantidade, Decimal("27.00"))
        self.assertEqual(itens[1].quantidade, Decimal("27.40"))
        self.assertIn("27 m2", itens[0].observacoes)

        self.orcamento.refresh_from_db()
        esperado = Decimal("27") * Decimal("85.50") + Decimal("27.40") * Decimal("32.00")
        self.assertEqual(self.orcamento.subtotal_itens, esperado)

    def test_catalogo_vai_para_a_ia_sem_precos(self):
        falso = ClienteFalso(resposta_ia([]))
        self.importar(falso)

        conteudo = falso.chamadas[0]["messages"][0]["content"]
        pedido = conteudo[-1]["text"]
        self.assertIn(self.piso.codigo, pedido)
        self.assertNotIn("85.50", pedido)
        self.assertNotIn("85,50", pedido)
        self.assertEqual(falso.chamadas[0]["model"], "claude-sonnet-5")
        self.assertEqual(falso.chamadas[0]["output_config"]["format"]["type"], "json_schema")

    def test_item_fora_do_catalogo_entra_com_valor_zero(self):
        falso = ClienteFalso(
            resposta_ia([sugestao("", nome="Ponto de energia 220V", unidade="un")])
        )
        self.importar(falso)

        item = self.orcamento.itens.get()
        self.assertIsNone(item.item_catalogo_id)
        self.assertEqual(item.nome, "Ponto de energia 220V")
        self.assertEqual(item.valor_unitario, Decimal("0.00"))

    def test_fora_do_catalogo_desmarcado_nao_cria_item(self):
        falso = ClienteFalso(resposta_ia([sugestao(""), sugestao(self.piso.codigo)]))
        self.importar(falso, incluir_fora_catalogo="")

        self.assertEqual(self.orcamento.itens.count(), 1)
        importacao = ImportacaoMemorial.objects.get()
        self.assertEqual(importacao.resultado["itens"][0]["situacao"], "ignorado")

    def test_mesmo_codigo_em_outra_empresa_nunca_puxa_item_nem_preco_dela(self):
        # O código do catálogo é sequencial POR EMPRESA: a B também tem um
        # CAT-ITEM-0001. O código tem de resolver no catálogo da dona do
        # orçamento, nunca no da outra.
        outro = Group.objects.create(name="Empresa B")
        categoria_b = CategoriaItem.objects.create(nome="Pisos B", empresa=outro)
        alheio = ItemCatalogo.objects.create(
            nome="Piso da B",
            categoria=categoria_b,
            unidade_medida="m2",
            valor_unitario_padrao=Decimal("999.00"),
            empresa=outro,
        )
        self.assertEqual(alheio.codigo, self.piso.codigo)
        falso = ClienteFalso(resposta_ia([sugestao(alheio.codigo)]))
        self.importar(falso)

        item = self.orcamento.itens.get()
        self.assertEqual(item.item_catalogo_id, self.piso.pk)
        self.assertEqual(item.valor_unitario, Decimal("85.50"))
        self.assertNotIn("Piso da B", falso.chamadas[0]["messages"][0]["content"][-1]["text"])

    def test_codigo_que_nao_existe_no_catalogo_vira_item_sem_preco(self):
        falso = ClienteFalso(resposta_ia([sugestao("CAT-ITEM-9999", nome="Inventado")]))
        self.importar(falso)

        item = self.orcamento.itens.get()
        self.assertIsNone(item.item_catalogo_id)
        self.assertEqual(item.valor_unitario, Decimal("0.00"))

    def test_quantidade_absurda_ou_invalida_e_saneada(self):
        falso = ClienteFalso(
            resposta_ia(
                [
                    sugestao(self.piso.codigo, quantidade=-5),
                    sugestao(self.carpete.codigo, quantidade=1e20),
                ]
            )
        )
        self.importar(falso)

        quantidades = list(
            self.orcamento.itens.order_by("ordem").values_list("quantidade", flat=True)
        )
        self.assertEqual(quantidades[0], Decimal("1.00"))
        self.assertEqual(quantidades[1], Decimal("9999999999.99"))

    def test_preenche_so_campos_do_evento_em_branco(self):
        self.orcamento.evento_local = "Local digitado pelo usuário"
        self.orcamento.save()
        self.importar(ClienteFalso(resposta_ia([])))

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.evento_local, "Local digitado pelo usuário")
        self.assertEqual(self.orcamento.evento_nome, "Feira Estadual de Agricultura")
        self.assertEqual(self.orcamento.evento_periodo, "10 a 14/11/2026")

    def test_nao_preenche_evento_quando_desmarcado(self):
        self.importar(ClienteFalso(resposta_ia([])), preencher_evento="")
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.evento_nome, "")

    def test_itens_novos_vao_depois_dos_existentes(self):
        self.orcamento.itens.create(nome="Já existia", valor_unitario=Decimal("10"), ordem=1)
        self.importar(ClienteFalso(resposta_ia([sugestao(self.piso.codigo)])))

        nomes = list(self.orcamento.itens.order_by("ordem").values_list("nome", flat=True))
        self.assertEqual(nomes, ["Já existia", "Piso elevado"])


class ImportacaoFalhasTests(BaseMemorialTests):
    def test_resposta_cortada_vira_erro_legivel_e_nao_cria_nada(self):
        falso = ClienteFalso(resposta_ia([sugestao(self.piso.codigo)]), stop_reason="max_tokens")
        self.importar(falso)

        importacao = ImportacaoMemorial.objects.get()
        self.assertEqual(importacao.status, "erro")
        self.assertIn("cortada", importacao.erro)
        self.assertEqual(self.orcamento.itens.count(), 0)

    def test_falha_de_api_vira_erro_legivel(self):
        import anthropic
        import httpx

        erro = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api"))
        self.importar(ClienteFalso(erro=erro))

        importacao = ImportacaoMemorial.objects.get()
        self.assertEqual(importacao.status, "erro")
        self.assertIn("Tente de novo", importacao.erro)

    def test_erro_inesperado_desfaz_itens_ja_criados(self):
        falso = ClienteFalso(
            resposta_ia([sugestao(self.piso.codigo), sugestao(self.carpete.codigo)])
        )
        with (
            mock.patch.object(services, "preencher_dados_gerais", side_effect=RuntimeError("bug")),
            self.assertLogs("memoriais.services", level="ERROR"),
        ):
            self.importar(falso)

        importacao = ImportacaoMemorial.objects.get()
        self.assertEqual(importacao.status, "erro")
        self.assertEqual(self.orcamento.itens.count(), 0)

    def test_importacao_travada_expira_e_libera_nova(self):
        travada = ImportacaoMemorial.objects.create(
            orcamento=self.orcamento, empresa=self.grupo, status="processando"
        )
        ImportacaoMemorial.objects.filter(pk=travada.pk).update(
            atualizado_em=travada.atualizado_em.replace(year=2020)
        )
        resposta = self.client.get(self.url_importar)

        self.assertEqual(resposta.status_code, 200)
        travada.refresh_from_db()
        self.assertEqual(travada.status, "erro")

    def test_importacao_em_andamento_redireciona_para_o_status(self):
        andamento = ImportacaoMemorial.objects.create(
            orcamento=self.orcamento, empresa=self.grupo, status="processando"
        )
        resposta = self.client.get(self.url_importar)
        self.assertRedirects(
            resposta, reverse("memoriais:status", args=[self.orcamento.pk, andamento.pk])
        )

    @override_settings(MEMORIAL_IA_LIMITE_DIARIO=1)
    def test_limite_diario(self):
        ImportacaoMemorial.objects.create(
            orcamento=self.orcamento, empresa=self.grupo, status="concluida"
        )
        falso = ClienteFalso(resposta_ia([]))
        resposta = self.importar(falso)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "limite diário")
        self.assertEqual(falso.chamadas, [])


class PermissoesTests(BaseMemorialTests):
    def orcamento_de_outra_empresa(self):
        outro = Group.objects.create(name="Empresa B")
        dono = get_user_model().objects.create_user(username="da_b", password=SENHA_TESTE)
        dono.groups.add(outro)
        return Orcamento.objects.create(
            cliente=Cliente.objects.create(nome_razao_social="X", empresa=outro),
            titulo="Alheio",
            data_emissao=date(2026, 10, 22),
            empresa=outro,
            criado_por=dono,
            atualizado_por=dono,
        )

    def test_orcamento_de_outra_empresa_da_404(self):
        alheio = self.orcamento_de_outra_empresa()
        resposta = self.client.get(reverse("memoriais:importar", args=[alheio.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_orcamento_fora_de_rascunho_e_bloqueado(self):
        self.orcamento.status = "enviado"
        self.orcamento.save()
        resposta = self.client.get(self.url_importar)
        self.assertEqual(resposta.status_code, 403)

    def test_status_de_importacao_de_outra_empresa_da_404(self):
        alheio = self.orcamento_de_outra_empresa()
        importacao = ImportacaoMemorial.objects.create(orcamento=alheio, empresa=alheio.empresa)
        resposta = self.client.get(reverse("memoriais:status", args=[alheio.pk, importacao.pk]))
        self.assertEqual(resposta.status_code, 404)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sem_chave_o_botao_some_e_a_rota_avisa(self):
        editar = self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))
        self.assertNotContains(editar, self.url_importar)

        resposta = self.client.get(self.url_importar)
        self.assertRedirects(resposta, reverse("orcamentos:editar", args=[self.orcamento.pk]))

    def test_com_chave_o_botao_aparece_na_edicao(self):
        editar = self.client.get(reverse("orcamentos:editar", args=[self.orcamento.pk]))
        self.assertContains(editar, self.url_importar)
        self.assertContains(editar, "Importar memorial com IA")


class TelasTests(BaseMemorialTests):
    def test_tela_de_importacao_renderiza(self):
        resposta = self.client.get(self.url_importar)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Importar memorial descritivo")
        self.assertContains(resposta, "css/memoriais.css")

    def test_formulario_sem_arquivo_nem_texto_reclama(self):
        resposta = self.client.post(self.url_importar, {"texto": ""})
        self.assertContains(resposta, "Envie o arquivo do memorial")
        self.assertFalse(ImportacaoMemorial.objects.exists())

    def test_status_concluido_mostra_resumo_e_pendencias(self):
        self.importar(
            ClienteFalso(
                resposta_ia(
                    [sugestao(self.piso.codigo), sugestao("", nome="Ponto de energia")],
                    pendencias=["Confirmar quem fornece a energia elétrica."],
                )
            )
        )
        importacao = ImportacaoMemorial.objects.get()
        resposta = self.client.get(
            reverse("memoriais:status", args=[self.orcamento.pk, importacao.pk])
        )
        self.assertContains(resposta, "2 itens adicionados")
        self.assertContains(resposta, "Confirmar quem fornece a energia elétrica.")
        self.assertContains(resposta, "Fora do catálogo, com valor zero")
        self.assertNotContains(resposta, "data-poll-url")

    def test_status_em_andamento_faz_polling_e_partial_responde(self):
        importacao = ImportacaoMemorial.objects.create(
            orcamento=self.orcamento, empresa=self.grupo, status="processando"
        )
        url = reverse("memoriais:status", args=[self.orcamento.pk, importacao.pk])
        self.assertContains(self.client.get(url), "data-poll-url")

        parcial = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertContains(parcial, "data-memorial-andamento")
        self.assertNotContains(parcial, "<html")

    def test_seguir_leva_para_a_edicao_com_mensagem(self):
        self.importar(ClienteFalso(resposta_ia([sugestao(self.piso.codigo)])))
        importacao = ImportacaoMemorial.objects.get()
        url = reverse("memoriais:status", args=[self.orcamento.pk, importacao.pk])
        resposta = self.client.get(url + "?seguir=1", follow=True)
        self.assertRedirects(resposta, reverse("orcamentos:editar", args=[self.orcamento.pk]))
        self.assertContains(resposta, "1 itens adicionados")


class ExtracaoTests(TestCase):
    def arquivo(self, nome, conteudo):
        return SimpleUploadedFile(nome, conteudo)

    def test_pdf_vai_como_documento(self):
        memorial = ler_memorial(self.arquivo("edital.pdf", b"%PDF-1.7 conteudo"))
        bloco = memorial.blocos_conteudo()[0]
        self.assertEqual(bloco["type"], "document")
        self.assertEqual(bloco["source"]["media_type"], "application/pdf")

    def test_pdf_falso_e_recusado(self):
        with self.assertRaises(MemorialInvalido):
            ler_memorial(self.arquivo("edital.pdf", b"nao sou pdf"))

    def test_docx_le_paragrafos_e_tabelas_em_ordem(self):
        conteudo = docx_com(
            ["Memorial descritivo do estande da feira estadual de agricultura"],
            tabela=[["Item", "Qtd"], ["Piso elevado", "27 m2"]],
        )
        memorial = ler_memorial(self.arquivo("memorial.docx", conteudo))
        self.assertIn("Memorial descritivo", memorial.texto)
        self.assertIn("Piso elevado | 27 m2", memorial.texto)

    def test_docx_corrompido(self):
        with self.assertRaises(MemorialInvalido):
            ler_memorial(self.arquivo("memorial.docx", b"PK\x03\x04 lixo"))

    def test_txt_em_cp1252(self):
        texto = "Memorial: instalação elétrica e iluminação do estande, área de 27 m²."
        memorial = ler_memorial(self.arquivo("m.txt", texto.encode("cp1252")))
        self.assertIn("instalação elétrica", memorial.texto)

    def test_extensao_nao_aceita(self):
        with self.assertRaises(MemorialInvalido):
            ler_memorial(self.arquivo("memorial.exe", b"MZ" * 100))

    @override_settings(MEMORIAL_IA_MAX_UPLOAD_BYTES=1024)
    def test_arquivo_grande_demais(self):
        with self.assertRaises(MemorialInvalido):
            ler_memorial(self.arquivo("edital.pdf", b"%PDF" + b"x" * 2048))

    def test_texto_curto_demais(self):
        with self.assertRaises(MemorialInvalido):
            ler_memorial(texto_colado="estande")

    def test_texto_colado_vai_dentro_de_tag(self):
        memorial = ler_memorial(texto_colado=MEMORIAL)
        self.assertTrue(memorial.blocos_conteudo()[0]["text"].startswith("<memorial>"))
