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
# Register your models here.
