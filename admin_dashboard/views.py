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
from .import_csv import importer_eleves_csv
from documents.models import Document
from entreprises.forms import ChangementStatutForm, CommentaireForm
from entreprises.models import Commentaire, HistoriqueStatut, Prospection, Statut, TypeContrat
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
    now = timezone.now()
    demandes_ouvertes = DemandeRGPD.objects.filter(
        statut__in=[StatutDemande.RECUE, StatutDemande.EN_COURS],
    )
    en_retard = demandes_ouvertes.filter(date_demande__lt=now - timedelta(days=25)).count()
    stats = {
        "eleves_valides": Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE, is_valide=True).count(),
        "eleves_attente": Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE, is_valide=False).count(),
        "superviseurs_actifs": Utilisateur.objects.filter(role=Utilisateur.Role.SUPERVISEUR, is_active=True).count(),
        "prospections_totales": Prospection.objects.count(),
        "demandes_rgpd_attente": demandes_ouvertes.count(),
        "demandes_rgpd_retard": en_retard,
    }
    return render(request, "admin_dashboard/dashboard.html", {"stats": stats})


@administrateur_requis
def admin_eleves_list(request):
    eleves = Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE).select_related(
        "centre", "formation", "valide_par",
    ).annotate(nb_prospections=Count("prospections", distinct=True))
    q = request.GET.get("q", "").strip()
    centre = request.GET.get("centre", "").strip()
    is_valide = request.GET.get("is_valide", "").strip().lower()
    if q:
        eleves = eleves.filter(Q(username__icontains=q) | Q(email__icontains=q))
    if centre.isdigit():
        eleves = eleves.filter(centre_id=int(centre))
    if is_valide in {"true", "false"}:
        eleves = eleves.filter(is_valide=(is_valide == "true"))
    eleves = _tri(
        eleves, request,
        {"username", "email", "last_name", "centre__nom", "is_valide", "date_joined"},
        "username",
    )
    return render(request, "admin_dashboard/eleves_list.html", {
        "page_obj": _page(request, eleves),
        "centres": Centre.objects.all(),
        "filtres": {"q": q, "centre": centre, "is_valide": is_valide},
        "query_params": _query_params(request),
    })


@administrateur_requis
def admin_superviseurs_list(request):
    superviseurs = Utilisateur.objects.filter(
        role=Utilisateur.Role.SUPERVISEUR,
    ).prefetch_related("scopes__centre")
    superviseurs = superviseurs.order_by("username")
    return render(request, "admin_dashboard/superviseurs_list.html", {
        "page_obj": _page(request, superviseurs),
        "query_params": _query_params(request),
    })


@administrateur_requis
def admin_superviseur_create(request):
    form = SuperviseurCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        superviseur = form.save(auteur=request.user)
        messages.success(request, f"Le superviseur {superviseur.username} a été créé avec son premier scope.")
        return redirect("admin_dashboard:superviseurs")
    return render(request, "admin_dashboard/superviseur_form.html", {"form": form})


@administrateur_requis
def admin_superviseur_scopes(request, pk):
    superviseur = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.SUPERVISEUR)
    scopes = ScopeSuperviseur.objects.filter(superviseur=superviseur).select_related("centre").order_by("-is_active", "centre__nom")
    return render(request, "admin_dashboard/superviseur_scopes.html", {
        "superviseur": superviseur,
        "page_obj": _page(request, scopes),
        "form": ScopeCreateForm(superviseur=superviseur),
        "afficher_formulaire": False,
        "query_params": _query_params(request),
    })


