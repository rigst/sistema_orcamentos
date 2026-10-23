from django import template

from catalogo.icones import icone_sugerido, svg_icone

register = template.Library()


@register.simple_tag
def icone_categoria(categoria, rotulo=True, classe="categoria-icone"):
    """Ícone da categoria (o escolhido ou o sugerido pelo nome)."""
    if categoria is None:
        return svg_icone(
            "caixa", rotulo="Item não registrado no catálogo" if rotulo else "", classe=classe
        )
    chave = getattr(categoria, "icone", "") or icone_sugerido(categoria.nome)
    return svg_icone(chave, rotulo=categoria.nome if rotulo else "", classe=classe)


@register.simple_tag
def icone_por_chave(chave, rotulo="", classe="categoria-icone"):
    return svg_icone(chave, rotulo=rotulo, classe=classe)
