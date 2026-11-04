"""Tableau de bord élève et gestion isolée des prospections."""
from datetime import datetime, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comptes.models import JournalAction, Utilisateur
from comptes.notifications import notifier_ajout_prospection, notifier_changement_statut
from comptes.utils import log_action
from core.filters import FiltreMixin

from .forms import ChangementStatutForm, EntrepriseForm, ProspectionForm
from .models import Entreprise, HistoriqueStatut, Prospection, Statut


NOMBRE_PAR_PAGE = 25
CHAMPS_DATE_STATUT = {
    Statut.A_RELANCER: "date_relance",
    Statut.CANDIDATURE_ENVOYEE: "date_candidature",
    Statut.EN_ATTENTE: "date_mise_en_attente",
    Statut.ENTRETIEN_PROGRAMME: "date_entretien",
    Statut.REFUS: "date_refus",
    Statut.ACCEPTE: "date_acceptation",
}


def _verifier_eleve(request):
    if request.user.role != Utilisateur.Role.ELEVE:
        raise PermissionDenied


def _prospection_eleve(request, pk):
    return get_object_or_404(
        Prospection.objects.select_related("entreprise"),
        pk=pk,
        eleve=request.user,
    )


def _rendre_formulaire_prospection(request, form, entreprise_form, titre, prospection=None):
    return render(
        request,
        "entreprises/entreprise_form.html",
        {
            "form": form,
            "entreprise_form": entreprise_form,
            "titre": titre,
            "prospection": prospection,
            "allow_new_entreprise": prospection is None,
        },
    )


def _datetime_entretien(date_entretien):
    if date_entretien is None:
        return None
    return timezone.make_aware(
        datetime.combine(date_entretien, time.min),
        timezone.get_current_timezone(),
    )


def _valeur_date_associee(prospection, statut):
    champ = CHAMPS_DATE_STATUT.get(statut)
    if champ is None:
        return None
    valeur = getattr(prospection, champ)
    return valeur.date() if champ == "date_entretien" and valeur else valeur


class FiltresDashboard(FiltreMixin):
    """Expose le mixin commun au tableau de bord élève."""


@login_required
def dashboard_eleve(request):
    _verifier_eleve(request)
    queryset = Prospection.objects.filter(eleve=request.user).select_related("entreprise")
    filtreur = FiltresDashboard()
    resultats = filtreur.apply_filters(queryset, request.GET)
    page_obj = Paginator(resultats, NOMBRE_PAR_PAGE).get_page(request.GET.get("page"))

    stats_par_statut = [
        {
            "code": code,
            "libelle": libelle,
            "nombre": queryset.filter(statut=code).count(),
        }
        for code, libelle in Statut.choices
    ]
    parametres_pagination = request.GET.copy()
    parametres_pagination.pop("page", None)
    pagination_query = parametres_pagination.urlencode()

    tri_urls = {}
    for champ in filtreur.CHAMPS_TRIABLES:
        parametres_tri = request.GET.copy()
        est_actif = parametres_tri.get("tri", "-date_modification").lstrip("-") == champ
        ordre_actuel = parametres_tri.get("ordre", "desc")
        prochain_ordre = "desc" if est_actif and ordre_actuel == "asc" else "asc"
        parametres_tri["tri"] = champ
        parametres_tri["ordre"] = prochain_ordre
        tri_urls[champ] = f"{request.path}?{parametres_tri.urlencode()}"

    contexte = {
        **filtreur.get_contexte_filtres(request),
        "prospections": page_obj.object_list,
        "page_obj": page_obj,
        "total_count": resultats.count(),
        "stats_par_statut": stats_par_statut,
        "statuts": Statut.choices,
        "pagination_query": pagination_query,
        "tri_urls": tri_urls,
    }
    return render(request, "entreprises/dashboard.html", contexte)


@login_required
def recherche_entreprises(request):
    """Recherche des entreprises sans exposer de données de prospection."""
    recherche = request.GET.get("q", "").strip()
    resultats = []
    if recherche:
        resultats = list(
            Entreprise.objects.filter(nom__icontains=recherche)
            .order_by("nom")
            .values("id", "nom", "ville")[:10]
        )
    return JsonResponse(resultats, safe=False)


@login_required
def entreprise_create(request):
    _verifier_eleve(request)
    if request.method == "POST":
        form = ProspectionForm(request.POST)
        entreprise_form = EntrepriseForm(request.POST)
        if form.is_valid():
            entreprise = form.cleaned_data.get("entreprise_id")
            if entreprise is None and not entreprise_form.is_valid():
                return _rendre_formulaire_prospection(
                    request, form, entreprise_form, "Nouvelle prospection"
                )
            if entreprise is None:
                nom_autocomplete = form.cleaned_data["entreprise_nom"].strip()
                if entreprise_form.cleaned_data["nom"].strip().casefold() != nom_autocomplete.casefold():
                    form.add_error(
                        "entreprise_nom",
                        "Le nom de l'entreprise doit correspondre au nom renseigné dans ses informations.",
                    )
                    return _rendre_formulaire_prospection(
                        request, form, entreprise_form, "Nouvelle prospection"
                    )
                entreprise = entreprise_form.save()

            prospection_existante = Prospection.objects.filter(
                eleve=request.user, entreprise=entreprise
            ).first()
            if prospection_existante:
                messages.info(request, "Vous avez déjà une prospection pour cette entreprise.")
                return redirect("entreprises:detail", pk=prospection_existante.pk)

            donnees = form.cleaned_data
            try:
                with transaction.atomic():
                    if entreprise.pk is None:
                        entreprise.save()
                    prospection = _creer_prospection(request.user, entreprise, donnees)
                    HistoriqueStatut.objects.create(
                        prospection=prospection,
                        ancien_statut="",
                        nouveau_statut=prospection.statut,
                        auteur=request.user,
                        date_associee=_valeur_date_associee(prospection, prospection.statut),
                    )
            except IntegrityError:
                form.add_error(
                    "entreprise_nom",
                    "Cette entreprise fait déjà l'objet d'une prospection pour votre compte.",
                )
                return _rendre_formulaire_prospection(
                    request, form, entreprise_form, "Nouvelle prospection"
                )
            notifier_ajout_prospection(prospection, request.user)
            return redirect("entreprises:detail", pk=prospection.pk)
    else:
        form = ProspectionForm()
        entreprise_form = EntrepriseForm()
    return _rendre_formulaire_prospection(request, form, entreprise_form, "Nouvelle prospection")


