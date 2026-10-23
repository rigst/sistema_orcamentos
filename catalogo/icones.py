"""Ícones das categorias do catálogo.

Traços simples em SVG (viewBox 24, só `path`/`rect`/`circle` em linha), na
cor da categoria. Nada de emoji: o desenho é o mesmo em qualquer aparelho.

Sem ícone escolhido, a categoria ganha um pelo nome (palavras-chave), e no
último caso o genérico (caixa).
"""

import unicodedata

from django.utils.html import format_html
from django.utils.safestring import mark_safe

# chave: (rótulo, desenho SVG interno)
ICONES = {
    "caixa": (
        "Caixa",
        '<path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5Z"/><path d="M3.5 7.5 12 12l8.5-4.5"/><path d="M12 12v9"/>',
    ),
    "piso": (
        "Piso",
        '<path d="M3 15 9 9h12l-6 6Z"/><path d="M3 15v3h12v-3"/><path d="M15 18l6-6v-3"/><path d="M8 15l3-6M13 15l3-6"/>',
    ),
    "parede": (
        "Parede",
        '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="M3 9.7h18M3 14.3h18"/><path d="M9 5v4.7M15 5v4.7M6 9.7v4.6M12 9.7v4.6M18 9.7v4.6M9 14.3V19M15 14.3V19"/>',
    ),
    "forro": (
        "Forro e cobertura",
        '<path d="M2.5 11 12 4l9.5 7"/><path d="M5 9.2V20h14V9.2"/><path d="M9.5 20v-5h5v5"/>',
    ),
    "eletrica": ("Elétrica", '<path d="M13 2.5 5 13.5h6l-1 8 8-11h-6Z"/>'),
    "luz": (
        "Iluminação",
        '<path d="M9 17.5h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.8 10.6c.6.5.8 1.2.8 1.9v2h6v-2c0-.7.2-1.4.8-1.9A6 6 0 0 0 12 3Z"/>',
    ),
    "movel": (
        "Mobiliário",
        '<path d="M5 11V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v5"/><path d="M3 11h18v5H3Z"/><path d="M5 16v4M19 16v4"/>',
    ),
    "equipamento": (
        "Equipamento",
        '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 21h8M12 17v4"/>',
    ),
    "som": (
        "Som",
        '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4Z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
    ),
    "comunicacao": (
        "Comunicação visual",
        '<path d="M4 4h16v11H4Z"/><path d="M8 15l-2 6M16 15l2 6"/><path d="M8 8h8M8 11h5"/>',
    ),
    "ferramenta": (
        "Montagem",
        '<path d="M14.5 5.5a4 4 0 0 0-5.3 5.3l-5.7 5.7a1.8 1.8 0 0 0 2.5 2.5l5.7-5.7a4 4 0 0 0 5.3-5.3l-2.5 2.5-2.5-.5-.5-2.5Z"/>',
    ),
    "planta": (
        "Paisagismo",
        '<path d="M12 21v-8"/><path d="M12 13c0-4 3-7 8-7 0 5-3 7-8 7Z"/><path d="M12 15c0-3-2.5-5.5-7-5.5 0 4 2.5 5.5 7 5.5Z"/>',
    ),
    "pessoa": (
        "Serviço e equipe",
        '<circle cx="12" cy="7.5" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/>',
    ),
    "caminhao": (
        "Transporte",
        '<path d="M2.5 6h11v10h-11Z"/><path d="M13.5 9.5h4l3 3.5v3h-7"/><circle cx="6.5" cy="17.5" r="1.8"/><circle cx="16.5" cy="17.5" r="1.8"/>',
    ),
    "copo": (
        "Alimentação",
        '<path d="M6 3h12l-1.5 17a1.5 1.5 0 0 1-1.5 1.4H9A1.5 1.5 0 0 1 7.5 20Z"/><path d="M6.6 9h10.8"/>',
    ),
    "limpeza": (
        "Limpeza",
        '<path d="M14 3 10 13"/><path d="M6 13h8l1.5 8h-11Z"/><path d="M8.5 17v4M11.5 17v4"/>',
    ),
}

# palavras do nome da categoria -> ícone (a primeira que bater vale)
PALAVRAS = (
    (("piso", "carpete", "tablado", "deck", "assoalho"), "piso"),
    (("parede", "painel", "divisoria", "octanorm"), "parede"),
    (("forro", "cobertura", "telhado", "tenda", "toldo"), "forro"),
    (("eletric", "energia", "tomada", "cabo"), "eletrica"),
    (("ilumina", "luz", "lumin", "refletor", "spot"), "luz"),
    (("mobil", "movel", "moveis", "cadeira", "mesa", "sofa", "balcao"), "movel"),
    (("som", "audio", "sonor", "caixa acustica"), "som"),
    (("equipamento", "tv", "video", "eletronico", "computador"), "equipamento"),
    (("comunicacao", "grafic", "adesiv", "lona", "placa", "sinaliza"), "comunicacao"),
    (("montagem", "ferragem", "estrutura", "outros itens"), "ferramenta"),
    (("planta", "paisag", "jardim", "flor", "decora"), "planta"),
    (("servico", "mao de obra", "equipe", "pessoal", "recepcion"), "pessoa"),
    (("transporte", "frete", "logistica", "carga"), "caminhao"),
    (("aliment", "buffet", "bebida", "cafe", "catering"), "copo"),
    (("limpeza", "higien"), "limpeza"),
)

ESCOLHAS = [(chave, rotulo) for chave, (rotulo, _) in ICONES.items()]


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def icone_sugerido(nome: str) -> str:
    nome = _sem_acento(nome)
    for palavras, chave in PALAVRAS:
        if any(p in nome for p in palavras):
            return chave
    return "caixa"


def svg_icone(chave: str, *, rotulo: str = "", classe: str = "categoria-icone"):
    """O `<svg>` pronto para o template (traço em currentColor)."""
    _, desenho = ICONES.get(chave) or ICONES["caixa"]
    if rotulo:
        return format_html(
            '<svg class="{}" viewBox="0 0 24 24" role="img" aria-label="{}"><title>{}</title>{}</svg>',
            classe,
            rotulo,
            rotulo,
            mark_safe(desenho),
        )
    return format_html(
        '<svg class="{}" viewBox="0 0 24 24" aria-hidden="true">{}</svg>',
        classe,
        mark_safe(desenho),
    )
