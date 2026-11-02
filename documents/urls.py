"""Routes de l'espace documentaire."""
from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="list"),
    path("ajouter/", views.document_upload, name="upload"),
    path("<int:pk>/telecharger/", views.document_download, name="download"),
    path("<int:pk>/supprimer/", views.document_delete, name="delete"),
]
