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
from core.gamification import resume_badges, verifier_et_attribuer_badges
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
    params_tous_eleves.pop("eleve", None)
    centres_stats = Centre.objects.filter(pk__in=centres_ids, utilisateurs__in=eleves_kpi).annotate(
        nombre=Count("utilisateurs", filter=Q(
            utilisateurs__role=Utilisateur.Role.ELEVE, utilisateurs__in=eleves_kpi,
        ))
    ).distinct().order_by("nom")
    stats = [{"centre": centre, "nombre": centre.nombre} for centre in centres_stats]
    aujourd_hui = timezone.localdate()
    objectifs_actifs = Objectif.objects.filter(
        eleve__in=eleves_kpi,
        periode_debut__lte=aujourd_hui,
        periode_fin__gte=aujourd_hui,
    ).select_related("eleve", "createur")
    objectifs_actifs = [
        {"objectif": objectif, "atteinte": calculer_atteinte_objectif(objectif)}
        for objectif in objectifs_actifs
    ]
    tri_urls = {
        "username": _url_tri(request, "username", tri, ordre),
        "last_name": _url_tri(request, "last_name", tri, ordre),
        "centre": _url_tri(request, "centre__nom", tri, ordre),
        "is_valide": _url_tri(request, "is_valide", tri, ordre),
    }
    contexte = {
        "eleves": pagination.object_list,
        "page_obj": pagination,
        "centres": centres,
        "eleves_filtre": eleves_kpi.order_by("username"),
        "stats_par_centre": stats,
        "total_count": queryset.count(),
        "filtre_q": recherche,
        "filtre_centre": centre_selectionne,
        "filtre_eleve": eleve_selectionne,
        "eleve_selectionne_obj": eleve_selectionne_obj,
        "url_tous_eleves": f"{request.path}?{params_tous_eleves.urlencode()}" if params_tous_eleves else request.path,
        "filtre_periode": periode,
        "periodes_dashboard": PERIODES_DASHBOARD,
        "filtre_is_valide": validation_selectionnee,
        "filtre_type_contrat": type_contrat_selectionne,
        "types_contrat": TypeContrat.choices,
        "filtre_tri": tri,
        "filtre_ordre": ordre,
        "url_reset": request.path,
        "pagination_query": pagination_params.urlencode(),
        "tri_urls": tri_urls,
        "objectifs_actifs": objectifs_actifs,
        **calculer_stats_superviseur(request.user, eleves=eleves_kpi, periode=periode),
        **calculer_kpis_dashboard(eleves_kpi.values("pk"), periode=periode),
    }
    return render(request, "staff/dashboard.html", contexte)


def _utilisateur_gestion_objectifs(request):
    if request.user.role not in {Utilisateur.Role.ADMIN, Utilisateur.Role.SUPERVISEUR}:
        raise PermissionDenied
    if request.user.role == Utilisateur.Role.SUPERVISEUR:
        verifier_superviseur(request)


def _objectifs_gestionnables(request):
    objectifs = Objectif.objects.select_related("eleve", "createur")
    if request.user.role == Utilisateur.Role.SUPERVISEUR:
        objectifs = objectifs.filter(eleve__centre_id__in=centres_du_superviseur(request.user))
    return objectifs


def _eleves_objectifs(request):
    eleves = Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE)
    if request.user.role == Utilisateur.Role.SUPERVISEUR:
        eleves = eleves.filter(centre_id__in=centres_du_superviseur(request.user))
    return eleves


def _verifier_eleve_poste(request):
    """Refuse explicitement un élève situé hors du scope du superviseur."""
    eleve_id = request.POST.get("eleve")
    if request.user.role == Utilisateur.Role.SUPERVISEUR and eleve_id and eleve_id.isdigit():
        if not _eleves_objectifs(request).filter(pk=int(eleve_id)).exists():
            raise PermissionDenied


def _objectifs_avec_atteinte(objectifs):
    return [
        {"objectif": objectif, "atteinte": calculer_atteinte_objectif(objectif)}
        for objectif in objectifs
    ]


