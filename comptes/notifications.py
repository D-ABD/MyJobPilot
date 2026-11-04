"""Création centralisée des notifications in-app."""
from .models import Notification, ScopeSuperviseur, TypeNotification


def creer_notification(destinataire, type, message, lien=""):
    """Crée une notification pour un destinataire actif."""
    if destinataire is None or not destinataire.is_active:
        return None
    return Notification.objects.create(
        destinataire=destinataire,
        type=type,
        message=message[:255],
        lien=lien[:255],
    )


def _superviseurs_actifs(prospection):
    return {
        scope.superviseur
        for scope in ScopeSuperviseur.objects.filter(
            centre=prospection.eleve.centre, is_active=True,
        ).select_related("superviseur")
        if scope.superviseur.is_active
    }


def notifier_changement_statut(prospection, auteur, ancien_statut, nouveau_statut):
    """Notifie l'élève et les superviseurs actifs d'un changement de statut."""
    destinataires = {prospection.eleve}
    destinataires.update(_superviseurs_actifs(prospection))
    destinataires.discard(auteur)
    message = (
        f"Votre prospection {prospection.entreprise.nom} est passée à "
        f"{prospection.get_statut_display()}"
    )
    lien = f"/entreprises/{prospection.pk}/"
    return [
        creer_notification(dest, TypeNotification.STATUT_CHANGE, message, lien)
        for dest in destinataires
    ]


def notifier_ajout_prospection(prospection, auteur):
    """Notifie les personnes concernées par l'ajout d'une prospection."""
    destinataires = _superviseurs_actifs(prospection)
    if auteur != prospection.eleve:
        destinataires.add(prospection.eleve)
    destinataires.discard(auteur)
    message = (
        f"Nouvelle prospection ajoutée : {prospection.entreprise.nom} "
        f"(par {auteur.username})"
    )
    lien = f"/entreprises/{prospection.pk}/"
    return [
        creer_notification(dest, TypeNotification.AJOUT_PROSPECTION, message, lien)
        for dest in destinataires
    ]
