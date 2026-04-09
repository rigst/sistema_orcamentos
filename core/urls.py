from django.urls import path
from .views import dashboard, manual

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("manual/", manual, name="manual"),
]
