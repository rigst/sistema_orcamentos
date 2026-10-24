"""Marca de identificação (círculo com iniciais numa cor fixa por registro).

Usada em orçamentos e clientes: a cor sai da paleta pelo id, então é estável
sem precisar de campo no banco.
"""

PALETA_IDENTIFICACAO = (
    "#2563EB",
    "#0D9488",
    "#D97706",
    "#7C3AED",
    "#DB2777",
    "#0891B2",
    "#65A30D",
    "#DC2626",
    "#4F46E5",
    "#C2410C",
)


def cor_por_id(pk: int | None) -> str:
    return PALETA_IDENTIFICACAO[(pk or 0) % len(PALETA_IDENTIFICACAO)]


def iniciais_de(texto: str) -> str:
    """Primeira letra das duas primeiras palavras com letra; com uma palavra só,
    as duas primeiras letras dela. Sem letra nenhuma, "#"."""
    palavras = [p for p in (texto or "").split() if any(c.isalpha() for c in p)]
    if not palavras:
        return "#"
    letras = [next(c for c in p if c.isalpha()) for p in palavras[:2]]
    if len(letras) == 1:
        letras = [c for c in palavras[0] if c.isalpha()][:2]
    return "".join(letras).upper()
