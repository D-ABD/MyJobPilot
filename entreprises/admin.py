"""Administration des entreprises et lecture du journal des statuts."""
from django.contrib import admin

from comptes.models import Utilisateur

from .models import Entreprise, HistoriqueStatut


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display = ("nom", "eleve", "statut", "date_modification")
    list_filter = ("statut", "date_modification")
    search_fields = ("nom", "eleve__username", "ville", "contact_email")
    readonly_fields = ("date_creation", "date_modification")


@admin.register(HistoriqueStatut)
class HistoriqueStatutAdmin(admin.ModelAdmin):
    list_display = ("entreprise", "ancien_statut", "nouveau_statut", "auteur", "date_changement")
    list_filter = ("nouveau_statut", "date_changement")
    search_fields = ("entreprise__nom", "auteur__username")
    readonly_fields = tuple(field.name for field in HistoriqueStatut._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and (
            request.user.is_superuser or getattr(request.user, "role", None) == Utilisateur.Role.ADMIN
        )
