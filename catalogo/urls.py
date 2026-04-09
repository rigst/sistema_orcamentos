from django.urls import path

from .views import (
    categoria_criar,
    categoria_editar,
    categoria_lista,
    item_criar,
    item_editar,
    item_lista,
)

app_name = "catalogo"

urlpatterns = [
    path("categorias/", categoria_lista, name="categoria_lista"),
    path("categorias/nova/", categoria_criar, name="categoria_criar"),
    path("categorias/<int:pk>/editar/", categoria_editar, name="categoria_editar"),
    path("itens/", item_lista, name="item_lista"),
    path("itens/novo/", item_criar, name="item_criar"),
    path("itens/<int:pk>/editar/", item_editar, name="item_editar"),
]
