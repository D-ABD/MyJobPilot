"""Recherche globale et gestion des tâches visibles par l'utilisateur connecté."""
from datetime import datetime, time, timezone as datetime_timezone
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import URLValidator
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.dateparse import parse_datetime, parse_date
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from comptes.models import JournalAction, Utilisateur
from comptes.scope_utils import centres_du_superviseur
from .external_apis import rechercher_entreprises_lba, rechercher_offres_lba
from .forms import OffresAlternanceForm, TacheForm
from .models import Badge, OffreEnregistree, Tache
from .gamification import calculer_progression_utilisateur, verifier_et_attribuer_badges
from documents.models import Document
from entreprises.models import Prospection


NB_MAX_RESULTATS = 20
PAGE_PARAMETRES_OFFERTS = ("page_offres", "page_entreprises")


def _date_publication(offre):
    valeur = offre.get("_publication_creation")
    if not valeur:
        return None
    date_heure = parse_datetime(valeur)
    if date_heure is None:
        date = parse_date(valeur)
        if date is None:
            return None
        date_heure = datetime.combine(date, time.min)
    if timezone.is_naive(date_heure):
        date_heure = date_heure.replace(tzinfo=datetime_timezone.utc)
    return date_heure


def _trier_offres(offres, tri, codes_rome):
    """Trie les offres de façon stable après le dédoublonnage effectué par le service LBA."""
    if tri == "lba":
        return offres
    if tri == "rome":
        ordre_codes = {code: index for index, code in enumerate(codes_rome)}
        groupes = {code: [] for code in codes_rome}
        sans_correspondance = []
        for offre in offres:
            rangs = [ordre_codes[code] for code in offre.get("_rome_codes", []) if code in ordre_codes]
            if rangs:
                groupes[codes_rome[min(rangs)]].append(offre)
            else:
                sans_correspondance.append(offre)
        return [offre for code in codes_rome for offre in groupes[code]] + sans_correspondance

    avec_date = []
    sans_date = []
    for offre in offres:
        date = _date_publication(offre)
        (avec_date if date is not None else sans_date).append((date, offre))
    avec_date.sort(key=lambda couple: couple[0], reverse=True)
    return [offre for _, offre in avec_date] + [offre for _, offre in sans_date]


def _pagination_contexte(request, resultats, parametre_page, params_base):
    page_obj = Paginator(resultats, NB_MAX_RESULTATS).get_page(request.GET.get(parametre_page))

    def url_page(numero):
        params = params_base.copy()
        params[parametre_page] = numero
        return f"?{params.urlencode()}"

    return {
        "page_obj": page_obj,
        "page_links": [{
            "number": numero,
            "url": url_page(numero),
            "current": numero == page_obj.number,
        } for numero in page_obj.paginator.page_range],
        "previous_url": url_page(page_obj.previous_page_number()) if page_obj.has_previous() else None,
        "next_url": url_page(page_obj.next_page_number()) if page_obj.has_next() else None,
    }


def offres_alternance(request):
    """Recherche publique d'offres et de recruteurs avec les données de LBA."""
    if request.method == "POST" and request.POST.get("creer_prospection"):
        if not request.user.is_authenticated:
            return redirect("comptes:connexion")
        if request.user.role == Utilisateur.Role.ELEVE:
            nom_url = "entreprises:create"
        elif request.user.role in {Utilisateur.Role.SUPERVISEUR, Utilisateur.Role.ADMIN}:
            nom_url = "entreprises:prospection_create_tout_role"
        else:
            raise PermissionDenied
        params = urlencode({
            "entreprise_nom": request.POST.get("entreprise_nom", "").strip(),
            "ville": request.POST.get("ville", "").strip(),
            "secteur": request.POST.get("secteur", "").strip(),
            "source": "La bonne alternance",
        })
        return redirect(f"{reverse(nom_url)}?{params}")

    initial = {"code_rome": request.user.codes_rome} if request.user.is_authenticated else {}
    form = OffresAlternanceForm(request.GET or None, initial=initial)
    offres = []
    entreprises = []
    recherche_effectuee = False
    message_aide = ""
    offres_page = entreprises_page = None
    offres_pagination = entreprises_pagination = None
    offres_enregistrees = set()
    if reques