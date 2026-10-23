from typing import cast

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from core.tenancy import VISITOR_GROUP_PREFIX, obter_grupo_empresa_usuario

from .models import Usuario


class UsuarioChangeForm(UserChangeForm):
    """Recusa marcar duas empresas no admin, com mensagem no próprio campo
    (o sinal do modelo também recusa, mas com erro 500 em vez de aviso)."""

    def clean_groups(self):
        grupos = self.cleaned_data.get("groups")
        if grupos is not None and len(grupos) > 1:
            raise forms.ValidationError("Escolha uma empresa só para o usuário.")
        return grupos


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin, ModelAdmin):
    # Os formulários do unfold existem porque as telas de troca de senha e de
    # criação de usuário do admin nativo trazem markup próprio e ficariam fora
    # do tema.
    form = UsuarioChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    fieldsets = (
        *(UserAdmin.fieldsets or ()),
        (
            "Informações adicionais",
            {"fields": ("perfil", "nome_exibicao", "criado_em", "atualizado_em")},
        ),
    )
    readonly_fields = ("criado_em", "atualizado_em")
    list_display = ("username", "email", "perfil", "is_staff", "is_active", "empresa_atual")
    list_filter = ("perfil", "is_staff", "is_active", "groups")

    def empresa_atual(self, obj):
        return obj.nome_empresa

    def grupos_empresa_queryset(self, request):
        queryset = Group.objects.exclude(name__startswith=VISITOR_GROUP_PREFIX).order_by("name")
        if request.user.is_superuser:
            return queryset
        grupo = obter_grupo_empresa_usuario(request.user)
        if grupo is None:
            return queryset.none()
        return queryset.filter(pk=grupo.pk)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        if "groups" in form.base_fields:
            campo = cast("forms.ModelMultipleChoiceField", form.base_fields["groups"])
            campo.queryset = self.grupos_empresa_queryset(request)
            campo.label = "Empresa"
            campo.help_text = "Cada usuário pertence a uma única empresa: marque só uma."
        return form

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        grupo = obter_grupo_empresa_usuario(request.user)
        if grupo is None:
            return queryset.none()
        return queryset.filter(groups=grupo)

    def has_module_permission(self, request):
        return bool(
            request.user.is_active and request.user.is_staff and request.user.eh_admin_perfil
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance.eh_visitante:
            return
        if request.user.is_superuser:
            # O superusuário escolhe a empresa (o form já barra mais de uma).
            grupo = form.instance.groups.order_by("id").first()
        else:
            grupo = obter_grupo_empresa_usuario(request.user)
        if grupo is not None:
            form.instance.groups.set([grupo])


# Register your models here.
