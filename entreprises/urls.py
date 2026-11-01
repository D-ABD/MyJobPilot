"""Routes de prospection, limitées au compte élève connecté."""
from django.urls import path

from . import views

app_name = "entreprises"

urlpatterns = [
    path("dashboard/", views.dashboard_eleve, name="dashboard"),
    path("entreprises/nouvelle/", views.entreprise_create, name="create"),
    path("entreprises/<int:pk>/", views.entreprise_detail, name="detail"),
    path("entreprises/<int:pk>/modifier/", views.entreprise_update, name="update"),
    path("entreprises/<int:pk>/supprimer/", views.entreprise_delete, name="delete"),
    path("entreprises/<int:pk>/statut/", views.entreprise_changer_statut, name="changer_statut"),
]
