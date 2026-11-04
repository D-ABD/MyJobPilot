"""Routes du projet."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("comptes.urls")),
    path("staff/", include("staff.urls", namespace="staff")),
    path("documents/", include("documents.urls", namespace="documents")),
    path("", include("entreprises.urls", namespace="entreprises")),
    path("admin-dashboard/", include("admin_dashboard.urls", namespace="admin_dashboard")),
    path("", include("rgpd.urls", namespace="rgpd")),
]
