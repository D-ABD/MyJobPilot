"""Tableau de bord et actions staff sur les élèves de leur périmètre."""
from datetime import datetime, time

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comptes.models import Centre, JournalAction, Utilisateur
from comptes.notifications import notifier_ajout_prospection
from comptes.scope_utils import centres_du_superviseur, superviser_eleve, verifier_superviseur
from comptes.utils import log_action
from entreprises.forms import EntrepriseForm
from entreprises.models import Commentaire, HistoriqueStatut, Prospection, Statut

from .forms import AjoutProspectionStaffForm, ChangementCentreFormStaff


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
    queryset = (
        Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE, centre_id__in=centres_ids)
        .select_related("centre", "formation")
        .annotate(nombre_prospections=Count("prospections", distinct=True))
    )

    recherche = request.GET.get("q", "").strip()
    if recherche:
        queryset = queryset.filter(
            Q(username__icontains=recherche)
            | Q(first_name__icontains=recherche)
            | Q(last_name__icontains=recherche)
            | Q(email__icontains=recherche)
        )

    centre_selectionne = request.GET.get("centre", "")
    if centre_selectionne:
        if not centre_selectionne.isdigit() or int(centre_selectionne) not in centres_ids:
            queryset = queryset.none()
        else:
            queryset = queryset.filter(centre_id=int(centre_selectionne))

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
    stats = [
        {
            "centre": centre,
            "nombre": Utilisateur.objects.filter(
                role=Utilisateur.Role.ELEVE,
                centre_id=centre.pk,
                centre_id__in=centres_ids,
            ).count(),
        }
        for centre in centres
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
        "stats_par_centre": stats,
        "total_count": queryset.count(),
        "filtre_q": recherche,
        "filtre_centre": centre_selectionne,
        "filtre_is_valide": validation_selectionnee,
        "filtre_tri": tri,
        "filtre_ordre": ordre,
        "url_reset": request.path,
        "pagination_query": pagination_params.urlencode(),
        "tri_urls": tri_urls,
    }
    return render(request, "staff/dashboard.html", contexte)


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


def _rendre_detail_eleve(request, eleve, prospection_form=None, entreprise_form=None):
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
    return render(
        request,
        "staff/detail_eleve.html",
        {
            "eleve": eleve,
            "prospections": prospections,
            "prospection_form": prospection_form if prospection_form is not None else AjoutProspectionStaffForm(),
            "entreprise_form": entreprise_form if entreprise_form is not None else EntrepriseForm(),
        },
    )


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
        {"eleve": eleve, "form": form},
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
            notifier_ajout_prospection(prospection, request.user)
            return redirect("staff:detail_eleve", pk=eleve.pk)
    else:
        form = AjoutProspectionStaffForm()
        entreprise_form = EntrepriseForm()
    return _rendre_detail_eleve(request, eleve, form, entreprise_form)
