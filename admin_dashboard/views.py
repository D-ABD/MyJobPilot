import csv
import io
from datetime import datetime, time, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.urls import reverse
from django.views.decorators.http import require_POST

from comptes.models import Centre, JournalAction, ScopeSuperviseur
from comptes.notifications import notifier_changement_statut
from comptes.utils import invalidate_user_sessions, log_action
from core.gamification import calculer_progression_utilisateur, verifier_et_attribuer_badges
from core.models import Objectif
from core.stats import (
    PERIODES_DASHBOARD,
    calculer_atteinte_objectif,
    calculer_kpis_dashboard,
    calculer_stats_admin,
    debut_periode_dashboard,
    normaliser_periode_dashboard,
)
from .import_csv import importer_eleves_csv
from documents.models import Document
from entreprises.forms import ChangementStatutForm, CommentaireForm
from entreprises.import_csv import importer_entreprises_csv
from entreprises.models import Commentaire, HistoriqueStatut, Prospection, Relance, Statut, TypeContrat
from rgpd.models import DemandeRGPD, StatutDemande, TypeDemande
from .forms import (
    AdminEleveCentreForm, AdminEleveFormationForm, AdminSuperviseurUpdateForm,
    MotDePasseSuperviseurForm, RefusCompteForm, ScopeCreateForm,
    SuperviseurCreateForm, ImportElevesCSVForm,
)

Utilisateur = get_user_model()
PAGE_SIZE = 25


def administrateur_requis(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != Utilisateur.Role.ADMIN:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def _page(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))


def _query_params(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


def _tri(queryset, request, autorises, defaut):
    champ = request.GET.get("tri", defaut)
    if champ not in autorises:
        champ = defaut
    if request.GET.get("ordre", "asc").lower() == "desc":
        champ = f"-{champ}"
    return queryset.order_by(champ)


@administrateur_requis
def dashboard_admin(request):
    periode = normaliser_periode_dashboard(request.GET.get("periode", "30"))
    eleves = Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE).select_related("centre", "formation")
    superviseurs = Utilisateur.objects.filter(role=Utilisateur.Role.SUPERVISEUR).order_by("username")

    superviseur_selectionne = request.GET.get("superviseur", "")
    centres_superviseur = None
    if superviseur_selectionne:
        if not superviseur_selectionne.isdigit():
            raise PermissionDenied
        superviseur = superviseurs.filter(pk=int(superviseur_selectionne)).first()
        if superviseur is None:
            raise PermissionDenied
        centres_superviseur = ScopeSuperviseur.objects.filter(
            superviseur=superviseur, is_active=True,
        ).values_list("centre_id", flat=True)
        eleves = eleves.filter(centre_id__in=centres_superviseur)
        superviseurs = superviseurs.filter(pk=superviseur.pk)

    centre_selectionne = request.GET.get("centre", "")
    centres = Centre.objects.order_by("nom")
    if centre_selectionne:
        if not centre_selectionne.isdigit() or not centres.filter(pk=int(centre_selectionne)).exists():
            raise PermissionDenied
        eleves = eleves.filter(centre_id=int(centre_selectionne))
    if centres_superviseur is not None:
        centres = centres.filter(pk__in=centres_superviseur)

    eleve_selectionne = request.GET.get("eleve", "")
    eleve_selectionne_obj = None
    if eleve_selectionne:
        if not eleve_selectionne.isdigit():
            raise PermissionDenied
        eleve = eleves.filter(pk=int(eleve_selectionne)).first()
        if eleve is None:
            raise PermissionDenied
        eleve_selectionne_obj = eleve
        eleves = eleves.filter(pk=eleve.pk)
    if centre_selectionne or eleve_selectionne:
        superviseurs = superviseurs.filter(
            scopes__is_active=True,
            scopes__centre_id__in=eleves.values_list("centre_id", flat=True),
        ).distinct()
    params_tous_eleves = request.GET.copy()
    params_tous_eleves.pop("eleve", None)

    now = timezone.now()
    demandes_ouvertes = DemandeRGPD.objects.filter(
        statut__in=[StatutDemande.RECUE, StatutDemande.EN_COURS],
        utilisateur__in=eleves,
    )
    debut = debut_periode_dashboard(periode)
    if debut:
        demandes_ouvertes = demandes_ouvertes.