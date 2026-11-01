"""Filtres réutilisables des tableaux de bord."""
from django.db.models import Q


class FiltreMixin:
    """Applique les filtres, la recherche et le tri reçus dans l'URL."""

    CHAMPS_TRIABLES = ["nom", "secteur", "ville", "statut", "date_creation", "date_modification"]

    def apply_filters(self, queryset, params):
        statut = params.get("statut")
        if statut and statut != "tous":
            queryset = queryset.filter(statut=statut)

        date_debut = params.get("date_debut")
        if date_debut:
            queryset = queryset.filter(date_modification__date__gte=date_debut)

        date_fin = params.get("date_fin")
        if date_fin:
            queryset = queryset.filter(date_modification__date__lte=date_fin)

        recherche = params.get("q", "").strip()
        if recherche:
            queryset = queryset.filter(
                Q(nom__icontains=recherche)
                | Q(secteur__icontains=recherche)
                | Q(ville__icontains=recherche)
                | Q(contact_nom__icontains=recherche)
                | Q(contact_email__icontains=recherche)
            )

        tri = params.get("tri", "-date_modification")
        ordre = params.get("ordre", "desc")
        if tri.lstrip("-") in self.CHAMPS_TRIABLES:
            if ordre == "desc" and not tri.startswith("-"):
                tri = f"-{tri}"
            elif ordre == "asc" and tri.startswith("-"):
                tri = tri[1:]
            queryset = queryset.order_by(tri)
        return queryset

    def reset_url(self, request):
        """Retourne le chemin de la page sans les paramètres GET."""
        return request.path

    def get_contexte_filtres(self, request):
        """Fournit aux templates les valeurs actuelles des filtres."""
        return {
            "filtre_statut": request.GET.get("statut", "tous"),
            "filtre_date_debut": request.GET.get("date_debut", ""),
            "filtre_date_fin": request.GET.get("date_fin", ""),
            "filtre_q": request.GET.get("q", ""),
            "filtre_tri": request.GET.get("tri", "-date_modification"),
            "filtre_ordre": request.GET.get("ordre", "desc"),
            "url_reset": self.reset_url(request),
        }
