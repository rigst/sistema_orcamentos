"""Empresa do usuário.

Cada usuário pertence a UMA empresa (um `auth.Group`, com a `core.Empresa`
correspondente). Não há empresa "ativa" para escolher: a empresa do usuário é
a única que ele tem. O vínculo continua no M2M `groups` do Django, que todo o
resto do app já usa, e a regra de "só uma" é garantida em
`usuarios.signals.impedir_segunda_empresa`.
"""

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied

from core.models import Empresa

DEFAULT_EMPRESA_GROUP_NAME = "Empresa padrão"
VISITOR_GROUP_PREFIX = "__visitante__"


def obter_grupo_empresa_padrao():
    grupo, _ = Group.objects.get_or_create(name=DEFAULT_EMPRESA_GROUP_NAME)
    Empresa.objects.get_or_create(grupo=grupo, defaults={"nome": grupo.name, "ativa": True})
    return grupo


def obter_grupo_empresa_usuario(user):
    """Sem cache de propósito: o vínculo pode mudar no meio da vida do objeto
    (admin trocando a empresa, visitante recém-criado) e um valor velho aqui
    vazaria dados entre empresas. É um SELECT por índice."""
    if not getattr(user, "is_authenticated", False):
        return None
    return user.groups.order_by("id").first()


def obter_empresa_usuario(user):
    grupo = obter_grupo_empresa_usuario(user)
    if grupo is None:
        return None
    empresa, _ = Empresa.objects.get_or_create(
        grupo=grupo, defaults={"nome": grupo.name, "ativa": True}
    )
    return empresa


def obter_grupo_empresa_ou_erro(user):
    grupo = obter_grupo_empresa_usuario(user)
    if grupo is None:
        raise PermissionDenied("Usuário sem empresa vinculada.")
    return grupo


def queryset_da_empresa(queryset, user, field_name="empresa"):
    grupo = obter_grupo_empresa_usuario(user)
    if grupo is None:
        return queryset.none()
    return queryset.filter(**{field_name: grupo})


def pertence_a_empresa(obj, user, field_name="empresa_id"):
    grupo = obter_grupo_empresa_usuario(user)
    if grupo is None:
        return False
    return getattr(obj, field_name, None) == grupo.pk


def nome_grupo_visitante(username):
    return f"{VISITOR_GROUP_PREFIX}{username}"
