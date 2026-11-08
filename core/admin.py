"""Administration en lecture seule des offres enregistrées."""
from django.contrib import admin

from .models import OffreEnregistree


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