def _creer_prospection(eleve, entreprise, donnees):
    valeurs = {
        champ: donnees.get(champ)
        for champ in (
            "statut", "notes", "source", "date_relance", "date_candidature",
            "date_mise_en_attente", "date_refus", "date_acceptation",
        )
    }
    valeurs["date_entretien"] = _datetime_entretien(donnees.get("date_entretien"))
    return Prospection.objects.create(eleve=eleve, entreprise=entreprise, **valeurs)


def _enregistrer_formulaire_prospection(prospection, donnees, request):
    ancien_statut = prospection.statut
    nouveau_statut = donnees["statut"]
    prospection.statut = nouveau_statut
    for champ in (
        "notes", "source", "date_relance", "date_candidature", "date_mise_en_attente",
        "date_refus", "date_acceptation",
    ):
        setattr(prospection, champ, donnees.get(champ))
    prospection.date_entretien = _datetime_entretien(donnees.get("date_entretien"))
    prospection.save()

    if ancien_statut != nouveau_statut:
        HistoriqueStatut.objects.create(
            prospection=prospection,
            ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut,
            auteur=prospection.eleve,
            date_associee=_valeur_date_associee(prospection, nouveau_statut),
        )
        log_action(
            JournalAction.Action.CHANGEMENT_STATUT,
            utilisateur=prospection.eleve,
            cible=prospection,
            details={
                "prospection_id": prospection.pk,
                "ancien_statut": ancien_statut,
                "nouveau_statut": nouveau_statut,
            },
            request=request,
        )


@login_required
def entreprise_update(request, pk):
    _verifier_eleve(request)
    prospection = _prospection_eleve(request, pk)
    if request.method == "POST":
        form = ProspectionForm(request.POST, prospection=prospection)
        if form.is_valid():
            entreprise_selectionnee = form.cleaned_data.get("entreprise_id")
            if entreprise_selectionnee != prospection.entreprise:
                form.add_error("entreprise_nom", "L'entreprise d'une prospection existante ne peut pas être remplacée ici.")
            else:
                with transaction.atomic():
                    _enregistrer_formulaire_prospection(prospection, form.cleaned_data, request)
                return redirect("entreprises:detail", pk=prospection.pk)
    else:
        form = ProspectionForm(prospection=prospection)
    return _rendre_formulaire_prospection(
        request,
        form,
        EntrepriseForm(instance=prospection.entreprise),
        f"Modifier la prospection de {prospection.entreprise.nom}",
        prospection=prospection,
    )


@login_required
def entreprise_delete(request, pk):
    _verifier_eleve(request)
    prospection = _prospection_eleve(request, pk)
    if request.method == "POST":
        prospection.delete()
        return redirect("entreprises:dashboard")
    return render(request, "entreprises/entreprise_confirm_delete.html", {"prospection": prospection})


@login_required
def entreprise_detail(request, pk):
    _verifier_eleve(request)
    prospection = _prospection_eleve(request, pk)
    historique = prospection.historique.select_related("auteur").order_by("-date_changement")
    return render(
        request,
        "entreprises/entreprise_detail.html",
        {"prospection": prospection, "historique": historique},
    )


@login_required
def entreprise_changer_statut(request, pk):
    _verifier_eleve(request)
    prospection = _prospection_eleve(request, pk)
    if request.method == "POST":
        form = ChangementStatutForm(request.POST)
        if form.is_valid():
            ancien_statut = prospection.statut
            nouveau_statut = form.cleaned_data["nouveau_statut"]
            date_associee = form.cleaned_data.get("date_associee")
            with transaction.atomic():
                prospection.statut = nouveau_statut
                champ_date = CHAMPS_DATE_STATUT.get(nouveau_statut)
                if champ_date:
                    valeur_date = date_associee
                    if champ_date == "date_entretien" and date_associee:
                        valeur_date = _datetime_entretien(date_associee)
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
            return redirect("entreprises:detail", pk=prospection.pk)
    else:
        form = ChangementStatutForm(initial={"nouveau_statut": prospection.statut})
    return render(
        request,
        "entreprises/entreprise_form.html",
        {
            "form": form,
            "entreprise_form": None,
            "titre": f"Changer le statut de {prospection.entreprise.nom}",
            "prospection": prospection,
            "allow_new_entreprise": False,
            "changement_statut": True,
        },
    )
