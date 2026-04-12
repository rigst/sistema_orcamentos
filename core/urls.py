from django.urls import path
from .views import alternar_empresa, dashboard, manual

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("manual/", manual, name="manual"),
    path("empresa/alternar/", alternar_empresa, name="alternar_empresa"),
]
