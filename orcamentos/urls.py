from django.urls import path

from .views import (
    item_orcamento_criar,
    item_orcamento_editar,
    item_orcamento_excluir,
    orcamento_alterar_status,
    orcamento_criar,
    orcamento_editar,
    orcamento_excluir,
    orcamento_lista,
)

app_name = "orcamentos"

urlpatterns = [
    path("", orcamento_lista, name="lista"),
    path("novo/", orcamento_criar, name="criar"),
    path("<int:pk>/editar/", orcamento_editar, name="editar"),
    path("<int:pk>/excluir/", orcamento_excluir, name="excluir"),
    path("<int:pk>/status/<str:novo_status>/", orcamento_alterar_status, name="alterar_status"),

    path("<int:orcamento_pk>/itens/novo/", item_orcamento_criar, name="item_criar"),
    path("<int:orcamento_pk>/itens/<int:item_pk>/editar/", item_orcamento_editar, name="item_editar"),
    path("<int:orcamento_pk>/itens/<int:item_pk>/excluir/", item_orcamento_excluir, name="item_excluir"),
]
