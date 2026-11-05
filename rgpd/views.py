import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comptes.models import JournalAction, Utilisateur
from comptes.utils import log_action
from documents.models import Document
from entreprises.models import Commentaire, Prospection
from .forms import DemandeRGPDForm, TraitementDemandeRGPDForm
from .models import DemandeRGPD, StatutDemande


def _eleve(request):
    if request.user.role != Utilisateur.Role.ELEVE:
        raise PermissionDenied


def _admin(request):
    if request.user.role != Utilisateur.Role.ADMIN:
        raise PermissionDenied


@login_required
def demandes_rgpd_list(request):
    _eleve(request)
    demandes = DemandeRGPD.objects.filter(utilisateur=request.user)
    return render(request, "rgpd/demandes_rgpd_list.html", {"demandes": demandes})


@login_required
def demande_rgpd_create(request):
    _eleve(request)
    form = DemandeRGPDForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        demande = form.save(commit=False)
        demande.utilisateur = request.user
        demande.save()
        log_action(
            JournalAction.Action.DEMANDE_RGPD_MAJ, utilisateur=request.user,
            cible=demande, details={"ancien_statut": None, "nouveau_statut": demande.statut},
            request=request,
        )
        messages.success(request, "Votre demande RGPD a été enregistrée.")
        return redirect("rgpd:demandes_rgpd_list")
    return render(request, "rgpd/demande_rgpd_form.html", {
        "form": form,
        "breadcrumb_items": [
            ("Accueil", "/"),
            ("Mes demandes RGPD", "/mon-compte/demandes-rgpd/"),
            ("Nouvelle demande", ""),
        ],
    }, status=200)


@login_required
def demande_rgpd_detail(request, pk):
    _eleve(request)
    demande = get_object_or_404(DemandeRGPD, pk=pk, utilisateur=request.user)
    return render(request, "rgpd/demande_rgpd_detail.html", {
        "demande": demande,
        "breadcrumb_items": [
            ("Accueil", "/"),
            ("Mes demandes RGPD", "/mon-compte/demandes-rgpd/"),
            (demande.get_type_display(), ""),
        ],
    })


@login_required
def admin_demandes_rgpd_list(request):
    _admin(request)
    return render(request, "rgpd/admin_demandes_rgpd_list.html", {
        "demandes": DemandeRGPD.objects.select_related("utilisateur", "traitee_par").all(),
    })


@login_required
def admin_demande_rgpd_traiter(request, pk):
    _admin(request)
    demande = get_object_or_404(DemandeRGPD, pk=pk)
    ancien_statut = demande.statut
    form = TraitementDemandeRGPDForm(request.POST or None, instance=demande)
    if request.method == "POST" and form.is_valid():
        demande = form.save(commit=False)
        demande.traitee_par = request.user
        demande.date_traitement = timezone.now()
        demande.save()
        if ancien_statut != demande.statut:
            log_action(
                JournalAction.Action.DEMANDE_RGPD_MAJ, utilisateur=request.user,
                cible=demande,
                details={"ancien_statut": ancien_statut, "nouveau_statut": demande.statut},
                request=request,
            )
        messages.success(request, "La demande a été mise à jour.")
        return redirect("rgpd:admin_demandes_rgpd_list")
    return render(request, "rgpd/admin_demande_rgpd_traiter.html", {
        "form": form,
        "demande": demande,
        "breadcrumb_items": [
            ("Accueil", "/"),
            ("Demandes RGPD", "/admin-dashboard/demandes-rgpd/"),
            (demande.utilisateur.username, ""),
        ],
    }, status=200)


@login_required
def export_rgpd(request):
    _eleve(request)
    user = request.user
    consent = getattr(user, "consentement", None)
    prospections = []
    for p in Prospection.objects.filter(eleve=user).select_related("entreprise").prefetch_related("historique__auteur"):
        prospections.append({
            "entreprise": {"nom": p.entreprise.nom, "secteur": p.entreprise.secteur, "ville": p.entreprise.ville},
            "statut": p.statut,
            "dates": {
                "relance": p.date_relance.isoformat() if p.date_relance else None,
                "candidature": p.date_candidature.isoformat() if p.date_candidature else None,
                "mise_en_attente": p.date_mise_en_attente.isoformat() if p.date_mise_en_attente else None,
                "entretien": p.date_entretien.isoformat() if p.date_entretien else None,
                "refus": p.date_refus.isoformat() if p.date_refus else None,
                "acceptation": p.date_acceptation.isoformat() if p.date_acceptation else None,
            },
            "notes": p.notes,
            "historique": [{
                "ancien_statut": h.ancien_statut, "nouveau_statut": h.nouveau_statut,
                "date_changement": h.date_changement.isoformat(), "commentaire": h.commentaire,
                "date_associee": h.date_associee.isoformat() if h.date_associee else None,
            } for h in p.historique.all()],
        })
    payload = {
        "utilisateur": {
            "username": user.username, "email": user.email, "first_name": user.first_name,
            "last_name": user.last_name, "role": user.role,
            "centre": user.centre.nom if user.centre_id else None,
            "formation": user.formation.nom if user.formation_id else None,
            "date_joined": user.date_joined.isoformat(),
        },
        "consentement": ({
            "version": consent.version_politique,
            "date": consent.date_consentement.isoformat(), "ip": consent.ip,
        } if consent else None),
        "prospections": prospections,
        "documents": list(Document.objects.filter(eleve=user).values(
            "nom", "type", "taille", "date_upload",
        )),
        "commentaires": [{
            "contenu": c.contenu, "date": c.date.isoformat(),
            "prospection_id": c.prospection_id,
            "entreprise": c.prospection.entreprise.nom,
        } for c in Commentaire.objects.filter(
            prospection__eleve=user,
        ).select_related("prospection__entreprise")],
        "demandes_rgpd": [{
            "type": d.type, "statut": d.statut,
            "date_demande": d.date_demande.isoformat(),
            "date_traitement": d.date_traitement.isoformat() if d.date_traitement else None,
            "description": d.description, "motif_refus": d.motif_refus,
        } for d in DemandeRGPD.objects.filter(utilisateur=user)],
    }
    log_action(JournalAction.Action.EXPORT_RGPD, utilisateur=user, request=request)
    response = HttpResponse(json.dumps(payload, ensure_ascii=False, indent=2, default=str), content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="export-rgpd.json"'
    return response


def confidentialite(request):
    return render(request, "rgpd/confidentialite.html")
