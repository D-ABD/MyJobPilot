"""Recherche globale des données visibles par l'utilisateur connecté."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

from comptes.models import Utilisateur
from comptes.scope_utils import centres_du_superviseur
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
