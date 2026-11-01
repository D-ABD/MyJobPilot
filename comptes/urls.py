"""Routes de l'application comptes."""
from django.urls import path

from . import views

app_name = "comptes"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("comptes/inscription/", views.inscription, name="inscription"),
    path("comptes/connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("comptes/deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("comptes/apres-login/", views.redirection_apres_login, name="redirection_apres_login"),
    path("comptes/en-attente/", views.en_attente, name="en_attente"),
]