@administrateur_requis
def admin_scope_create(request, pk):
    superviseur = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.SUPERVISEUR)
    form = ScopeCreateForm(request.POST or None, superviseur=superviseur)
    if request.method == "POST" and form.is_valid():
        centre = form.cleaned_data["centre"]
        scope, cree = ScopeSuperviseur.objects.get_or_create(
            superviseur=superviseur, centre=centre,
            defaults={"cree_par": request.user, "is_active": True},
        )
        if not cree and not scope.is_active:
            scope.is_active = True
            scope.date_desactivation = None
            scope.cree_par = request.user
            scope.save(update_fields=["is_active", "date_desactivation", "cree_par"])
            log_action(
                JournalAction.Action.SCOPE_CREE, utilisateur=request.user, cible=scope,
                details={"action": "reactivation", "superviseur_id": superviseur.pk, "centre_id": centre.pk},
                request=request,
            )
        elif cree:
            log_action(
                JournalAction.Action.SCOPE_CREE, utilisateur=request.user, cible=scope,
                details={"superviseur_id": superviseur.pk, "centre_id": centre.pk},
                request=request,
            )
        messages.success(request, f"Scope mis à jour pour {centre.nom}.")
        return redirect("admin_dashboard:superviseur_scopes", pk=superviseur.pk)
    scopes = ScopeSuperviseur.objects.filter(superviseur=superviseur).select_related("centre").order_by("-is_active", "centre__nom")
    return render(request, "admin_dashboard/superviseur_scopes.html", {
        "superviseur": superviseur,
        "page_obj": _page(request, scopes),
        "form": form,
        "afficher_formulaire": True,
        "query_params": _query_params(request),
    }, status=200)


@administrateur_requis
@require_POST
def admin_scope_desactiver(request, pk):
    scope = get_object_or_404(ScopeSuperviseur.objects.select_related("superviseur"), pk=pk)
    if scope.is_active:
        scope.is_active = False
        scope.date_desactivation = timezone.now()
        scope.save(update_fields=["is_active", "date_desactivation"])
        log_action(
            JournalAction.Action.SCOPE_CREE, utilisateur=request.user, cible=scope,
            details={
                "action": "desactivation",
                "superviseur_id": scope.superviseur_id,
                "centre_id": scope.centre_id,
            },
            request=request,
        )
        messages.success(request, f"Le scope de {scope.centre.nom} a été désactivé.")
    return redirect("admin_dashboard:superviseur_scopes", pk=scope.superviseur_id)


@administrateur_requis
def admin_demandes_rgpd_list(request):
    demandes = DemandeRGPD.objects.select_related("utilisateur", "traitee_par")
    q = request.GET.get("q", "").strip()
    statut = request.GET.get("statut", "").strip()
    type_demande = request.GET.get("type", "").strip()
    if q:
        demandes = demandes.filter(
            Q(utilisateur__username__icontains=q) | Q(utilisateur__email__icontains=q),
        )
    valid_statuses = {value for value, _ in StatutDemande.choices}
    if statut in valid_statuses:
        demandes = demandes.filter(statut=statut)
    valid_types = {value for value, _ in TypeDemande.choices}
    if type_demande in valid_types:
        demandes = demandes.filter(type=type_demande)
    demandes = _tri(
        demandes, request,
        {"date_demande", "date_traitement", "statut", "type", "utilisateur__username"},
        "date_demande",
    )
    return render(request, "admin_dashboard/demandes_rgpd_list.html", {
        "page_obj": _page(request, demandes),
        "filtres": {"q": q, "statut": statut, "type": type_demande},
        "date_limite": timezone.now() - timedelta(days=25),
        "statuts": StatutDemande.choices,
        "types": TypeDemande.choices,
        "query_params": _query_params(request),
    })


def _csv_response(request, nom, entetes, lignes):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(entetes)
    count = 0
    for ligne in lignes:
        writer.writerow(ligne)
        count += 1
    response = HttpResponse(
        "\ufeff" + buffer.getvalue(),
        content_type="text/csv; charset=utf-8",
    )
    date_fichier = timezone.localdate().isoformat()
    response["Content-Disposition"] = f'attachment; filename="{nom}_{date_fichier}.csv"'
    log_action(
        JournalAction.Action.EXPORT_CSV,
        utilisateur=request.user,
        details={"type": nom, "nb_lignes": count},
        request=request,
    )
    return response


def _format_date(value):
    return value.isoformat() if value else ""


@administrateur_requis
def admin_export_csv(request):
    return render(request, "admin_dashboard/exports.html")


