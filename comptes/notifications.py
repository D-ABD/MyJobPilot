"""Création centralisée des notifications in-app."""
from .models import Notification


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
