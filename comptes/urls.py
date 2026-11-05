"""Routes de l'application comptes."""
from django.urls import path

from . import notification_views, views

app_name = "comptes"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("comptes/inscription/", views.inscription, name="inscription"),
    path("comptes/connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("comptes/deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("comptes/apres-login/", views.redirection_apres_login, name="redirection_apres_login"),
    path("comptes/en-attente/", views.en_attente, name="en_attente"),
    path("mon-compte/", views.mon_compte, name="mon_compte"),
    path("notifications/", notification_views.notification_list, name="notifications"),
    path("notifications/unread-count/", notification_views.notification_unread_count, name="notifications_unread_count"),
    path("notifications/<int:pk>/marquer-lu/", notification_views.notification_mark_read, name="notification_mark_read"),
    path("notifications/marquer-tout-lu/", notification_views.notification_mark_all_read, name="notification_mark_all_read"),
]
