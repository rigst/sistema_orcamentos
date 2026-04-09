from django.urls import path

from .views import configuracao_criar, configuracao_editar, configuracao_lista

app_name = "relatorios"

urlpatterns = [
    path("configuracoes/", configuracao_lista, name="configuracao_lista"),
    path("configuracoes/nova/", configuracao_criar, name="configuracao_criar"),
    path("configuracoes/<int:pk>/editar/", configuracao_editar, name="configuracao_editar"),
]
