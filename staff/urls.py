"""Routes du tableau de bord superviseur."""
from django.urls import path

from documents.views import staff_documents_eleve

from . import views

app_name = "staff"

urlpatterns = [
    path("", views.dashboard_staff, name="dashboard"),
    path("eleves/<int:pk>/", views.detail_eleve_staff, name="detail_eleve"),
    path("eleves/<int:pk>/centre/", views.changer_centre_eleve_staff, name="changer_centre"),
    path("eleves/<int:pk>/entreprises/ajouter/", views.ajouter_entreprise_staff, name="ajouter_entreprise"),
    path("eleves/<int:pk>/documents/", staff_documents_eleve, name="documents_eleve"),
]
