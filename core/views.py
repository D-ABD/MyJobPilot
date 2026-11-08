"""Recherche globale et gestion des tâches visibles par l'utilisateur connecté."""
from datetime import datetime, time, timezone as datetime_timezone
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime, parse_date
from django.utils import timezone
from django.views.decorators.http import require_POST

from comptes.models import JournalAction, Utilisateur
from comptes.scope_utils import centres_du_superviseur
from .external_apis import rechercher_entreprises_lba, rechercher_offres_lba
from .forms import OffresAlternanceForm, TacheForm
from .models import Tache
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
    if request.method == "GET" and request.GET:
        if form.is_valid():
            codes_rome = form.cleaned_data["code_rome"].split(",") if form.cleaned_data["code_rome"] else []
            ville = form.cleaned_data["ville"]
            rayon = form.cleaned_data["rayon"]
            tri = form.cleaned_data["tri"] or "recent"
            if codes_rome:
                recherche_effectuee = True
                codes_rome = [code.strip().upper() for code in codes_rome]
                offres = rechercher_offres_lba(",".join(codes_rome), ville, rayon)
                entreprises = rechercher_entreprises_lba(",".join(codes_rome), ville, rayon)
                offres = _trier_offres(offres, tri, codes_rome)
                params_base = request.GET.copy()
                for parametre in PAGE_PARAMETRES_OFFERTS:
                    params_base.pop(parametre, None)
                offres_pagination = _pagination_contexte(request, offres, "page_offres", params_base)
                entreprises_pagination = _pagination_contexte(request, entreprises, "page_entreprises", params_base)
                offres_page = offres_pagination.pop("page_obj")
                entreprises_page = entreprises_pagination.pop("page_obj")
                offres = offres_page.object_list
                entreprises = entreprises_page.object_list
            else:
                message_aide = "Saisissez votre code ROME, ou consultez le référentiel France Travail."
    return render(request, "offres/recherche.html", {
        "form": form,
        "offres": offres,
        "entreprises": entreprises,
        "recherche_effectuee": recherche_effectuee,
        "message_aide": message_aide,
        "offres_page": offres_page,
        "entreprises_page": entreprises_page,
        "offres_pagination": offres_pagination,
        "entreprises_pagination": entreprises_pagination,
    })


def _normaliser(texte):
    """Réutilise la normalisation accent-insensible du référentiel d'entreprises."""
    from entreprises.views import _normaliser_recherche_entreprise

    return _normaliser_recherche_entreprise(texte)


def _limiter_resultats(queryset, terme, extraire_texte):
    resultats = []
    for objet in queryset:
        valeurs = extraire_texte(objet)
        if any(terme in _normaliser(valeur) for valeur in valeurs if valeur):
            resultats.append(objet)
            if len(resultats) == NB_MAX_RESULTATS:
                break
    return resultats


