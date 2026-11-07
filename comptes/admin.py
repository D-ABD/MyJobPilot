"""Administration des référentiels, comptes, consentements et journaux."""
import logging

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.utils.html import format_html

from .models import Centre, ConsentementRGPD, Formation, JournalAction, Notification, ScopeSuperviseur, TypeNotification, Utilisateur
from .emails import envoyer_email_refus, envoyer_email_validation
from .notifications import creer_notification
from .utils import invalidate_user_sessions, log_action

logger = logging.getLogger("comptes")


@admin.register(Centre)
class CentreAdmin(admin.ModelAdmin):
    list_display = ("nom", "departement")
    search_fields = ("nom", "departement")
    ordering = ("nom",)


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = ("nom", "centre")
    list_filter = ("centre",)
    search_fields = ("nom", "centre__nom")
    ordering = ("centre__nom", "nom")


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Parcours", {"fields": ("role", "centre", "formation", "is_valide", "date_validation", "valide_par", "motif_refus")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Parcours", {"fields": ("role", "centre", "formation", "is_valide")}),
    )
    list_display = ("username", "email", "role", "centre", "formation", "is_valide", "is_active", "voir_fiche_staff")
    list_filter = ("role", "centre", "is_valide", "is_active")
    actions = ("valider_comptes", "refuser_comptes", "desactiver_comptes")

    def voir_fiche_staff(self, obj):
        if obj.role == "eleve":
            return format_html('<a href="/staff/eleves/{}/">Fiche staff</a>', obj.pk)
        return "—"

    voir_fiche_staff.short_description = "Fiche staff"

    def save_model(self, request, obj, form, change):
        if not change and obj.role in {Utilisateur.Role.ADMIN, Utilisateur.Role.SUPERVISEUR}:
            obj.is_valide = True
        super().save_model(request, obj, form, change)

    @admin.action(description="Valider les comptes sélectionnés")
    def valider_comptes(self, request, queryset):
        for utilisateur in queryset:
            utilisateur.is_valide = True
            utilisateur.date_validation = timezone.now()
            utilisateur.valide_par = request.user
            utilisateur.motif_refus = ""
            utilisateur.save(update_fields=("is_valide", "date_validation", "valide_par", "motif_refus"))
            log_action(
                JournalAction.Action.COMPTE_VALIDE,
                utilisateur=request.user,
                cible=utilisateur,
                request=request,
            )
            creer_notification(
                utilisateur, TypeNotification.COMPTE_VALIDE,
                "Votre compte a été validé", "/dashboard/",
            )
            try:
                envoyer_email_validation(utilisateur)
            except Exception:
                logger.exception(
                    "Échec de l'envoi de l'email de validation pour %s",
                    utilisateur.username,
                )

    @admin.action(description="Refuser les comptes sélectionnés")
    def refuser_comptes(self, request, queryset):
        comptes_refusables = queryset.exclude(motif_refus="")
        nombre_refuses = 0
        for utilisateur in comptes_refusables:
            utilisateur.is_valide = False
            utilisateur.date_validation = None
            utilisateur.valide_par = request.user
            utilisateur.save(update_fields=("is_valide", "date_validation", "valide_par"))
            log_action(
                JournalAction.Action.COMPTE_REFUSE,
                utilisateur=request.user,
                cible=utilisateur,
                details={"motif_refus": utilisateur.motif_refus},
                request=request,
            )
            creer_notification(
                utilisateur, TypeNotification.COMPTE_REFUSE,
                "Votre compte a été refusé", "/en-attente/",
            )
            try:
                envoyer_email_refus(utilisateur, utilisateur.motif_refus)
            except Exception:
                logger.exception(
                    "Échec de l'envoi de l'email de refus pour %s",
                    utilisateur.username,
                )
            nombre_refuses += 1
        nombre_sans_motif = queryset.count() - nombre_refuses
        if nombre_sans_motif:
            self.message_user(
                request,
                f"{nombre_sans_motif} compte(s) non refusé(s) : renseignez le motif de refus avant de relancer l'action.",
                level=messages.WARNING,
            )

    @admin.action(description="Désactiver les comptes sélectionnés")
    def desactiver_comptes(self, request, queryset):
        for utilisateur in queryset:
            utilisateur.is_active = False
            utilisateur.save(update_fields=("is_active",))
            sessions_supprimees = invalidate_user_sessions(utilisateur)
            log_action(
                JournalAction.Action.COMPTE_DESACTIVE,
                utilisateur=request.user,
                cible=utilisateur,
                details={"sessions_supprimees": sessions_supprimees},
                request=request,
            )


@admin.register(JournalAction)
class JournalActionAdmin(admin.ModelAdmin):
    list_display = ("date", "action", "utilisateur", "cible_type", "cible_id", "ip")
    list_filter = ("action", "date")
    search_fields = ("utilisateur__username", "cible_type", "cible_id", "ip")
    readonly_fields = ("utilisateur", "action", "cible_type", "cible_id", "details", "ip", "user_agent", "date")
    ordering = ("-date",)

    def has_add_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and (
            request.user.is_superuser or getattr(request.user, "role", None) == Utilisateur.Role.ADMIN
        )

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConsentementRGPD)
class ConsentementRGPDAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "version_politique", "date_consentement", "ip")
    list_filter = ("version_politique", "date_consentement")
    search_fields = ("utilisateur__username",)
    readonly_fields = ("utilisateur", "version_politique", "date_consentement", "ip", "user_agent")

    def has_add_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and (
            request.user.is_superuser or getattr(request.user, "role", None) == Utilisateur.Role.ADMIN
        )

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScopeSuperviseur)
class ScopeSuperviseurAdmin(admin.ModelAdmin):
    list_display = ("superviseur", "centre", "is_active", "date_creation", "date_desactivation")
    list_filter = ("is_active", "centre")
    search_fields = ("superviseur__username", "centre__nom")
    readonly_fields = ("date_creation", "date_desactivation", "cree_par", "is_active")
    actions = ("desactiver_scopes",)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return
        scope, _ = ScopeSuperviseur.creer(
            superviseur=obj.superviseur,
            centre=obj.centre,
            auteur=request.user,
        )
        obj.pk = scope.pk
        obj._state.adding = False
        obj._state.db = scope._state.db
        obj.date_creation = scope.date_creation
        obj.cree_par = scope.cree_par

    @admin.action(description="Désactiver les scopes sélectionnés")
    def desactiver_scopes(self, request, queryset):
        nombre = 0
        for scope in queryset.filter(is_active=True):
            scope.desactiver(auteur=request.user)
            nombre += 1
        self.message_user(request, f"{nombre} scope(s) désactivé(s).")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("destinataire", "type", "message", "lu", "date_creation")
    list_filter = ("type", "lu", "date_creation")
    search_fields = ("destinataire__username", "message")
    readonly_fields = ("date_creation",)
