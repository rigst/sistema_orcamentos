from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_out
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from core.tenancy import obter_grupo_empresa_padrao

from .visitantes import limpar_dados_visitante

Usuario = get_user_model()

MSG_UMA_EMPRESA = "Um usuário só pode pertencer a uma empresa."


@receiver(post_save, sender=Usuario)
def garantir_grupo_padrao_para_usuario(sender, instance, created, **kwargs):
    if not created or instance.eh_visitante or instance.groups.exists():
        return
    instance.groups.add(obter_grupo_empresa_padrao())


@receiver(m2m_changed, sender=Usuario.groups.through)
def manter_uma_empresa_por_usuario(sender, instance, action, pk_set, reverse, **kwargs):
    """Um usuário pertence a uma empresa só.

    Colocar o usuário numa empresa (`user.groups.add(x)` ou
    `empresa.user_set.add(user)`) o MOVE para ela: a empresa anterior sai.
    Assim o vínculo automático com a empresa padrão, feito na criação, não
    trava quem depois põe o usuário na empresa certa. Pedir duas empresas de
    uma vez para o mesmo usuário é ambíguo e é recusado antes de gravar.
    """
    if not pk_set:
        return
    if action == "pre_add" and not reverse and len(pk_set) > 1:
        raise ValidationError(MSG_UMA_EMPRESA)
    if action != "post_add":
        return
    through = Usuario.groups.through
    if reverse:
        # empresa.user_set.add(u1, u2): cada usuário recebido sai das outras.
        through.objects.filter(usuario_id__in=pk_set).exclude(group_id=instance.pk).delete()
        return
    (nova,) = pk_set
    through.objects.filter(usuario_id=instance.pk).exclude(group_id=nova).delete()


@receiver(user_logged_out)
def limpar_visitante_ao_sair(sender, request, user, **kwargs):
    limpar_dados_visitante(user)
