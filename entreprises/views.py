"""Tableau de bord élève et gestion isolée des prospections."""
from datetime import datetime, time, timedelta
import unicodedata

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from comptes.models import JournalAction, TypeNotification, Utilisateur
from comptes.notifications import creer_notification, notifier_changement_statut
from comptes.scope_utils import centres_du_superviseur, verifier_superviseur
from core.stats import calculer_stats_eleve
from comptes.utils import log_action
from core.filters import FiltreMixin
from core.gamification import calculer_progression_utilisateur, verifier_et_attribuer_badges

from .forms import (
    ChangementStatutForm, EntrepriseForm, ProspectionForm, ProspectionFormToutRole,
)
from .models import Entreprise, HistoriqueStatut, Prospection, Relance, Statut, TypeContrat


NOMBRE_PAR_PAGE = 25
CHAMPS_DATE_STATUT = {
    Statut.A_RELANCER: "date_relance",
    Statut.CANDIDATURE_ENVOYEE: "date_candidature",
    Statut.EN_ATTENTE: "date_mise_en_attente",
    Statut.ENTRETIEN_PROGRAMME: "date_entretien",
    Statut.REFUS: "date_refus",
    Statut.ACCEPTE: "date_acceptation",
}


def _verifier_eleve(request):
    if request.user.role != Utilisateur.Role.ELEVE:
        raise PermissionDenied


def _prospection_eleve(request, pk):
    return get_object_or_404(
        Prospection.objects.select_related("entreprise"),
        pk=pk,
        eleve=request.user,
    )


def _prospection_pour_action(request, pk, *, autoriser_scope=False):
    """Retourne une prospection si son propriétaire ou le rôle y a accès."""
    prospection = get_object_or_404(
        Prospection.objects.select_related("entreprise", "eleve"), pk=pk,
    )
    utilisateur = request.user
    if utilisateur.role == Utilisateur.Role.ADMIN:
        return prospection
    if (
        utilisateur.role in {Utilisateur.Role.ELEVE, Utilisateur.Role.SUPERVISEUR}
        and prospection.eleve_id == utilisateur.pk
    ):
        return prospection
    if (
        autoriser_scope
        and utilisateur.role == Utilisateur.Role.SUPERVISEUR
        and prospection.eleve.role == Utilisateur.Role.ELEVE
        and prospection.eleve.centre_id in centres_du_superviseur(utilisateur)
    ):
        return prospection
    raise PermissionDenied


def _rendre_formulaire_prospection(request, form, entreprise_form, titre, prospection=None):
    if prospection is None:
        breadcrumb_items = [
            ("Accueil", "/"),
            ("Dashboard", "/dashboard/"),
            ("Nouvelle prospection", ""),
        ]
    else:
        breadcrumb_items = [
            ("Accueil", "/"),
            ("Dashboard", "/dashboard/"),
            (prospection.entreprise.nom, f"/entreprises/{prospection.pk}/"),
            ("Modifier", ""),
        ]
    return render(
        request,
        "entreprises/entreprise_form.html",
        {
            "form": form,
            "entreprise_form": entreprise_form,
            "titre": titre,
            "prospection": prospection,
            "allow_new_entreprise": prospection is None,
            "breadcrumb_items": breadcrumb_items,
        },
    )


def _datetime_entretien(date_entretien):
    if date_entretien is None:
        return None
    return timezone.make_aware(
        datetime.combine(date_entretien, time.min),
        timezone.get_current_timezone(),
    )


def _valeur_date_associee(prospection, statut):
    champ = CHAMPS_DATE_STATUT.get(statut)
    if champ is None:
        return None
    valeur = getattr(prospection, champ)
    return valeur.date() if champ == "date_entretien" and valeur else valeur


def _prospections_reference_visibles(user):
    """Retourne les prospections que ce rôle peut consulter dans le référentiel."""
    queryset = Prospection.objects.select_related("entreprise", "eleve")
    if user.role == Utilisateur.Role.ELEVE:
        return queryset.filter(eleve=user)
    if user.role == Utilisateur.Role.SUPERVISEUR:
        centres = centres_du_superviseur(user)
        return queryset.filter(
            Q(eleve=user)
            | Q(eleve__role=Utilisateur.Role.ELEVE, eleve__centre__in=centres)
        )
    if user.role == Utilisateur.Role.ADMIN:
        return queryset
    raise PermissionDenied


def _normaliser_recherche_entreprise(texte):
    """Normalise casse et accents pour la recherche du référentiel partagé."""
    texte = unicodedata.normalize("NFKD", texte or "")
    return "".join(cara