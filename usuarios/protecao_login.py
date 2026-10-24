"""Trava de tentativas de login (força bruta).

Conta as falhas por usuário e por IP no cache (Redis em produção). Ao passar do
limite, o login fica bloqueado por um tempo, mesmo com a senha certa:

- por usuário: protege a conta contra quem tenta adivinhar a senha dela;
- por IP: segura quem testa muitos usuários diferentes a partir do mesmo lugar.

O bloqueio tem prazo fixo: novas tentativas durante o bloqueio não o estendem,
para que um ataque não consiga manter o dono da conta trancado para sempre.
"""

from __future__ import annotations

import logging
import os
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)


def _env_int(nome: str, padrao: int, minimo: int) -> int:
    try:
        return max(int(os.getenv(nome, str(padrao))), minimo)
    except ValueError:
        return padrao


def limite_por_usuario() -> int:
    return _env_int("DJANGO_LOGIN_FALHAS_POR_USUARIO", 5, 1)


def limite_por_ip() -> int:
    return _env_int("DJANGO_LOGIN_FALHAS_POR_IP", 20, 1)


def janela_segundos() -> int:
    """Período em que as falhas são somadas e duração do bloqueio."""
    return _env_int("DJANGO_LOGIN_BLOQUEIO_SEGUNDOS", 900, 60)


def _normalizar(username: str | None) -> str:
    return (username or "").strip().lower()[:150]


def _chaves(tipo: str, valor: str) -> tuple[str, str]:
    return f"login:falhas:{tipo}:{valor}", f"login:bloqueio:{tipo}:{valor}"


def _alvos(username: str | None, ip: str | None) -> list[tuple[str, str, int]]:
    alvos = []
    usuario = _normalizar(username)
    if usuario:
        alvos.append(("usuario", usuario, limite_por_usuario()))
    if ip:
        alvos.append(("ip", ip, limite_por_ip()))
    return alvos


def segundos_de_bloqueio(username: str | None, ip: str | None) -> int:
    """Quanto falta para liberar o login (0 = liberado)."""
    agora = time.time()
    restante = 0
    for tipo, valor, _ in _alvos(username, ip):
        _, chave_bloqueio = _chaves(tipo, valor)
        ate = cache.get(chave_bloqueio)
        if ate:
            restante = max(restante, int(float(ate) - agora) + 1)
    return restante


def registrar_falha(username: str | None, ip: str | None) -> None:
    janela = janela_segundos()
    for tipo, valor, limite in _alvos(username, ip):
        chave_falhas, chave_bloqueio = _chaves(tipo, valor)
        if cache.add(chave_falhas, 1, timeout=janela):
            falhas = 1
        else:
            try:
                falhas = cache.incr(chave_falhas)
            except ValueError:
                cache.set(chave_falhas, 1, timeout=janela)
                falhas = 1
        # `add` não sobrescreve: o bloqueio em andamento mantém o prazo original.
        if falhas >= limite and cache.add(chave_bloqueio, time.time() + janela, timeout=janela):
            logger.warning(
                "Login bloqueado por excesso de tentativas",
                extra={"tipo": tipo, "ip": ip, "falhas": falhas},
            )


def limpar_falhas(username: str | None) -> None:
    """Login certo zera o contador do usuário (o do IP segue, de propósito:
    acertar uma conta não libera a tentativa em massa contra as outras)."""
    usuario = _normalizar(username)
    if usuario:
        chave_falhas, _ = _chaves("usuario", usuario)
        cache.delete(chave_falhas)


def mensagem_bloqueio(segundos: int) -> str:
    minutos = max(1, -(-segundos // 60))
    unidade = "minuto" if minutos == 1 else "minutos"
    return (
        "Muitas tentativas de login sem sucesso. Por segurança, o acesso foi pausado. "
        f"Tente de novo em {minutos} {unidade} ou use “Esqueci minha senha”."
    )
