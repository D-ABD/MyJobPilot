from django.urls import path

from . import views

app_name = "admin_dashboard"

urlpatterns = [
    path("", views.dashboard_admin, name="dashboard"),
    path("eleves/", views.admin_eleves_list, name="eleves"),
    path("superviseurs/", views.admin_superviseurs_list, name="superviseurs"),
    path("superviseurs/creer/", views.admin_superviseur_create, name="superviseur_create"),
    path("superviseurs/<int:pk>/scopes/", views.admin_superviseur_scopes, name="superviseur_scopes"),
    path("superviseurs/<int:pk>/scopes/creer/", views.admin_scope_create, name="scope_create"),
    path("scopes/<int:pk>/desactiver/", views.admin_scope_desactiver, name="scope_desactiver"),
    path("demandes-rgpd/", views.admin_demandes_rgpd_list, name="demandes_rgpd"),
    path("exports/", views.admin_export_csv, name="exports"),
    path("exports/eleves.csv", views.admin_export_eleves_csv, name="export_eleves"),
    path("exports/prospections.csv", views.admin_export_prospections_csv, name="export_prospections"),
    path("exports/historique.csv", views.admin_export_historique_csv, name="export_historique"),
    path("exports/demandes-rgpd.csv", views.admin_export_demandes_rgpd_csv, name="export_demandes_rgpd"),
]
