from core.tenancy import obter_empresa_usuario


def empresa_context(request):
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {}
    return {"empresa_ativa": obter_empresa_usuario(user)}
