"""Tableau de bord élève et gestion des entreprises de prospection."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from comptes.models import JournalAction, Utilisateur
from comptes.utils import log_action
from core.filters import FiltreMixin

from .forms import ChangementStatutForm, EntrepriseForm
from .models import Entreprise, HistoriqueStatut, Statut


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


def _entreprise_eleve(request, pk):
    return get_object_or_404(Entreprise, pk=pk, eleve=request.user)


class FiltresDashboard(FiltreMixin):
    """Expose le mixin commun au tableau de bord élève."""


@login_required
def dashboard_eleve(request):
    _verifier_eleve(request)
    queryset = Entreprise.objects.filter(eleve=request.user)
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
        "entreprises": page_obj.object_list,
        "page_obj": page_obj,
        "total_count": resultats.count(),
        "stats_par_statut": stats_par_statut,
        "statuts": Statut.choices,
        "pagination_query": pagination_query,
        "tri_urls": tri_urls,
    }
    return render(request, "entreprises/dashboard.html", contexte)


@login_required
def entreprise_create(request):
    _verifier_eleve(request)
    if request.method == "POST":
        form = EntrepriseForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                entreprise = form.save(commit=False)
                entreprise.eleve = request.user
                entreprise.statut = Statut.A_CONTACTER
                entreprise.save()
                HistoriqueStatut.objects.create(
                    entreprise=entreprise,
                    ancien_statut="",
                    nouveau_statut=Statut.A_CONTACTER,
                    auteur=request.user,
                )
            return redirect("entreprises:detail", pk=entreprise.pk)
    else:
        form = EntrepriseForm()
    return render(request, "entreprises/entreprise_form.html", {"form": form, "titre": "Nouvelle entreprise"})


@login_required
def entreprise_update(request, pk):
    _verifier_eleve(request)
    entreprise = _entreprise_eleve(request, pk)
    if request.method == "POST":
        form = EntrepriseForm(request.POST, instance=entreprise)
        if form.is_valid():
            form.save()
            return redirect("entreprises:detail", pk=entreprise.pk)
    else:
        form = EntrepriseForm(instance=entreprise)
    return render(
        request,
        "entreprises/entreprise_form.html",
        {"form": form, "titre": f"Modifier {entreprise.nom}", "entreprise": entreprise},
    )


@login_required
def entreprise_delete(request, pk):
    _verifier_eleve(request)
    entreprise = _entreprise_eleve(request, pk)
    if request.method == "POST":
        entreprise.delete()
        return redirect("entreprises:dashboard")
    return render(request, "entreprises/entreprise_confirm_delete.html", {"entreprise": entreprise})


@login_required
def entreprise_detail(request, pk):
    _verifier_eleve(request)
    entreprise = _entreprise_eleve(request, pk)
    historique = entreprise.historique.select_related("auteur").order_by("-date_changement")
    return render(
        request,
        "entreprises/entreprise_detail.html",
        {"entreprise": entreprise, "historique": historique},
    )


@login_required
def entreprise_changer_statut(request, pk):
    _verifier_eleve(request)
    entreprise = _entreprise_eleve(request, pk)
    if request.method == "POST":
        form = ChangementStatutForm(request.POST)
        if form.is_valid():
            ancien_statut = entreprise.statut
            nouveau_statut = form.cleaned_data["nouveau_statut"]
            date_associee = form.cleaned_data.get("date_associee")
            with transaction.atomic():
                entreprise.statut = nouveau_statut
                champ_date = CHAMPS_DATE_STATUT.get(nouveau_statut)
                if champ_date:
                    setattr(entreprise, champ_date, date_associee)
                entreprise.save()
                HistoriqueStatut.objects.create(
                    entreprise=entreprise,
                    ancien_statut=ancien_statut,
                    nouveau_statut=nouveau_statut,
                    auteur=request.user,
                    commentaire=form.cleaned_data.get("commentaire", ""),
                    date_associee=date_associee,
                )
                log_action(
                    JournalAction.Action.CHANGEMENT_STATUT,
                    utilisateur=request.user,
                    cible=entreprise,
                    details={
                        "entreprise_id": entreprise.pk,
                        "ancien_statut": ancien_statut,
                        "nouveau_statut": nouveau_statut,
                    },
                    request=request,
                )
            return redirect("entreprises:detail", pk=entreprise.pk)
    else:
        form = ChangementStatutForm(initial={"nouveau_statut": entreprise.statut})
    return render(
        request,
        "entreprises/entreprise_form.html",
        {"form": form, "titre": f"Changer le statut de {entreprise.nom}", "entreprise": entreprise},
    )