@administrateur_requis
def admin_export_eleves_csv(request):
    eleves = Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE).select_related(
        "centre", "formation", "valide_par",
    ).annotate(nb=Count("prospections", distinct=True)).order_by("username")
    headers = [
        "username", "email", "first_name", "last_name", "centre", "formation",
        "is_valide", "date_validation", "valide_par", "motif_refus", "date_joined",
        "nb_prospections",
    ]
    rows = (
        [
            e.username, e.email, e.first_name, e.last_name,
            e.centre.nom if e.centre_id else "",
            e.formation.nom if e.formation_id else "",
            e.is_valide, _format_date(e.date_validation),
            e.valide_par.username if e.valide_par_id else "",
            e.motif_refus, _format_date(e.date_joined), e.nb,
        ]
        for e in eleves
    )
    return _csv_response(request, "eleves", headers, rows)


@administrateur_requis
def admin_export_prospections_csv(request):
    prospections = Prospection.objects.select_related("eleve", "entreprise").order_by("eleve__username", "entreprise__nom")
    headers = [
        "eleve_username", "entreprise_nom", "entreprise_ville", "statut", "type_contrat",
        "date_creation", "date_modification", "date_relance", "date_candidature",
        "date_entretien", "date_refus", "date_acceptation",
    ]
    rows = ([
        p.eleve.username, p.entreprise.nom, p.entreprise.ville, p.statut, p.type_contrat,
        _format_date(p.date_creation), _format_date(p.date_modification),
        _format_date(p.date_relance), _format_date(p.date_candidature),
        _format_date(p.date_entretien), _format_date(p.date_refus),
        _format_date(p.date_acceptation),
    ] for p in prospections)
    return _csv_response(request, "prospections", headers, rows)


@administrateur_requis
def admin_export_historique_csv(request):
    historique = HistoriqueStatut.objects.select_related(
        "prospection__eleve", "prospection__entreprise", "auteur",
    ).order_by("date_changement", "pk")
    headers = [
        "eleve_username", "entreprise_nom", "ancien_statut", "nouveau_statut",
        "date_changement", "auteur_username", "commentaire", "date_associee",
    ]
    rows = ([
        h.prospection.eleve.username, h.prospection.entreprise.nom,
        h.ancien_statut, h.nouveau_statut, _format_date(h.date_changement),
        h.auteur.username if h.auteur_id else "système",
        h.commentaire, _format_date(h.date_associee),
    ] for h in historique)
    return _csv_response(request, "historique", headers, rows)


@administrateur_requis
def admin_export_demandes_rgpd_csv(request):
    demandes = DemandeRGPD.objects.select_related("utilisateur", "traitee_par").order_by("date_demande")
    headers = [
        "utilisateur_username", "type", "statut", "date_demande",
        "date_traitement", "traitee_par_username", "motif_refus", "description",
    ]
    rows = ([
        d.utilisateur.username, d.type, d.statut, _format_date(d.date_demande),
        _format_date(d.date_traitement), d.traitee_par.username if d.traitee_par_id else "",
        d.motif_refus, d.description,
    ] for d in demandes)
    return _csv_response(request, "demandes-rgpd", headers, rows)



def _contexte_eleve_detail(eleve, type_contrat="tous"):
    prospections = Prospection.objects.filter(eleve=eleve).select_related(
        "entreprise",
    ).prefetch_related("historique__auteur")
    if type_contrat in {choix for choix, _ in TypeContrat.choices}:
        prospections = prospections.filter(type_contrat=type_contrat)
    return {
        "eleve": eleve,
        "prospections": prospections,
        "types_contrat": TypeContrat.choices,
        "filtre_type_contrat": type_contrat,
        "documents": Document.objects.listing().filter(eleve=eleve),
        "commentaires": Commentaire.objects.filter(
            prospection__eleve=eleve,
        ).select_related("auteur", "prospection__entreprise").order_by("-date"),
        "demandes_rgpd": DemandeRGPD.objects.filter(utilisateur=eleve),
    }


@administrateur_requis
def admin_eleve_detail(request, pk):
    eleve = get_object_or_404(
        Utilisateur.objects.select_related("centre", "formation", "valide_par"),
        pk=pk, role=Utilisateur.Role.ELEVE,
    )
    type_contrat = request.GET.get("type_contrat", "tous")
    return render(request, "admin_dashboard/eleve_detail.html", _contexte_eleve_detail(eleve, type_contrat))


