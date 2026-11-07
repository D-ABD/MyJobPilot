"""Routes de prospection accessibles selon le rôle et les droits du compte."""
from django.urls import path

from . import commentaires, views

app_name = "entreprises"

urlpatterns = [
    path("commentaires/ajouter/<int:prospection_pk>/", commentaires.commentaire_ajouter, name="commentaire_ajouter"),
    path("commentaires/<int:pk>/supprimer/", commentaires.commentaire_supprimer, name="commentaire_supprimer"),
    path("hub/", views.hub, name="hub"),
    path("mes-relances/compteur/", views.mes_relances_compteur, name="mes_relances_compteur"),
    path("mes-relances/terminer/<int:pk>/", views.mes_relances_terminer, name="mes_relances_terminer"),
    path("mes-relances/", views.mes_relances, name="mes_relances"),
    path("entreprises-reference/", views.entreprises_reference, name="reference"),
    path("entreprises-reference/export.csv", views.entreprises_reference_export_csv, name="export_csv"),
    path("entreprises-reference/<int:pk>/", views.entreprise_reference_detail, name="reference_detail"),
    path("dashboard/", views.dashboard_eleve, name="dashboard"),
    path("prospections/", views.prospections_toutes, name="prospections_toutes"),
    path("prospections/nouvelle/", views.prospection_create_tout_role, name="prospection_create_tout_role"),
    path("entreprises/search/", views.recherche_entreprises, name="search"),
    path("entreprises/nouvelle/", views.entreprise_create, name="create"),
    path("entreprises/<int:pk>/", views.entreprise_detail, name="detail"),
    path("entreprises/<int:pk>/modifier/", views.entreprise_update, name="update"),
    path("entreprises/<int:pk>/supprimer/", views.entreprise_delete, name="delete"),
    path("entreprises/<int:pk>/statut/", views.entreprise_changer_statut, name="changer_statut"),
]
