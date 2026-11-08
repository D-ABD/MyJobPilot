"""Création centralisée des notifications in-app."""
from .models import Notification, TypeNotification


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


def notifier_changement_statut(prospection, auteur, ancien_statut, nouveau_statut):
    """Notifie l'élève d'un changement de statut fait par un membre du staff."""
    if auteur == prospection.eleve or auteur.role not in {
        "superviseur", "admin",
    }:
        return []

    lien = f"/entreprises/{prospection.pk}/"
    if nouveau_statut == "a_relancer":
        type_notification = TypeNotification.RELANCE_CREEE
        message = f"Nouvelle relance sur {prospection.entreprise.nom}"
    else:
        type_notification = TypeNotification.STATUT_CHANGE
        message = (
            f"Statut de {prospection.entreprise.nom} changé en "
            f"{prospection.get_statut_display()}"
        )
    notification = creer_notification(
        prospection.eleve, type_notification, message, lien,
    )
    return [notification] if notification else []


def notifier_ajout_prospection(prospection, auteur):
    """Compatibilité historique : la création de prospection ne notifie plus."""
    return []
