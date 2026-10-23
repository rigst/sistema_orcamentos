"""Leitura do memorial pela Claude e montagem do orçamento.

O fluxo tem duas metades que não se misturam:

1. `analisar_memorial` conversa com a API e devolve o JSON validado pelo
   schema. Não toca no banco.
2. `aplicar_resultado` transforma esse JSON em itens do orçamento. É aqui que
   o preço entra, sempre a partir do catálogo, nunca da IA.

A chamada leva de 30 s a alguns minutos, então roda numa thread fora do
request (este app não tem Celery). A tela consulta o status por polling.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import close_old_connections, transaction
from django.utils import timezone

from catalogo.models import CategoriaItem, ItemCatalogo
from orcamentos.models import ItemOrcamento

from . import prompts
from .extracao import Memorial
from .models import ImportacaoMemorial
from .preenchimento import preencher_dados_gerais

logger = logging.getLogger(__name__)

DUAS_CASAS = Decimal("0.01")
QUANTIDADE_MAXIMA = Decimal("9999999999.99")  # max_digits=12, decimal_places=2


class IAIndisponivel(RuntimeError):
    """Falha que o usuário pode entender e, em geral, resolver tentando de novo."""


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def obter_cliente():
    chave = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not chave:
        raise IAIndisponivel("A integração com a IA não está configurada neste servidor.")
    import anthropic

    return anthropic.Anthropic(
        api_key=chave,
        timeout=float(getattr(settings, "MEMORIAL_IA_TIMEOUT", 600)),
        max_retries=2,
    )


def _texto_resposta(mensagem):
    return "".join(b.text for b in mensagem.content if getattr(b, "type", "") == "text")


def _parametros_chamada(memorial: Memorial, pedido: str) -> dict:
    return {
        "model": settings.MEMORIAL_IA_MODEL,
        "max_tokens": settings.MEMORIAL_IA_MAX_TOKENS,
        "system": [
            {"type": "text", "text": prompts.SYSTEM, "cache_control": {"type": "ephemeral"}}
        ],
        "messages": [
            {
                "role": "user",
                "content": [*memorial.blocos_conteudo(), {"type": "text", "text": pedido}],
            }
        ],
        "thinking": {"type": "adaptive"},
        "output_config": {
            "effort": settings.MEMORIAL_IA_EFFORT,
            "format": {"type": "json_schema", "schema": prompts.SCHEMA},
        },
    }


def _ler_resposta(mensagem) -> dict:
    if mensagem.stop_reason == "max_tokens":
        raise IAIndisponivel(
            "O orçamento ficou grande demais e a resposta da IA foi cortada. "
            "Divida o memorial em partes e importe uma de cada vez."
        )
    if mensagem.stop_reason == "refusal":
        raise IAIndisponivel("A IA se recusou a processar este documento.")
    try:
        return json.loads(_texto_resposta(mensagem))
    except json.JSONDecodeError as exc:
        raise IAIndisponivel("A resposta da IA veio num formato inesperado.") from exc


def analisar_memorial(memorial: Memorial, catalogo_texto: str, *, instrucoes, incluir_fora):
    """Chama a Claude e devolve (dados, mensagem). Streaming porque a resposta
    de um memorial grande passa fácil de 10 minutos de teto do modo síncrono do
    SDK, e o stream não tem esse teto."""
    import anthropic

    cliente = obter_cliente()
    pedido = prompts.montar_pedido(
        catalogo_texto, instrucoes=instrucoes, incluir_fora_catalogo=incluir_fora
    )
    try:
        with cliente.messages.stream(**_parametros_chamada(memorial, pedido)) as fluxo:
            mensagem = fluxo.get_final_message()
    except anthropic.APIStatusError as exc:
        logger.warning("memorial: API devolveu %s: %s", exc.status_code, exc.message)
        if exc.status_code == 413 or "too long" in str(exc.message).lower():
            raise IAIndisponivel(
                "O memorial é grande demais para a IA ler de uma vez. "
                "Envie só a parte do memorial descritivo."
            ) from exc
        raise IAIndisponivel("A IA recusou o pedido agora. Tente de novo em instantes.") from exc
    except anthropic.APIError as exc:
        logger.warning("memorial: falha de comunicação com a API: %s", exc)
        raise IAIndisponivel("Não consegui falar com a IA. Tente de novo em instantes.") from exc
    return _ler_resposta(mensagem), mensagem


# ---------------------------------------------------------------------------
# Montagem do orçamento
# ---------------------------------------------------------------------------


def _quantidade(valor) -> Decimal:
    try:
        quantidade = Decimal(str(valor)).quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("1.00")
    if not quantidade.is_finite() or quantidade < DUAS_CASAS:
        return Decimal("1.00")
    return min(quantidade, QUANTIDADE_MAXIMA)


def _cortar(texto, limite):
    return " ".join(str(texto or "").split())[:limite]


def _observacao(sugestao):
    partes = [f"Sugerido pela IA (confiança {sugestao.get('confianca', '?')})."]
    if sugestao.get("justificativa"):
        partes.append(str(sugestao["justificativa"]).strip())
    if sugestao.get("trecho_memorial"):
        partes.append(f"Ref.: {str(sugestao['trecho_memorial']).strip()}")
    return " ".join(partes)


def _montar_item(orcamento, sugestao, catalogo_por_codigo, incluir_fora):
    """ItemOrcamento ainda não salvo, ou None se a sugestão não vira item.
    O valor vem do catálogo; item fora do catálogo entra com zero."""
    codigo = str(sugestao.get("catalogo_codigo") or "").strip()
    do_catalogo = catalogo_por_codigo.get(codigo) if codigo else None
    if do_catalogo is None and not incluir_fora:
        return None

    item = ItemOrcamento(
        orcamento=orcamento,
        quantidade=_quantidade(sugestao.get("quantidade")),
        observacoes=_observacao(sugestao),
    )
    if do_catalogo is not None:
        item.item_catalogo = do_catalogo
        item.nome = do_catalogo.nome
        item.unidade_medida = do_catalogo.unidade_medida
        item.valor_unitario = do_catalogo.valor_unitario_padrao
        item.descricao = (sugestao.get("descricao") or do_catalogo.descricao_padrao or "").strip()
    else:
        unidade = sugestao.get("unidade")
        item.nome = _cortar(sugestao.get("nome") or "Item do memorial", 255)
        item.unidade_medida = unidade if unidade in prompts.UNIDADES else "un"
        item.valor_unitario = Decimal("0.00")
        item.descricao = (sugestao.get("descricao") or "").strip()
    return item


def _registrar_destino(sugestao, item, motivo=""):
    sugestao["situacao"] = "adicionado" if item is not None else "ignorado"
    sugestao["no_catalogo"] = bool(item is not None and item.item_catalogo_id)
    if item is not None:
        sugestao["item_id"] = item.pk
        sugestao["valor_unitario"] = str(item.valor_unitario)
        sugestao["quantidade_aplicada"] = str(item.quantidade)
    if motivo:
        sugestao["motivo"] = motivo


def aplicar_resultado(importacao: ImportacaoMemorial, dados: dict) -> int:
    """Cria os itens e devolve quantos entraram. Atômico: ou entra o
    orçamento inteiro sugerido, ou nada."""
    orcamento = importacao.orcamento
    catalogo_por_codigo = {
        item.codigo: item
        for item in ItemCatalogo.objects.filter(empresa=importacao.empresa, ativo=True)
    }
    sugestoes = list(dados.get("itens") or [])
    criados = 0

    with transaction.atomic():
        ordem = orcamento.itens.count()
        for sugestao in sugestoes:
            item = _montar_item(
                orcamento, sugestao, catalogo_por_codigo, importacao.incluir_fora_catalogo
            )
            if item is None:
                _registrar_destino(sugestao, None, "fora do catálogo")
                continue
            ordem += 1
            item.ordem = ordem
            try:
                item.save()
            except ValidationError as exc:
                logger.warning("memorial %s: item recusado: %s", importacao.pk, exc)
                ordem -= 1
                _registrar_destino(sugestao, None, "; ".join(exc.messages))
                continue
            _registrar_destino(sugestao, item)
            criados += 1

        if importacao.preencher_evento:
            alterados, resumo_cliente = preencher_dados_gerais(
                orcamento, dados.get("orcamento") or {}, importacao.empresa
            )
            if alterados:
                orcamento.save(update_fields=[*alterados, "atualizado_em"])
            if resumo_cliente:
                dados["cliente"] = resumo_cliente
        orcamento.recalcular_totais()

    dados["itens"] = sugestoes
    return criados


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------


def categorias_da_empresa(empresa):
    return CategoriaItem.objects.filter(empresa=empresa, ativo=True).order_by("nome")


def catalogo_da_empresa(empresa):
    return (
        ItemCatalogo.objects.filter(empresa=empresa, ativo=True, categoria__ativo=True)
        .select_related("categoria")
        .order_by("categoria__nome", "nome")
    )


def processar_importacao(importacao_id: int, memorial: Memorial) -> None:
    """Corpo da thread. Toda falha termina em `status=erro` com mensagem
    legível: a tela nunca fica girando para sempre."""
    importacao = ImportacaoMemorial.objects.select_related("orcamento").get(pk=importacao_id)
    importacao.status = "processando"
    importacao.save(update_fields=["status", "atualizado_em"])

    try:
        catalogo_texto = prompts.montar_catalogo(
            catalogo_da_empresa(importacao.empresa),
            categorias_da_empresa(importacao.empresa).values_list("nome", flat=True),
        )
        dados, mensagem = analisar_memorial(
            memorial,
            catalogo_texto,
            instrucoes=importacao.instrucoes,
            incluir_fora=importacao.incluir_fora_catalogo,
        )
        importacao.modelo = getattr(mensagem, "model", "") or settings.MEMORIAL_IA_MODEL
        uso = getattr(mensagem, "usage", None)
        importacao.tokens_entrada = int(getattr(uso, "input_tokens", 0) or 0)
        importacao.tokens_saida = int(getattr(uso, "output_tokens", 0) or 0)
        importacao.itens_criados = aplicar_resultado(importacao, dados)
        importacao.resultado = dados
        importacao.status = "concluida"
    except IAIndisponivel as exc:
        importacao.status = "erro"
        importacao.erro = str(exc)
    except Exception:
        # Último recurso da thread: sem isto o erro morre sem rastro e o
        # registro fica em "processando" até expirar.
        logger.exception("memorial %s: falha inesperada na importação", importacao_id)
        importacao.status = "erro"
        importacao.erro = "Algo deu errado ao montar o orçamento. Nada foi adicionado."
    importacao.save()


def _executar_em_thread(importacao_id, memorial):
    try:
        processar_importacao(importacao_id, memorial)
    finally:
        close_old_connections()


def disparar(importacao: ImportacaoMemorial, memorial: Memorial) -> None:
    """Agenda o processamento para depois do commit, quando o registro já é
    visível para a conexão da thread. Nos testes roda no mesmo processo."""
    if not getattr(settings, "MEMORIAL_IA_ASSINCRONO", True):
        transaction.on_commit(lambda: processar_importacao(importacao.pk, memorial))
        return

    def iniciar():
        threading.Thread(
            target=_executar_em_thread,
            args=(importacao.pk, memorial),
            name=f"memorial-{importacao.pk}",
            daemon=True,
        ).start()

    transaction.on_commit(iniciar)


def expirar_travadas(orcamento) -> None:
    """Importação que passou do prazo sem terminar perdeu a thread (reload do
    gunicorn, queda do processo). Vira erro para liberar uma nova tentativa."""
    limite = timezone.now() - timedelta(minutes=settings.MEMORIAL_IA_EXPIRA_MINUTOS)
    ImportacaoMemorial.objects.filter(
        orcamento=orcamento,
        status__in=ImportacaoMemorial.EM_ANDAMENTO,
        atualizado_em__lt=limite,
    ).update(
        status="erro",
        erro="A leitura foi interrompida antes de terminar. Tente de novo.",
        atualizado_em=timezone.now(),
    )


def limite_diario(user) -> int:
    if getattr(user, "eh_visitante", False):
        return settings.MEMORIAL_IA_LIMITE_DIARIO_VISITANTE
    return settings.MEMORIAL_IA_LIMITE_DIARIO


def usadas_hoje(empresa) -> int:
    inicio = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return ImportacaoMemorial.objects.filter(empresa=empresa, criado_em__gte=inicio).count()
