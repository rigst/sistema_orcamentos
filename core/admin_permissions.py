from typing import TYPE_CHECKING, ClassVar

from core.tenancy import obter_grupo_empresa_usuario

if TYPE_CHECKING:
    from django.contrib.admin import ModelAdmin

    AdminBase = ModelAdmin
else:
    AdminBase = object


class PerfilAdminPermissionMixin(AdminBase):
    # ClassVar[str | None]: cada admin concreto sobrescreve com o nome da
    # capability. Sem a anotação o mypy infere `None` da base e reprova as
    # quatro atribuições em cada um dos seis admins.
    capability_view: ClassVar[str | None] = None
    capability_add: ClassVar[str | None] = None
    capability_change: ClassVar[str | None] = None
    capability_delete: ClassVar[str | None] = None

    def _has_capability(self, request, capability_name):
        return bool(
            request.user.is_active
            and request.user.is_staff
            and capability_name
            and getattr(request.user, capability_name, False)
        )

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def has_view_permission(self, request, obj=None):
        return self._has_capability(request, self.capability_view)

    def has_add_permission(self, request):
        return self._has_capability(request, self.capability_add)

    def has_change_permission(self, request, obj=None):
        return self._has_capability(request, self.capability_change)

    def has_delete_permission(self, request, obj=None):
        return self._has_capability(request, self.capability_delete)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not hasattr(queryset.model, "empresa_id"):
            return queryset

        grupo = obter_grupo_empresa_usuario(request.user)
        if grupo is None:
            return queryset.none()
        return queryset.filter(empresa=grupo)

    def save_model(self, request, obj, form, change):
        if hasattr(obj, "empresa_id") and obj.empresa_id is None:
            obj.empresa = obter_grupo_empresa_usuario(request.user)
        super().save_model(request, obj, form, change)
