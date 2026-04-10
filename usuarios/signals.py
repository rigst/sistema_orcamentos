from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from catalogo.models import CategoriaItem, ItemCatalogo
from clientes.models import Cliente
from core.tenancy import (
    VISITOR_GROUP_PREFIX,
    nome_grupo_visitante,
    obter_grupo_empresa_padrao,
    obter_grupo_empresa_usuario,
)
from orcamentos.models import Orcamento
from relatorios.models import ConfiguracaoEmpresa


@receiver(post_save, sender=get_user_model())
def garantir_grupo_padrao_para_usuario(sender, instance, created, **kwargs):
    if not created or instance.eh_visitante or instance.groups.exists():
        return
    instance.groups.add(obter_grupo_empresa_padrao())


@receiver(user_logged_out)
def limpar_visitante_ao_sair(sender, request, user, **kwargs):
    if not user or not getattr(user, "eh_visitante", False):
        return

    grupo = obter_grupo_empresa_usuario(user)
    if grupo:
        Orcamento.objects.filter(empresa=grupo).delete()
        Cliente.objects.filter(empresa=grupo).delete()
        ItemCatalogo.objects.filter(empresa=grupo).delete()
        CategoriaItem.objects.filter(empresa=grupo).delete()
        ConfiguracaoEmpresa.objects.filter(empresa=grupo).delete()

    user.delete()

    if grupo and grupo.name.startswith(VISITOR_GROUP_PREFIX):
        Group.objects.filter(pk=grupo.pk).delete()