@administrateur_requis
@require_POST
def admin_eleve_valider(request, pk):
    eleve = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.ELEVE)
    if not eleve.is_valide:
        eleve.is_valide = True
        eleve.date_validation = timezone.now()
        eleve.valide_par = request.user
        eleve.motif_refus = ""
        eleve.save(update_fields=["is_valide", "date_validation", "valide_par", "motif_refus"])
        log_action(
            JournalAction.Action.COMPTE_VALIDE, utilisateur=request.user, cible=eleve,
            details={"eleve_id": eleve.pk}, request=request,
        )
        messages.success(request, "Le compte élève a été validé.")
    return redirect("admin_dashboard:eleve_detail", pk=eleve.pk)


@administrateur_requis
@require_POST
def admin_eleve_refuser(request, pk):
    eleve = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.ELEVE)
    form = RefusCompteForm(request.POST)
    if eleve.is_valide or not form.is_valid():
        messages.error(request, "Le refus exige un compte en attente et un motif.")
        return redirect("admin_dashboard:eleve_detail", pk=eleve.pk)
    eleve.motif_refus = form.cleaned_data["motif_refus"]
    eleve.date_validation = None
    eleve.valide_par = None
    eleve.save(update_fields=["motif_refus", "date_validation", "valide_par"])
    log_action(
        JournalAction.Action.COMPTE_REFUSE, utilisateur=request.user, cible=eleve,
        details={"eleve_id": eleve.pk, "motif_refus": eleve.motif_refus},
        request=request,
    )
    messages.success(request, "Le compte élève a été refusé.")
    return redirect("admin_dashboard:eleve_detail", pk=eleve.pk)


@administrateur_requis
@require_POST
def admin_eleve_desactiver(request, pk):
    eleve = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.ELEVE)
    if eleve.is_active:
        eleve.is_active = False
        eleve.save(update_fields=["is_active"])
        invalidate_user_sessions(eleve)
        log_action(
            JournalAction.Action.COMPTE_DESACTIVE, utilisateur=request.user, cible=eleve,
            details={"eleve_id": eleve.pk}, request=request,
        )
        messages.success(request, "Le compte élève a été désactivé.")
    return redirect("admin_dashboard:eleve_detail", pk=eleve.pk)


@administrateur_requis
@require_POST
def admin_eleve_reactiver(request, pk):
    eleve = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.ELEVE)
    if not eleve.is_active:
        eleve.is_active = True
        eleve.save(update_fields=["is_active"])
        messages.success(request, "Le compte élève a été réactivé.")
    return redirect("admin_dashboard:eleve_detail", pk=eleve.pk)


@administrateur_requis
def admin_eleve_changer_centre(request, pk):
    eleve = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.ELEVE)
    ancien_centre_id = eleve.centre_id
    form = AdminEleveCentreForm(request.POST or None, instance=eleve)
    if request.method == "POST" and form.is_valid():
        form.save()
        if ancien_centre_id != eleve.centre_id:
            log_action(
                JournalAction.Action.CHANGEMENT_CENTRE, utilisateur=request.user,
                cible=eleve,
                details={
                    "ancien_centre_id": ancien_centre_id,
                    "nouveau_centre_id": eleve.centre_id,
                    "eleve_id": eleve.pk,
                },
                request=request,
            )
        messages.success(request, "Le centre et la formation de l'élève ont été modifiés.")
        return redirect("admin_dashboard:eleve_detail", pk=eleve.pk)
    contexte = _contexte_eleve_detail(eleve)
    contexte.update({
        "action_form": form,
        "action_url": reverse("admin_dashboard:eleve_changer_centre", args=[pk]),
        "action_title": "Modifier le centre et la formation",
    })
    return render(request, "admin_dashboard/eleve_detail.html", contexte, status=200)


