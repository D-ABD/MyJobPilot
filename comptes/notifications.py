"""Création centralisée des notifications in-app."""
from .models import Notification, ScopeSuperviseur, TypeNotification, Utilisateur


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


def notifier_ajout_prospection(prospection, auteur):
    """Notifie les personnes concernées par l'ajout d'une prospection."""
    eleve = prospection.eleve
    superviseurs = {
        scope.superviseur
        for scope in ScopeSuperviseur.objects.filter(
            centre=eleve.centre, is_active=True,
        ).select_related("superviseur")
        if scope.superviseur.is_active
    }
    destinataires = set(superviseurs)
    if auteur != eleve:
        destinataires.add(eleve)
    destinataires.discard(auteur)

    # Un élève sans superviseur de scope doit alerter un administrateur actif.
    if auteur == eleve and not destinataires:
        admin = Utilisateur.objects.filter(
            role=Utilisateur.Role.ADMIN, is_active=True,
        ).order_by("pk").first()
        if admin and admin != auteur:
            destinataires.add(admin)

    message = (
        f"Nouvelle prospection ajoutée : {prospection.entreprise.nom} "
        f"(par {auteur.username})"
    )
    lien = f"/entreprises/{prospection.pk}/"
    return [
        creer_notification(dest, TypeNotification.AJOUT_PROSPECTION, message, lien)
        for dest in destinataires
    ]
