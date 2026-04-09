from django.urls import path
from .views import cliente_criar, cliente_editar, cliente_lista

app_name = "clientes"

urlpatterns = [
    path("", cliente_lista, name="lista"),
    path("novo/", cliente_criar, name="criar"),
    path("<int:pk>/editar/", cliente_editar, name="editar"),
]
