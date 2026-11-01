"""Routes du projet."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("comptes.urls")),
    path("staff/", include("staff.urls", namespace="staff")),
    path("", include("entreprises.urls", namespace="entreprises")),
]