@login_required
def objectifs_liste(request):
    role = request.user.role
    if role == Utilisateur.Role.ADMIN:
        objectifs = Objectif.objects.all()
        peut_gerer = True
    elif role == Utilisateur.Role.SUPERVISEUR:
        verifier_superviseur(request)
        objectifs = _objectifs_gestionnables(request)
        peut_gerer = True
    elif role == Utilisateur.Role.ELEVE:
        objectifs = Objectif.objects.filter(eleve=request.user)
        peut_gerer = False
    else:
        raise PermissionDenied
    return render(request, "objectifs/liste.html", {
        "objectifs": _objectifs_avec_atteinte(objectifs),
        "peut_gerer": peut_gerer,
    })


@login_required
def objectif_nouveau(request):
    _utilisateur_gestion_objectifs(request)
    if request.method == "POST":
        _verifier_eleve_poste(request)
    form = ObjectifForm(request.POST or None, utilisateur=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            objectif = form.save(commit=False)
            objectif.createur = request.user
            objectif.save()
            log_action(
                JournalAction.Action.OBJECTIF_CREE,
                utilisateur=request.user,
                cible=objectif,
                details={"objectif_id": objectif.pk, "eleve_id": objectif.eleve_id, "type": objectif.type},
                request=request,
            )
        return redirect("objectifs:liste")
    return render(request, "objectifs/form.html", {"form": form, "action": "Créer"})


@login_required
def objectif_modifier(request, pk):
    if request.user.role == Utilisateur.Role.ELEVE:
        get_object_or_404(Objectif, pk=pk, eleve=request.user)
        raise PermissionDenied
    _utilisateur_gestion_objectifs(request)
    objectif = get_object_or_404(_objectifs_gestionnables(request), pk=pk)
    if request.method == "POST":
        _verifier_eleve_poste(request)
    form = ObjectifForm(request.POST or None, utilisateur=request.user, instance=objectif)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            objectif = form.save()
            log_action(
                JournalAction.Action.OBJECTIF_MODIFIE,
                utilisateur=request.user,
                cible=objectif,
                details={"objectif_id": objectif.pk, "eleve_id": objectif.eleve_id, "type": objectif.type},
                request=request,
            )
        return redirect("objectifs:liste")
    return render(request, "objectifs/form.html", {"form": form, "action": "Modifier", "objectif": objectif})


@login_required
def objectif_supprimer(request, pk):
    if request.method not in {"GET", "POST"}:
        raise PermissionDenied
    if request.user.role == Utilisateur.Role.ELEVE:
        get_object_or_404(Objectif, pk=pk, eleve=request.user)
        raise PermissionDenied
    _utilisateur_gestion_objectifs(request)
    objectif = get_object_or_404(_objectifs_gestionnables(request), pk=pk)
    if request.method == "GET":
        return render(request, "objectifs/confirm_delete.html", {"objectif": objectif})
    with transaction.atomic():
        details = {"objectif_id": objectif.pk, "eleve_id": objectif.eleve_id, "type": objectif.type}
        log_action(
            JournalAction.Action.OBJECTIF_SUPPRIME,
            utilisateur=request.user,
            cible=objectif,
            details=details,
            request=request,
        )
        objectif.delete()
    return redirect("objectifs:liste")


@login_required
def detail_eleve_staff(request, pk):
    """Affiche la fiche d'un élève au superviseur de son scope ou à l'admin."""
    if request.user.role not in {Utilisateur.Role.ADMIN, Utilisateur.Role.SUPERVISEUR}:
        raise PermissionDenied
    if request.user.role == Utilisateur.Role.SUPERVISEUR:
        verifier_superviseur(request)
    eleve = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.ELEVE)
    if request.user.role == Utilisateur.Role.SUPERVISEUR and not superviser_eleve(request.user, eleve):
        raise PermissionDenied
    return _rendre_detail_eleve(request, eleve)


def _eleve_pour_action(request, pk):
    """Retourne l'élève si l'utilisateur est admin ou superviseur autorisé."""
    role = request.user.role
    if role not in {Utilisateur.Role.ADMIN, Utilisateur.Role.SUPERVISEUR}:
        raise PermissionDenied
    if role == Utilisateur.Role.SUPERVISEUR:
        verifier_superviseur(request)
    eleve = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.ELEVE)
    if role == Utilisateur.Role.SUPERVISEUR and not superviser_eleve(request.user, eleve):
        raise PermissionDenied
    return eleve


