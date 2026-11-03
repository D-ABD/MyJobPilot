"""Administration du référentiel et des prospections."""
from django.contrib import admin

from comptes.models import Utilisateur

from .models import Commentaire, Entreprise, HistoriqueStatut, Prospection


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display = ("nom", "secteur", "ville", "contact_nom", "date_creation")
    search_fields = ("nom", "secteur", "ville", "contact_nom", "contact_email")
    readonly_fields = ("date_creation",)


@admin.register(Prospection)
class ProspectionAdmin(admin.ModelAdmin):
    list_display = ("eleve", "entreprise", "statut", "date_creation", "date_modification")
    list_filter = ("statut", "date_modification")
    search_fields = ("eleve__username", "entreprise__nom", "entreprise__ville")
    readonly_fields = ("date_creation", "date_modification")


@admin.register(HistoriqueStatut)
class HistoriqueStatutAdmin(admin.ModelAdmin):
    list_display = ("prospection", "ancien_statut", "nouveau_statut", "auteur", "date_changement")
    list_filter = ("nouveau_statut", "date_changement")
    search_fields = ("prospection__entreprise__nom", "prospection__eleve__username", "auteur__username")
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


@admin.register(Commentaire)
class CommentaireAdmin(admin.ModelAdmin):
    list_display = ("prospection", "auteur", "date")
    list_filter = ("date",)
    search_fields = (
        "auteur__username",
        "prospection__eleve__username",
        "prospection__entreprise__nom",
        "contenu",
    )
    readonly_fields = tuple(field.name for field in Commentaire._meta.fields)

    def has_add_permission(self, request):
        return False
