from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied


DEFAULT_EMPRESA_GROUP_NAME = "Empresa padrão"
VISITOR_GROUP_PREFIX = "__visitante__"
EMPRESA_ATIVA_SESSION_KEY = "empresa_ativa_id"


def obter_grupo_empresa_padrao():
    grupo, _ = Group.objects.get_or_create(name=DEFAULT_EMPRESA_GROUP_NAME)
    return grupo


def obter_grupo_empresa_usuario(user):
    if not getattr(user, "is_authenticated", False):
        return None
    grupos = user.groups.order_by("name", "id")
    grupo_id_ativo = getattr(user, "_empresa_ativa_id", None)
    if grupo_id_ativo:
        grupo_ativo = grupos.filter(pk=grupo_id_ativo).first()
        if grupo_ativo is not None:
            return grupo_ativo
    return grupos.first()


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


def definir_grupo_empresa_ativo(request, user, grupo_id):
    if not getattr(user, "is_authenticated", False):
        return None

    try:
        grupo_id_int = int(grupo_id)
    except (TypeError, ValueError):
        return None

    grupo = user.groups.filter(pk=grupo_id_int).first()
    if grupo is None:
        return None

    request.session[EMPRESA_ATIVA_SESSION_KEY] = grupo.pk
    user._empresa_ativa_id = grupo.pk
    return grupo
