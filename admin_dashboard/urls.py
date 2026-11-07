from django.urls import path

from . import views

app_name = "admin_dashboard"

urlpatterns = [
    path("", views.dashboard_admin, name="dashboard"),
    path("import-eleves/", views.admin_import_eleves_csv, name="import_eleves"),
    path("import-entreprises/exemple.csv", views.admin_import_entreprises_exemple_csv, name="import_entreprises_exemple"),
    path("import-entreprises/", views.admin_import_entreprises_csv, name="import_entreprises"),
    path("eleves/", views.admin_eleves_list, name="eleves"),
    path("eleves/<int:pk>/", views.admin_eleve_detail, name="eleve_detail"),
    path("eleves/<int:pk>/valider/", views.admin_eleve_valider, name="eleve_valider"),
    path("eleves/<int:pk>/refuser/", views.admin_eleve_refuser, name="eleve_refuser"),
    path("eleves/<int:pk>/desactiver/", views.admin_eleve_desactiver, name="eleve_desactiver"),
    path("eleves/<int:pk>/reactiver/", views.admin_eleve_reactiver, name="eleve_reactiver"),
    path("eleves/<int:pk>/centre/", views.admin_eleve_changer_centre, name="eleve_changer_centre"),
    path("eleves/<int:pk>/formation/", views.admin_eleve_changer_formation, name="eleve_changer_formation"),
    path("superviseurs/", views.admin_superviseurs_list, name="superviseurs"),
    path("superviseurs/<int:pk>/", views.admin_superviseur_detail, name="superviseur_detail"),
    path("superviseurs/<int:pk>/modifier/", views.admin_superviseur_modifier, name="superviseur_modifier"),
    path("superviseurs/<int:pk>/mot-de-passe/", views.admin_superviseur_mot_de_passe, name="superviseur_mot_de_passe"),
    path("superviseurs/<int:pk>/desactiver/", views.admin_superviseur_desactiver, name="superviseur_desactiver"),
    path("superviseurs/<int:pk>/reactiver/", views.admin_superviseur_reactiver, name="superviseur_reactiver"),
    path("superviseurs/<int:pk>/supprimer/", views.admin_superviseur_supprimer, name="superviseur_supprimer"),
    path("superviseurs/creer/", views.admin_superviseur_create, name="superviseur_create"),
    path("superviseurs/<int:pk>/scopes/", views.admin_superviseur_scopes, name="superviseur_scopes"),
    path("superviseurs/<int:pk>/scopes/creer/", views.admin_scope_create, name="scope_create"),
    path("scopes/<int:pk>/desactiver/", views.admin_scope_desactiver, name="scope_desactiver"),
    path("demandes-rgpd/", views.admin_demandes_rgpd_list, name="demandes_rgpd"),
    path("prospections/<int:pk>/", views.admin_prospection_detail, name="prospection_detail"),
    path("prospections/<int:pk>/statut/", views.admin_prospection_changer_statut, name="prospection_changer_statut"),
    path("prospections/<int:pk>/commentaire/", views.admin_prospection_ajouter_commentaire, name="prospection_ajouter_commentaire"),
    path("exports/", views.admin_export_csv, name="exports"),
    path("exports/eleves.csv", views.admin_export_eleves_csv, name="export_eleves"),
    path("exports/prospections.csv", views.admin_export_prospections_csv, name="export_prospections"),
    path("exports/historique.csv", views.admin_export_historique_csv, name="export_historique"),
    path("exports/demandes-rgpd.csv", views.admin_export_demandes_rgpd_csv, name="export_demandes_rgpd"),
]
