"""Envoi des emails transactionnels MyJobPilot."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger("comptes")
SITE_URL = "https://myjobpilot.adserv.fr"


def _envoyer(destinataire, sujet, template, contexte, type_email):
    email = getattr(destinataire, "email", "")
    if not email or not email.strip():
        logger.info("Email %s non envoyé : adresse absente.", type_email)
        return 0

    html_message = render_to_string(template, {
        **contexte,
        "lien_confidentialite": f"{SITE_URL}/confidentialite/",
    })
    resultat = send_mail(
        sujet,
        strip_tags(html_message),
        settings.DEFAULT_FROM_EMAIL,
        [email.strip()],
        fail_silently=False,
        html_message=html_message,
    )
    logger.info("Email %s envoyé à %s.", type_email, email.strip())
    return resultat


def envoyer_email_validation(user):
    """Envoie un email de validation de compte."""
    nom = user.first_name or user.username
    return _envoyer(
        user,
        "Votre compte MyJobPilot a été validé",
        "emails/validation.html",
        {
            "nom": nom,
            "username": user.username,
            "lien_connexion": f"{SITE_URL}/comptes/connexion/",
        },
        "validation de compte",
    )


def envoyer_email_refus(user, motif):
    """Envoie un email de refus de compte avec le motif communiqué par l'admin."""
    return _envoyer(
        user,
        "Votre compte MyJobPilot n'a pas été validé",
        "emails/refus.html",
        {"nom": user.first_name or user.username, "username": user.username, "motif": motif},
        "refus de compte",
    )


def envoyer_email_accuse_rgpd(demande):
    """Envoie l'accusé de réception d'une demande RGPD."""
    return _envoyer(
        demande.utilisateur,
        "Accusé de réception de votre demande RGPD",
        "emails/accuse_rgpd.html",
        {
            "nom": demande.utilisateur.first_name or demande.utilisateur.username,
            "type_demande": demande.get_type_display(),
            "date_demande": timezone.localtime(demande.date_demande),
        },
        "accusé de réception RGPD",
    )


def envoyer_email_reponse_rgpd(demande):
    """Envoie la réponse de traitement d'une demande RGPD."""
    return _envoyer(
        demande.utilisateur,
        "Réponse à votre demande RGPD",
        "emails/reponse_rgpd.html",
        {
            "nom": demande.utilisateur.first_name or demande.utilisateur.username,
            "type_demande": demande.get_type_display(),
            "statut": demande.get_statut_display(),
            "est_refusee": demande.statut == "refusee",
            "motif_refus": demande.motif_refus,
        },
        "réponse RGPD",
    )


def envoyer_email_relance(prospection):
    """Envoie un email de rappel à l'élève pour une relance échue."""
    entreprise = prospection.entreprise
    return _envoyer(
        prospection.eleve,
        f"Rappel : relance à effectuer pour {entreprise.nom}",
        "emails/relance.html",
        {
            "nom": prospection.eleve.first_name or prospection.eleve.username,
            "entreprise": entreprise,
            "date_relance": prospection.date_relance,
            "lien_relances": f"{SITE_URL}/mes-relances/",
        },
        "relance de prospection",
    )