@administrateur_requis
def admin_eleve_changer_formation(request, pk):
    eleve = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.ELEVE)
    form = AdminEleveFormationForm(request.POST or None, instance=eleve)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "La formation de l'élève a été modifiée.")
        return redirect("admin_dashboard:eleve_detail", pk=eleve.pk)
    contexte = _contexte_eleve_detail(eleve)
    contexte.update({
        "action_form": form,
        "action_url": reverse("admin_dashboard:eleve_changer_formation", args=[pk]),
        "action_title": "Modifier la formation",
    })
    return render(request, "admin_dashboard/eleve_detail.html", contexte, status=200)


@administrateur_requis
def admin_superviseur_detail(request, pk):
    superviseur = get_object_or_404(
        Utilisateur.objects.prefetch_related("scopes__centre"),
        pk=pk, role=Utilisateur.Role.SUPERVISEUR,
    )
    return render(request, "admin_dashboard/superviseur_detail.html", {
        "superviseur": superviseur,
        "scopes": superviseur.scopes.all(),
    })


@administrateur_requis
def admin_superviseur_modifier(request, pk):
    superviseur = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.SUPERVISEUR)
    form = AdminSuperviseurUpdateForm(request.POST or None, instance=superviseur)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Les informations du superviseur ont été modifiées.")
        return redirect("admin_dashboard:superviseur_detail", pk=superviseur.pk)
    return render(request, "admin_dashboard/superviseur_detail.html", {
        "superviseur": superviseur,
        "scopes": superviseur.scopes.select_related("centre"),
        "action_form": form,
        "action_url": reverse("admin_dashboard:superviseur_modifier", args=[pk]),
        "action_title": "Modifier le superviseur",
    })


@administrateur_requis
def admin_superviseur_mot_de_passe(request, pk):
    superviseur = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.SUPERVISEUR)
    form = MotDePasseSuperviseurForm(request.POST or None, user=superviseur)
    if request.method == "POST" and form.is_valid():
        superviseur.set_password(form.cleaned_data["nouveau_mot_de_passe"])
        superviseur.save(update_fields=["password"])
        messages.success(request, "Le mot de passe du superviseur a été modifié.")
        return redirect("admin_dashboard:superviseur_detail", pk=superviseur.pk)
    return render(request, "admin_dashboard/superviseur_detail.html", {
        "superviseur": superviseur,
        "scopes": superviseur.scopes.select_related("centre"),
        "action_form": form,
        "action_url": reverse("admin_dashboard:superviseur_mot_de_passe", args=[pk]),
        "action_title": "Changer le mot de passe",
    })


@administrateur_requis
@require_POST
def admin_superviseur_desactiver(request, pk):
    superviseur = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.SUPERVISEUR)
    if superviseur.is_active:
        superviseur.is_active = False
        superviseur.save(update_fields=["is_active"])
        invalidate_user_sessions(superviseur)
        log_action(
            JournalAction.Action.COMPTE_DESACTIVE, utilisateur=request.user, cible=superviseur,
            details={"action": "desactivation_superviseur", "superviseur_id": superviseur.pk},
            request=request,
        )
        messages.success(request, "Le compte superviseur a été désactivé.")
    return redirect("admin_dashboard:superviseur_detail", pk=superviseur.pk)


@administrateur_requis
@require_POST
def admin_superviseur_reactiver(request, pk):
    superviseur = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.SUPERVISEUR)
    if not superviseur.is_active:
        superviseur.is_active = True
        superviseur.save(update_fields=["is_active"])
        messages.success(request, "Le compte superviseur a été réactivé.")
    return redirect("admin_dashboard:superviseur_detail", pk=superviseur.pk)


@administrateur_requis
@require_POST
def admin_superviseur_supprimer(request, pk):
    superviseur = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.SUPERVISEUR)
    if request.POST.get("confirmation") != "oui":
        messages.error(request, "Cochez la confirmation pour supprimer ce superviseur.")
        return redirect("admin_dashboard:superviseur_detail", pk=superviseur.pk)
    superviseur_id = superviseur.pk
    invalidate_user_sessions(superviseur)
    log_action(
        JournalAction.Action.COMPTE_DESACTIVE, utilisateur=request.user, cible=superviseur,
        details={"action": "suppression_superviseur", "superviseur_id": superviseur_id},
        request=request,
    )
    superviseur.delete()
    messages.success(request, "Le superviseur et ses scopes ont été supprimés.")
    return redirect("admin_dashboard:superviseurs")


