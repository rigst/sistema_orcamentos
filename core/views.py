"""Sonda de saúde para o smoke-test do CD (rigst/ci RUNBOOK.md, seção 7.8).

Responde 200 só quando o processo consegue usar o que precisa para servir uma
página: banco e cache (Redis em produção). Este app não usa Celery, então não
há broker a conferir. Qualquer falha vira 503, que o cd-deploy.sh trata como
deploy quebrado e reverte.

O corpo é só o status: qual componente caiu fica no log, não na resposta.
Com HEALTHZ_TOKEN definido, sem o cabeçalho X-Healthz-Token correto a rota
responde 404, como antes.
"""

import logging
import secrets
import uuid
from collections.abc import Callable

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)


def _banco() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def _cache() -> None:
    chave = f"healthz:{uuid.uuid4().hex}"
    cache.set(chave, "1", 10)
    if cache.get(chave) != "1":
        raise RuntimeError("cache não devolveu o valor gravado")
    cache.delete(chave)


VERIFICACOES: tuple[tuple[str, Callable[[], None]], ...] = (("banco", _banco), ("cache", _cache))


def _token_valido(request: HttpRequest) -> bool:
    healthz_token = getattr(settings, "HEALTHZ_TOKEN", "")
    if not healthz_token:
        return True
    token_recebido = request.headers.get("X-Healthz-Token", "").strip()
    return bool(token_recebido) and secrets.compare_digest(token_recebido, healthz_token)


@never_cache
@require_safe
def healthz(request: HttpRequest) -> HttpResponse:
    if not _token_valido(request):
        return HttpResponseNotFound()
    falhas = []
    for nome, verificar in VERIFICACOES:
        try:
            verificar()
        except Exception:  # sonda: qualquer falha é "indisponível", e vai para o log
            logger.exception("healthz: %s indisponível", nome)
            falhas.append(nome)
    if falhas:
        return JsonResponse({"status": "indisponivel"}, status=503)
    return JsonResponse({"status": "ok"})
