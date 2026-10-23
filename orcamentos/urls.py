from django.urls import path

from .views import (
    item_orcamento_criar,
    item_orcamento_duplicar,
    item_orcamento_duplicar_editar,
    item_orcamento_edicao_rapida,
    item_orcamento_editar,
    item_orcamento_excluir,
    item_orcamento_mover,
    item_orcamento_preview,
    orcamento_alterar_status,
    orcamento_contrato_do_cliente,
    orcamento_criar,
    orcamento_criar_rapido,
    orcamento_duplicar,
    orcamento_editar,
    orcamento_excluir,
    orcamento_lista,
    orcamento_novo,
    orcamento_visualizar,
)
from .views_versoes import orcamento_autosalvar, orcamento_desfazer, orcamento_refazer

app_name = "orcamentos"

urlpatterns = [
    path("", orcamento_lista, name="lista"),
    path("novo/", orcamento_novo, name="novo"),
    path("novo/rapido/", orcamento_criar_rapido, name="criar_rapido"),
    path("novo/completo/", orcamento_criar, name="criar"),
    path("<int:pk>/editar/", orcamento_editar, name="editar"),
    path("<int:pk>/autosalvar/", orcamento_autosalvar, name="autosalvar"),
    path("<int:pk>/desfazer/", orcamento_desfazer, name="desfazer"),
    path("<int:pk>/refazer/", orcamento_refazer, name="refazer"),
    path("<int:pk>/visualizar/", orcamento_visualizar, name="visualizar"),
    path("<int:pk>/duplicar/", orcamento_duplicar, name="duplicar"),
    path("<int:pk>/excluir/", orcamento_excluir, name="excluir"),
    path("<int:pk>/status/<str:novo_status>/", orcamento_alterar_status, name="alterar_status"),
    path(
        "<int:pk>/contrato-do-cliente/", orcamento_contrato_do_cliente, name="contrato_do_cliente"
    ),
    path("<int:orcamento_pk>/itens/novo/", item_orcamento_criar, name="item_criar"),
    path(
        "<int:orcamento_pk>/itens/<int:item_pk>/editar/", item_orcamento_editar, name="item_editar"
    ),
    path(
        "<int:orcamento_pk>/itens/<int:item_pk>/excluir/",
        item_orcamento_excluir,
        name="item_excluir",
    ),
    path(
        "<int:orcamento_pk>/itens/<int:item_pk>/duplicar/",
        item_orcamento_duplicar,
        name="item_duplicar",
    ),
    path(
        "<int:orcamento_pk>/itens/<int:item_pk>/duplicar-editar/",
        item_orcamento_duplicar_editar,
        name="item_duplicar_editar",
    ),
    path(
        "<int:orcamento_pk>/itens/<int:item_pk>/mover/<str:direcao>/",
        item_orcamento_mover,
        name="item_mover",
    ),
    path("<int:orcamento_pk>/itens/previsualizar/", item_orcamento_preview, name="item_preview"),
    path(
        "<int:orcamento_pk>/itens/<int:item_pk>/rapido/",
        item_orcamento_edicao_rapida,
        name="item_edicao_rapida",
    ),
]
