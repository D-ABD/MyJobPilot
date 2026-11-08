"""Administration en lecture seule des offres enregistrées."""
from django.contrib import admin

from .models import Badge, BadgeObtenu, OffreEnregistree


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = (
        "slug", "nom", "categorie", "type_condition", "seuil",
        "valeur_points", "ordre_affichage", "est_actif",
    )
    list_filter = ("categorie", "type_condition", "est_actif")
    list_editable = ("ordre_affichage", "est_actif")
    search_fields = ("nom", "slug")

    def get_readonly_fields(self, request, obj=None):
        return ("slug",) if obj else ()


@admin.register(BadgeObtenu)
class BadgeObtenuAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "badge", "date_obtention")
    list_filter = ("badge__categorie",)
    search_fields = ("utilisateur__email", "badge__nom")
    readonly_fields = ("date_obtention",)
    raw_id_fields = ("utilisateur", "badge")


@admin.register(OffreEnregistree)
class OffreEnregistreeAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "titre", "entreprise", "date_enregistrement")
    search_fields = ("utilisateur__username", "titre", "entreprise", "offre_id_lba")
    readonly_fields = (
        "utilisateur", "offre_id_lba", "titre", "entreprise", "ville", "url",
        "date_publication", "date_enregistrement",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
