from django.urls import path

from . import views, views_catalogo

app_name = "memoriais"

urlpatterns = [
    path("novo/memorial/", views.novo_com_memorial, name="novo_com_memorial"),
    path("<int:orcamento_pk>/memorial/importar/", views.importar, name="importar"),
    path("<int:orcamento_pk>/memorial/<int:pk>/", views.status, name="status"),
    path(
        "<int:orcamento_pk>/memorial/<int:pk>/catalogo/",
        views_catalogo.salvar_catalogo,
        name="salvar_catalogo",
    ),
]
