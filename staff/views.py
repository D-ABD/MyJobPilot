"""Tableau de bord et actions staff sur les élèves de leur périmètre."""
from datetime import datetime, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comptes.models import Centre, JournalAction, TypeNotification, Utilisateur
from comptes.notifications import creer_notification
from comptes.scope_utils import centres_du_superviseur, superviser_eleve, verifier_superviseur
from comptes.utils import log_action
from core.gamification import calculer_progression_utilisateur, verifier_et_attribuer_badges
from core.stats import (
    PERIODES_DASHBOARD,
    calculer_atteinte_objectif,
    calculer_kpis_dashboard,
    calculer_stats_superviseur,
    debut_periode_dashboard,
    normaliser_periode_dashboard,
)
from core.models import Objectif
from entreprises.forms import EntrepriseForm
from entreprises.models import Commentaire, HistoriqueStatut, Prospection, Relance, Statut, TypeContrat

from .forms import AjoutProspectionStaffForm, ChangementCentreFormStaff, CodesRomeForm, ObjectifForm


NOMBRE_PAR_PAGE = 25
CHAMPS_TRIABLES = ("username", "last_name", "centre__nom", "is_valide")


def _url_tri(request, champ, champ_actuel, ordre_actuel):
    parametres = request.GET.copy()
    parametres.pop("page", None)
    prochain_ordre = "desc" if champ == champ_actuel and ordre_actuel == "asc" else "asc"
    parametres["tri"] = champ
    parametres["ordre"] = prochain_ordre
    return f"{request.path}?{parametres.urlencode()}"


@login_required
def dashboard_staff(request):
    """Liste, filtre et pagine les élèves rattachés aux centres du scope."""
    verifier_superviseur(request)
    centres_ids = centres_du_superviseur(request.user)
    centres = list(Centre.objects.filter(pk__in=centres_ids))
    periode = normaliser_periode_dashboard(request.GET.get("periode", "30"))
    eleves_scope = Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE, centre_id__in=centres_ids)

    centre_selectionne = request.GET.get("centre", "")
    if centre_selectionne:
        if not centre_selectionne.isdigit() or int(centre_selectionne) not in centres_ids:
            raise PermissionDenied
        eleves_scope = eleves_scope.filter(centre_id=int(centre_selectionne))

    eleve_selectionne = request.GET.get("eleve", "")
    eleve_selectionne_obj = None
    if eleve_selectionne:
        if not eleve_selectionne.isdigit():
            raise PermissionDenied
        eleve = Utilisateur.objects.filter(
            pk=int(eleve_selectionne), role=Utilisateur.Role.ELEVE,
            centre_id__in=centres_ids,
        ).first()
        if eleve is None or (centre_selectionne and eleve.centre_id != int(centre_selectionne)):
            raise PermissionDenied
        eleve_selectionne_obj = eleve
        eleves_scope = eleves_scope.filter(pk=eleve.pk)

    eleves_kpi = eleves_scope.select_related("centre", "formation")
    filtre_date_prospection = {}
    debut_periode = debut_periode_dashboard(periode)
    if debut_periode:
        filtre_date_prospection["filter"] = Q(
            prospections__date_creation__date__gte=debut_periode,
        )
    queryset = (
        eleves_kpi
        .select_related("centre", "formation")
        .annotate(nombre_prospections=Count(
            "prospections", distinct=True, **filtre_date_prospection,
        ))
    )

    recherche = request.GET.get("q", "").strip()
    if recherche:
        queryset = queryset.filter(
            Q(username__icontains=recherche)
            | Q(first_name__icontains=recherche)
            | Q(last_name__icontains=recherche)
            | Q(email__icontains=recherche)
        )

    type_contrat_selectionne = request.GET.get("type_contrat", "tous")
    if type_contrat_selectionne in {choix for choix, _ in TypeContrat.choices}:
        queryset = queryset.filter(prospections__type_contrat=type_contrat_selectionne).distinct()

    validation_selectionnee = request.GET.get("is_valide", "")
    if validation_selectionnee == "true":
        queryset = queryset.filter(is_valide=True)
    elif validation_selectionnee == "false":
        queryset = queryset.filter(is_valide=False)

    tri = request.GET.get("tri", "username")
    if tri not in CHAMPS_TRIABLES:
        tri = "username"
    ordre = request.GET.get("ordre", "asc")
    if ordre not in {"asc", "desc"}:
        ordre = "asc"
    champ_ordre = tri if ordre == "asc" else f"-{tri}"
    queryset = queryset.order_by(champ_ordre, "pk")

    pagination = Paginator(queryset, NOMBRE_PAR_PAGE).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    params_tous_eleves = request.GET.copy()
    params_tous_eleves.pop