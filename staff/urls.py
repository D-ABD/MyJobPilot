"""Routes du tableau de bord superviseur."""
from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("", views.dashboard_staff, name="dashboard"),
    path("eleves/<int:pk>/", views.detail_eleve_staff, name="detail_eleve"),
]
