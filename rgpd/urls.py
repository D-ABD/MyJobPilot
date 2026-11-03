from django.urls import path

from . import views

app_name = "rgpd"

urlpatterns = [
    path("mon-compte/demandes-rgpd/", views.demandes_rgpd_list, name="demandes_rgpd_list"),
    path("mon-compte/demandes-rgpd/creer/", views.demande_rgpd_create, name="demande_rgpd_create"),
    path("mon-compte/demandes-rgpd/<int:pk>/", views.demande_rgpd_detail, name="demande_rgpd_detail"),
    path("admin-dashboard/demandes-rgpd/", views.admin_demandes_rgpd_list, name="admin_demandes_rgpd_list"),
    path("admin-dashboard/demandes-rgpd/<int:pk>/traiter/", views.admin_demande_rgpd_traiter, name="admin_demande_rgpd_traiter"),
    path("mon-compte/export-rgpd/", views.export_rgpd, name="export_rgpd"),
    path("confidentialite/", views.confidentialite, name="confidentialite"),
]
