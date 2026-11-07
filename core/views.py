"""Recherche globale et gestion des tâches visibles par l'utilisateur connecté."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from comptes.models import JournalAction, Utilisateur
from comptes.scope_utils import centres_du_superviseur
from .forms import TacheForm
from .models import Tache
from documents.models import Document
from entreprises.models import Prospection


NB_MAX_RESULTATS = 20


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
