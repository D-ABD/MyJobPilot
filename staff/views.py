"""Tableau de bord en lecture seule du périmètre superviseur."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from comptes.models import Centre, Utilisateur
from comptes.scope_utils import centres_du_superviseur, superviser_eleve, verifier_superviseur
from entreprises.models import Entreprise


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
        .annotate(nombre_entreprises=Count("entreprises", distinct=True))
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
    """Affiche en lecture seule un élève et ses entreprises dans le scope."""
    verifier_superviseur(request)
    eleve = get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.ELEVE)
    if not superviser_eleve(request.user, eleve):
        raise PermissionDenied
    entreprises = Entreprise.objects.filter(eleve=eleve).order_by("-date_modification")
    return render(
        request,
        "staff/detail_eleve.html",
        {"eleve": eleve, "entreprises": entreprises},
    )
