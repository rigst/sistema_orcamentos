from django.urls import path

from . import views

app_name = "memoriais"

urlpatterns = [
    path("<int:orcamento_pk>/memorial/importar/", views.importar, name="importar"),
    path("<int:orcamento_pk>/memorial/<int:pk>/", views.status, name="status"),
]
