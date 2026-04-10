from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied


DEFAULT_EMPRESA_GROUP_NAME = "Empresa padrão"
VISITOR_GROUP_PREFIX = "__visitante__"


def obter_grupo_empresa_padrao():
    grupo, _ = Group.objects.get_or_create(name=DEFAULT_EMPRESA_GROUP_NAME)
    return grupo


def obter_grupo_empresa_usuario(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return user.groups.order_by("name", "id").first()


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
