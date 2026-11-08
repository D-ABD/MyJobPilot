"""Routes du projet."""
from django.contrib import admin
from django.urls import include, path
from . import views as project_views
from entreprises.api import entreprises_list, prospections_list
from staff import views as staff_views

handler404 = "myjobpilot.views.page_404"


urlpatterns = [
    path("objectifs/", include(([
        path("", staff_views.objectifs_liste, name="liste"),
        path("nouveau/", staff_views.objectif_nouveau, name="nouveau"),
        path("<int:pk>/modifier/", staff_views.objectif_modifier, name="modifier"),
        path("<int:pk>/supprimer/", staff_views.objectif_supprimer, name="supprimer"),
    ], "objectifs"), namespace="objectifs")),
    path("", include("core.urls", namespace="core")),
    path("api/prospections/", prospections_list, name="api_prospections"),
    path("api/entreprises/", entreprises_list, name="api_entreprises"),
    path("sw.js", project_views.sw_js, name="service_worker"),
    path("offline/", project_views.offline_view, name="offline"),
    path("static/manifest.json", project_views.manifest_json, name="manifest"),
    path("admin/", admin.site.urls),
    path("", include("comptes.urls")),
    path("staff/", include("staff.urls", namespace="staff")),
    path("documents/", include("documents.urls", namespace="documents")),
    path("", include("entreprises.urls", namespace="entreprises")),
    path("admin-dashboard/", include("admin_dashboard.urls", namespace="admin_dashboard")),
    path("", include("rgpd.urls", namespace="rgpd")),
]