def _rendre_detail_eleve(request, eleve, prospection_form=None, entreprise_form=None, codes_rome_form=None):
    verifier_et_attribuer_badges(eleve)
    prospections = (
        Prospection.objects.filter(eleve=eleve)
        .select_related("entreprise")
        .prefetch_related(
            Prefetch(
                "commentaires",
                queryset=Commentaire.objects.select_related("auteur"),
            )
        )
        .order_by("-date_modification")
    )
    type_contrat_selectionne = request.GET.get("type_contrat", "tous")
    if type_contrat_selectionne in {choix for choix, _ in TypeContrat.choices}:
        prospections = prospections.filter(type_contrat=type_contrat_selectionne)
    return render(
        request,
        "staff/detail_eleve.html",
        {
            "eleve": eleve,
            **resume_badges(eleve),
            "prospections": prospections,
            "historique_relances": Relance.objects.filter(
                prospection__eleve=eleve
            ).select_related("auteur", "prospection__entreprise")[:50],
            "types_contrat": TypeContrat.choices,
            "filtre_type_contrat": type_contrat_selectionne,
            "prospection_form": prospection_form if prospection_form is not None else AjoutProspectionStaffForm(),
            "entreprise_form": entreprise_form if entreprise_form is not None else EntrepriseForm(),
            "codes_rome_form": codes_rome_form or CodesRomeForm(initial={"codes_rome": eleve.codes_rome}),
            "breadcrumb_items": [
                ("Accueil", "/"),
                ("Mon staff", "/staff/"),
                (eleve.get_full_name() or eleve.username, ""),
            ],
        },
    )


@login_required
def modifier_codes_rome_eleve(request, pk):
    """Permet à l'admin ou au superviseur de modifier les codes de l'élève autorisé."""
    eleve = _eleve_pour_action(request, pk)
    if request.method != "POST":
        return redirect("staff:detail_eleve", pk=eleve.pk)
    form = CodesRomeForm(request.POST)
    if form.is_valid():
        nouveaux_codes = form.cleaned_data["codes_rome"]
        codes_modifies = eleve.codes_rome != nouveaux_codes
        eleve.codes_rome = nouveaux_codes
        eleve.save(update_fields=["codes_rome"])
        if codes_modifies and request.user.role == Utilisateur.Role.SUPERVISEUR:
            creer_notification(
                eleve,
                TypeNotification.CODES_ROME_MODIFIES,
                "Vos codes ROME ont été mis à jour par votre superviseur",
            )
        messages.success(request, "Les codes ROME de l’élève ont été mis à jour.")
        return redirect("staff:detail_eleve", pk=eleve.pk)
    return _rendre_detail_eleve(request, eleve, codes_rome_form=form)


@login_required
def changer_centre_eleve_staff(request, pk):
    """Change le centre d'un élève et journalise l'ancien et le nouveau."""
    eleve = _eleve_pour_action(request, pk)
    if request.user.role == Utilisateur.Role.ADMIN:
        centres = Centre.objects.all()
        centres_ids = None
    else:
        centres_ids = centres_du_superviseur(request.user)
        centres = Centre.objects.filter(pk__in=centres_ids)

    if request.method == "POST":
        centre_id = request.POST.get("centre", "")
        if request.user.role == Utilisateur.Role.SUPERVISEUR and centre_id:
            if not centre_id.isdigit() or int(centre_id) not in centres_ids:
                raise PermissionDenied
        form = ChangementCentreFormStaff(request.POST, centres=centres)
        if form.is_valid():
            nouveau_centre = form.cleaned_data["centre"]
            ancien_centre_id = eleve.centre_id
            if ancien_centre_id != nouveau_centre.pk:
                with transaction.atomic():
                    eleve.centre = nouveau_centre
                    eleve.save(update_fields=["centre"])
                    log_action(
                        JournalAction.Action.CHANGEMENT_CENTRE,
                        utilisateur=request.user,
                        cible=eleve,
                        details={
                            "ancien_centre_id": ancien_centre_id,
                            "nouveau_centre_id": nouveau_centre.pk,
                            "eleve_id": eleve.pk,
                        },
                        request=request,
                    )
            return redirect("staff:detail_eleve", pk=eleve.pk)
    else:
        form = ChangementCentreFormStaff(
            initial={"centre": eleve.centre_id},
            centres=centres,
        )

    return render(
        request,
        "staff/eleve_changer_centre.html",
        {
            "eleve": eleve,
            "form": form,
            "breadcrumb_items": [
                ("Accueil", "/"),
                ("Mon staff", "/staff/"),
                (eleve.get_full_name() or eleve.username, f"/staff/eleves/{eleve.pk}/"),
                ("Changer de centre", ""),
            ],
        },
    )


