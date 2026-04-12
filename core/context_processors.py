from core.tenancy import obter_grupo_empresa_usuario


def empresa_context(request):
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {}

    empresas_usuario = list(user.groups.order_by("name", "id"))
    empresa_ativa = obter_grupo_empresa_usuario(user)
    return {
        "empresas_usuario": empresas_usuario,
        "empresa_ativa": empresa_ativa,
    }
