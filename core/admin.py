from django.contrib import admin
from django.contrib.auth.models import Group

from core.tenancy import VISITOR_GROUP_PREFIX, obter_grupo_empresa_usuario


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(Group)
class EmpresaGroupAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_staff and getattr(request.user, "eh_admin_perfil", False))

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).exclude(name__startswith=VISITOR_GROUP_PREFIX)
        grupo = obter_grupo_empresa_usuario(request.user)
        if request.user.is_superuser:
            return queryset
        if grupo is None:
            return queryset.none()
        return queryset.filter(pk=grupo.pk)
