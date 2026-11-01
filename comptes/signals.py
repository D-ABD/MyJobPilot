"""Journalise les événements d'authentification Django."""
import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import JournalAction
from .utils import log_action

logger = logging.getLogger("comptes")


@receiver(user_logged_in)
def journaliser_connexion(sender, request, user, **kwargs):
    log_action(JournalAction.Action.LOGIN, utilisateur=user, cible=user, request=request)


@receiver(user_logged_out)
def journaliser_deconnexion(sender, request, user, **kwargs):
    log_action(JournalAction.Action.LOGOUT, utilisateur=user, cible=user, request=request)


@receiver(user_login_failed)
def journaliser_echec_connexion(sender, credentials, request, **kwargs):
    identifiant = credentials.get("username", "") if credentials else ""
    log_action(
        JournalAction.Action.LOGIN_FAILED,
        details={"username": identifiant},
        request=request,
    )
