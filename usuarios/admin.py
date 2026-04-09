from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Informações adicionais", {"fields": ("perfil", "nome_exibicao", "criado_em", "atualizado_em")}),
    )
    readonly_fields = ("criado_em", "atualizado_em")
    list_display = ("username", "email", "perfil", "is_staff", "is_active")
    list_filter = ("perfil", "is_staff", "is_active")

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_staff and request.user.eh_admin_perfil)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)
# Register your models here.
