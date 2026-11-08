"""Routes de la recherche globale et des tâches."""
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("offres-alternance/", views.offres_alternance, name="offres_alternance"),
    path("offres/enregistrer/<str:offre_id_lba>/", views.enregistrer_offre, name="enregistrer_offre"),
    path("offres/retirer/<str:offre_id_lba>/", views.retirer_offre, name="retirer_offre"),
    path("mes-offres-enregistrees/", views.mes_offres_enregistrees, name="mes_offres_enregistrees"),
    path("recherche/", views.recherche, name="recherche"),
    path("taches/compteur/", views.taches_compteur, name="taches_compteur"),
    path("taches/", views.taches_liste, name="taches_liste"),
    path("taches/nouvelle/", views.tache_nouvelle, name="tache_nouvelle"),
    path("taches/<int:pk>/modifier/", views.tache_modifier, name="tache_modifier"),
    path("taches/<int:pk>/terminer/", views.tache_terminer, name="tache_terminer"),
    path("taches/<int:pk>/supprimer/", views.tache_supprimer, name="tache_supprimer"),
]
