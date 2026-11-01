"""Helpers de vérification et de lecture des scopes superviseur."""
from django.core.exceptions import PermissionDenied

from .models import ScopeSuperviseur, Utilisateur


def centres_du_superviseur(user):
    """Retourne les IDs des centres couverts par les scopes actifs."""
    if not user or not user.is_authenticated:
        return []
    if user.role != Utilisateur.Role.SUPERVISEUR:
        return []
    return list(
        ScopeSuperviseur.objects.filter(
            superviseur=user,
            is_active=True,
        ).values_list("centre_id", flat=True)
    )


def superviser_eleve(user, eleve):
    """Indique si un superviseur détient un scope actif pour cet élève."""
    if not user or not user.is_authenticated:
        return False
    if user.role != Utilisateur.Role.SUPERVISEUR:
        return False
    if not eleve or eleve.role != Utilisateur.Role.ELEVE or not eleve.centre_id:
        return False
    return ScopeSuperviseur.objects.filter(
        superviseur=user,
        centre_id=eleve.centre_id,
        is_active=True,
    ).exists()


def verifier_superviseur(request, eleve=None):
    """Refuse l'accès hors du rôle superviseur ou hors du scope actif."""
    utilisateur = getattr(request, "user", None)
    if not utilisateur or not utilisateur.is_authenticated:
        raise PermissionDenied
    if utilisateur.role != Utilisateur.Role.SUPERVISEUR:
        raise PermissionDenied
    if eleve is not None and not superviser_eleve(utilisateur, eleve):
        raise PermissionDenied