@login_required
def ajouter_entreprise_staff(request, pk):
    """Ajoute une prospection à un élève autorisé et journalise l'action."""
    eleve = _eleve_pour_action(request, pk)
    if request.method == "POST":
        form = AjoutProspectionStaffForm(request.POST)
        entreprise_form = EntrepriseForm(request.POST)
        if form.is_valid():
            entreprise = form.cleaned_data.get("entreprise_id")
            if entreprise is None and not entreprise_form.is_valid():
                return _rendre_detail_eleve(request, eleve, form, entreprise_form)
            if entreprise is None:
                if entreprise_form.cleaned_data["nom"].strip().casefold() != form.cleaned_data["entreprise_nom"].strip().casefold():
                    form.add_error("entreprise_nom", "Le nom doit correspondre aux informations de l'entreprise.")
                    return _rendre_detail_eleve(request, eleve, form, entreprise_form)
                entreprise = entreprise_form.save()
            if Prospection.objects.filter(eleve=eleve, entreprise=entreprise).exists():
                form.add_error("entreprise_nom", "Cet élève a déjà une prospection pour cette entreprise.")
                return _rendre_detail_eleve(request, eleve, form, entreprise_form)

            donnees = form.cleaned_data
            date_entretien = donnees.get("date_entretien")
            date_entretien = (
                timezone.make_aware(
                    datetime.combine(date_entretien, time.min),
                    timezone.get_current_timezone(),
                )
                if date_entretien
                else None
            )
            try:
                with transaction.atomic():
                    if entreprise.pk is None:
                        entreprise.save()
                    prospection = Prospection.objects.create(
                        eleve=eleve,
                        entreprise=entreprise,
                        statut=donnees["statut"],
                        type_contrat=donnees["type_contrat"],
                        notes=donnees.get("notes", ""),
                        source=donnees.get("source", ""),
                        date_relance=donnees.get("date_relance"),
                        date_candidature=donnees.get("date_candidature"),
                        date_mise_en_attente=donnees.get("date_mise_en_attente"),
                        date_entretien=date_entretien,
                        date_refus=donnees.get("date_refus"),
                        date_acceptation=donnees.get("date_acceptation"),
                    )
                    champ_date = {
                        Statut.A_RELANCER: prospection.date_relance,
                        Statut.CANDIDATURE_ENVOYEE: prospection.date_candidature,
                        Statut.EN_ATTENTE: prospection.date_mise_en_attente,
                        Statut.ENTRETIEN_PROGRAMME: date_entretien.date() if date_entretien else None,
                        Statut.REFUS: prospection.date_refus,
                        Statut.ACCEPTE: prospection.date_acceptation,
                    }.get(prospection.statut)
                    HistoriqueStatut.objects.create(
                        prospection=prospection,
                        ancien_statut="",
                        nouveau_statut=prospection.statut,
                        auteur=request.user,
                        date_associee=champ_date,
                    )
                    log_action(
                        JournalAction.Action.ACTION_STAFF_ELEVE,
                        utilisateur=request.user,
                        cible=prospection,
                        details={
                            "prospection_id": prospection.pk,
                            "eleve_id": eleve.pk,
                            "action": "ajout_prospection",
                        },
                        request=request,
                    )
            except IntegrityError:
                form.add_error("entreprise_nom", "Cette entreprise fait déjà l'objet d'une prospection pour cet élève.")
                return _rendre_detail_eleve(request, eleve, form, entreprise_form)
            verifier_et_attribuer_badges(eleve)
            return redirect("staff:detail_eleve", pk=eleve.pk)
    else:
        form = AjoutProspectionStaffForm()
        entreprise_form = EntrepriseForm()
    return _rendre_detail_eleve(request, eleve, form, entreprise_form)