@login_required
def recherche(request):
    terme_saisi = request.GET.get("q", "").strip()
    contexte = {
        "terme": terme_saisi,
        "prospections": [],
        "documents": [],
        "eleves": [],
        "message_recherche": "",
    }
    if not terme_saisi:
        contexte["message_recherche"] = "Saisissez un terme de recherche pour commencer."
        return render(request, "recherche.html", contexte)

    terme = _normaliser(terme_saisi)
    if not terme:
        contexte["message_recherche"] = f"Aucun résultat pour « {terme_saisi} ». Essayez un autre terme."
        return render(request, "recherche.html", contexte)
    role = request.user.role
    prospections = Prospection.objects.select_related("entreprise", "eleve")
    documents = Document.objects.listing().select_related("eleve")
    eleves = Utilisateur.objects.none()

    if role == Utilisateur.Role.ELEVE:
        prospections = prospections.filter(eleve=request.user)
        documents = documents.filter(eleve=request.user)
    elif role == Utilisateur.Role.SUPERVISEUR:
        centres = centres_du_superviseur(request.user)
        scope_eleve = Q(eleve__role=Utilisateur.Role.ELEVE, eleve__centre_id__in=centres)
        prospections = prospections.filter(Q(eleve=request.user) | scope_eleve)
        documents = documents.filter(Q(eleve=request.user) | scope_eleve)
        eleves = Utilisateur.objects.filter(
            role=Utilisateur.Role.ELEVE,
            centre_id__in=centres,
        ).only("pk", "username", "first_name", "last_name", "email")
    elif role == Utilisateur.Role.ADMIN:
        eleves = Utilisateur.objects.filter(
            role=Utilisateur.Role.ELEVE,
        ).only("pk", "username", "first_name", "last_name", "email")
    else:
        raise PermissionDenied

    prospection_resultats = _limiter_resultats(
        prospections,
        terme,
        lambda prospection: (prospection.entreprise.nom,),
    )
    document_resultats = _limiter_resultats(
        documents,
        terme,
        lambda document: (document.nom,),
    )
    eleve_resultats = _limiter_resultats(
        eleves,
        terme,
        lambda eleve: (eleve.username, eleve.email, eleve.first_name, eleve.last_name),
    )

    contexte["prospections"] = [{
        "objet": prospection,
        "url": reverse("entreprises:reference_detail", args=[prospection.entreprise_id]),
    } for prospection in prospection_resultats]
    contexte["documents"] = [{
        "objet": document,
        "url": reverse("documents:download", args=[document.pk]),
    } for document in document_resultats]
    if role in {Utilisateur.Role.ADMIN, Utilisateur.Role.SUPERVISEUR}:
        nom_url = (
            "admin_dashboard:eleve_detail"
            if role == Utilisateur.Role.ADMIN
            else "staff:detail_eleve"
        )
        contexte["eleves"] = [{
            "username": eleve.username,
            "nom_complet": " ".join(part for part in (eleve.first_name, eleve.last_name) if part),
            "url": reverse(nom_url, args=[eleve.pk]),
        } for eleve in eleve_resultats]

    if not any((contexte["prospections"], contexte["documents"], contexte["eleves"])):
        contexte["message_recherche"] = f"Aucun résultat pour « {terme_saisi} ». Essayez un autre terme."
    return render(request, "recherche.html", contexte)


def taches_visibles(utilisateur):
    """Queryset commun aux pages et au badge, limité au rôle connecté."""
    taches = Tache.objects.select_related("createur", "assigne_a", "prospection", "prospection__entreprise")
    if utilisateur.role == Utilisateur.Role.ELEVE:
        return taches.filter(Q(assigne_a=utilisateur) | Q(createur=utilisateur)).distinct()
    if utilisateur.role == Utilisateur.Role.SUPERVISEUR:
        centres = centres_du_superviseur(utilisateur)
        return taches.filter(
            Q(assigne_a=utilisateur)
            | Q(assigne_a__role=Utilisateur.Role.ELEVE, assigne_a__centre_id__in=centres)
        ).distinct()
    if utilisateur.role == Utilisateur.Role.ADMIN:
        return taches
    raise PermissionDenied


def _verifier_role_taches(utilisateur):
    if utilisateur.role not in {
        Utilisateur.Role.ELEVE,
        Utilisateur.Role.SUPERVISEUR,
        Utilisateur.Role.ADMIN,
    }:
        raise PermissionDenied


def _verifier_assignation_postee(request):
    identifiant = request.POST.get("assigne_a", "").strip()
    if not identifiant:
        return
    autorises = TacheForm(user=request.user).fields["assigne_a"].queryset
    if Utilisateur.objects.filter(pk=identifiant).exists() and not autorises.filter(pk=identifiant).exists():
        raise PermissionDenied


def _journaliser_tache(utilisateur, action, tache):
    JournalAction.objects.create(
        utilisateur=utilisateur,
        action=action,
        cible_type="Tache",
        cible_id=str(tache.pk),
        details={"titre": tache.titre, "assigne_a_id": tache.assigne_a_id},
    )


