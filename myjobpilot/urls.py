"""Routes du projet."""
from django.contrib import admin
from django.urls import include, path
from . import views as project_views
from entreprises.api import entreprises_list, prospections_list

handler404 = "myjobpilot.views.page_404"


urlpatterns = [
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