@administrateur_requis
def admin_prospection_detail(request, pk):
    prospection = get_object_or_404(
        Prospection.objects.select_related("eleve", "entreprise"),
        pk=pk,
    )
    return render(request, "admin_dashboard/prospection_detail.html", {
        "prospection": prospection,
        "historique": prospection.historique.select_related("auteur"),
        "commentaires": prospection.commentaires.select_related("auteur"),
        "statut_form": ChangementStatutForm(initial={"nouveau_statut": prospection.statut}),
        "commentaire_form": CommentaireForm(),
    })


@administrateur_requis
@require_POST
def admin_prospection_changer_statut(request, pk):
    prospection = get_object_or_404(Prospection.objects.select_related("entreprise"), pk=pk)
    form = ChangementStatutForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Le formulaire de changement de statut est invalide.")
        return redirect("admin_dashboard:prospection_detail", pk=pk)
    ancien_statut = prospection.statut
    nouveau_statut = form.cleaned_data["nouveau_statut"]
    date_associee = form.cleaned_data.get("date_associee")
    date_fields = {
        Statut.A_RELANCER: "date_relance",
        Statut.CANDIDATURE_ENVOYEE: "date_candidature",
        Statut.EN_ATTENTE: "date_mise_en_attente",
        Statut.ENTRETIEN_PROGRAMME: "date_entretien",
        Statut.REFUS: "date_refus",
        Statut.ACCEPTE: "date_acceptation",
    }
    with transaction.atomic():
        prospection.statut = nouveau_statut
        champ_date = date_fields.get(nouveau_statut)
        if champ_date:
            valeur_date = date_associee
            if champ_date == "date_entretien" and date_associee:
                valeur_date = timezone.make_aware(
                    datetime.combine(date_associee, time.min),
                    timezone.get_current_timezone(),
                )
            setattr(prospection, champ_date, valeur_date)
        prospection.save()
        HistoriqueStatut.objects.create(
            prospection=prospection,
            ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut,
            auteur=request.user,
            commentaire=form.cleaned_data.get("commentaire", ""),
            date_associee=date_associee,
        )
        log_action(
            JournalAction.Action.CHANGEMENT_STATUT,
            utilisateur=request.user,
            cible=prospection,
            details={
                "prospection_id": prospection.pk,
                "ancien_statut": ancien_statut,
                "nouveau_statut": nouveau_statut,
            },
            request=request,
        )
        if ancien_statut != nouveau_statut:
            notifier_changement_statut(
                prospection, request.user, ancien_statut, nouveau_statut,
            )
    messages.success(request, "Le statut de la prospection a été modifié.")
    return redirect("admin_dashboard:prospection_detail", pk=pk)


@administrateur_requis
@require_POST
def admin_prospection_ajouter_commentaire(request, pk):
    prospection = get_object_or_404(
        Prospection.objects.select_related("eleve", "entreprise"), pk=pk,
    )
    form = CommentaireForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Le commentaire ne peut pas être vide.")
        return redirect("admin_dashboard:prospection_detail", pk=pk)
    commentaire = form.save(commit=False)
    commentaire.auteur = request.user
    commentaire.prospection = prospection
    commentaire.save()
    log_action(
        JournalAction.Action.COMMENTAIRE_CREE,
        utilisateur=request.user,
        cible=commentaire,
        details={"prospection_id": prospection.pk},
        request=request,
    )
    return redirect("admin_dashboard:prospection_detail", pk=pk)


@administrateur_requis
def admin_import_eleves_csv(request):
    rapport = None
    form = ImportElevesCSVForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        fichier = form.cleaned_data["fichier"]
        rapport = importer_eleves_csv(fichier)
        log_action(
            JournalAction.Action.IMPORT_CSV,
            utilisateur=request.user,
            details={
                "fichier": fichier.name,
                "total": rapport["total"],
                "crees": rapport["crees"],
                "rejetes": rapport["rejetes"],
            },
            request=request,
        )
    return render(request, "admin_dashboard/import_eleves.html", {"form": form, "rapport": rapport})
