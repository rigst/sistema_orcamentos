from django.urls import path
from django.views.generic import RedirectView

from .views import healthz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    # A página inicial é a lista de orçamentos. O nome "dashboard" fica como
    # apelido da raiz: LOGIN_REDIRECT_URL, o app legal e os 403/404 apontam
    # para ele, e links antigos salvos continuam funcionando.
    path("", RedirectView.as_view(pattern_name="orcamentos:lista"), name="dashboard"),
]
