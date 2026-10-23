"""Saudação da página inicial: bom dia/boa tarde/boa noite e uma frase que
troca a cada dia (e muda de novo a cada carregamento, para não ficar parada).

As frases são curtas, sobre trabalho bem feito e clareza, sem autoajuda.
Autoria só quando é conhecida e de domínio público.
"""

import random
from datetime import datetime

from django.utils import timezone

FRASES = (
    # Autoria bem estabelecida; o que é atribuição duvidosa fica sem nome.
    ("O que é bem começado já está meio feito.", "Aristóteles"),
    ("Nenhum vento sopra a favor de quem não sabe para onde ir.", "Sêneca"),
    ("Menos, porém melhor.", "Dieter Rams"),
    ("Os detalhes não são os detalhes. Eles fazem o projeto.", "Charles Eames"),
    ("Quem tem um porquê enfrenta quase qualquer como.", "Friedrich Nietzsche"),
    ("A pressa é inimiga da perfeição.", ""),
    ("Medir duas vezes, cortar uma.", ""),
    ("Devagar se vai ao longe.", ""),
    ("De grão em grão, a galinha enche o papo.", ""),
    ("Quem não arrisca não petisca.", ""),
    ("Um orçamento claro vale mais que três reuniões.", ""),
    ("Bem feito é melhor do que bem dito.", ""),
    ("O detalhe de hoje é o elogio de amanhã.", ""),
    ("Cada item no lugar, cada número com motivo.", ""),
)


def saudacao(agora: datetime | None = None) -> str:
    hora = timezone.localtime(agora).hour if agora else timezone.localtime().hour
    if 5 <= hora < 12:
        return "Bom dia"
    if 12 <= hora < 18:
        return "Boa tarde"
    return "Boa noite"


def frase_do_momento(semente: int | None = None) -> dict:
    escolha = random.Random(semente).choice(FRASES)
    return {"texto": escolha[0], "autor": escolha[1]}
