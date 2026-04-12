from core.tenancy import EMPRESA_ATIVA_SESSION_KEY


class EmpresaAtivaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            grupos = user.groups.order_by("name", "id")
            grupo_id_ativo = request.session.get(EMPRESA_ATIVA_SESSION_KEY)

            if grupo_id_ativo is not None and not grupos.filter(pk=grupo_id_ativo).exists():
                request.session.pop(EMPRESA_ATIVA_SESSION_KEY, None)
                grupo_id_ativo = None

            if grupo_id_ativo is None:
                grupo_padrao = grupos.first()
                if grupo_padrao is not None:
                    grupo_id_ativo = grupo_padrao.pk
                    request.session[EMPRESA_ATIVA_SESSION_KEY] = grupo_id_ativo

            if grupo_id_ativo is not None:
                user._empresa_ativa_id = int(grupo_id_ativo)

        return self.get_response(request)
