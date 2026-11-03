from django.contrib import admin

from .models import DemandeRGPD


@admin.register(DemandeRGPD)
class DemandeRGPDAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "type", "statut", "date_demande", "date_traitement", "traitee_par")
    list_filter = ("type", "statut", "date_demande")
    search_fields = ("utilisateur__username", "utilisateur__email", "description")
    readonly_fields = ("utilisateur", "type", "description", "date_demande", "date_traitement", "traitee_par")