@login_required
def taches_liste(request):
    _verifier_role_taches(request.user)
    queryset = taches_visibles(request.user)
    statut = request.GET.get("statut", "tous")
    if statut in {code for code, _ in Tache.Statut.choices}:
        queryset = queryset.filter(statut=statut)
    tri = request.GET.get("tri", "date_echeance")
    if tri not in {"titre", "date_echeance", "statut", "date_creation"}:
        tri = "date_echeance"
    ordre = request.GET.get("ordre", "asc")
    if ordre not in {"asc", "desc"}:
        ordre = "asc"
    champ_tri = tri if ordre == "asc" else f"-{tri}"
    queryset = queryset.order_by(champ_tri, "-date_creation")
    total_count = queryset.count()
    page_obj = Paginator(queryset, 25).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    pagination_query = params.urlencode()
    return render(request, "taches/liste.html", {
        "taches": page_obj.object_list,
        "page_obj": page_obj,
        "total_count": total_count,
        "statuts": Tache.Statut.choices,
        "filtre_statut": statut,
        "filtre_tri": tri,
        "filtre_ordre": ordre,
        "pagination_query": pagination_query,
        "taches_a_faire": taches_visibles(request.user).filter(statut=Tache.Statut.A_FAIRE).count(),
    })


@login_required
def taches_compteur(request):
    _verifier_role_taches(request.user)
    count = taches_visibles(request.user).filter(statut=Tache.Statut.A_FAIRE).count()
    return JsonResponse({"count": count})


@login_required
def tache_nouvelle(request):
    _verifier_role_taches(request.user)
    if request.method == "POST":
        _verifier_assignation_postee(request)
        form = TacheForm(request.POST, user=request.user)
        if form.is_valid():
            tache = form.save(commit=False)
            tache.createur = request.user
            tache.save()
            _journaliser_tache(request.user, JournalAction.Action.TACHE_CREE, tache)
            return redirect("core:taches_liste")
    else:
        form = TacheForm(user=request.user, initial={"assigne_a": request.user.pk})
    return render(request, "taches/form.html", {"form": form, "titre": "Nouvelle tâche"})


def _tache_visible(request, pk):
    _verifier_role_taches(request.user)
    return get_object_or_404(taches_visibles(request.user), pk=pk)


def _verifier_createur_ou_admin(request, tache):
    if request.user != tache.createur and request.user.role != Utilisateur.Role.ADMIN:
        raise PermissionDenied


@login_required
def tache_modifier(request, pk):
    tache = _tache_visible(request, pk)
    _verifier_createur_ou_admin(request, tache)
    if request.method == "POST":
        _verifier_assignation_postee(request)
        form = TacheForm(request.POST, instance=tache, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("core:taches_liste")
    else:
        form = TacheForm(instance=tache, user=request.user)
    return render(request, "taches/form.html", {"form": form, "titre": "Modifier la tâche", "tache": tache})


@login_required
@require_POST
def tache_terminer(request, pk):
    tache = _tache_visible(request, pk)
    if (
        request.user != tache.createur
        and request.user != tache.assigne_a
        and request.user.role != Utilisateur.Role.ADMIN
    ):
        raise PermissionDenied
    if tache.statut != Tache.Statut.TERMINEE:
        tache.statut = Tache.Statut.TERMINEE
        tache.save(update_fields=["statut", "date_modification"])
        _journaliser_tache(request.user, JournalAction.Action.TACHE_TERMINEE, tache)
    return redirect("core:taches_liste")


@login_required
def tache_supprimer(request, pk):
    tache = _tache_visible(request, pk)
    _verifier_createur_ou_admin(request, tache)
    if request.method == "POST":
        _journaliser_tache(request.user, JournalAction.Action.TACHE_SUPPRIMEE, tache)
        tache.delete()
        return redirect("core:taches_liste")
    return render(request, "taches/confirm_delete.html", {"tache": tache})
