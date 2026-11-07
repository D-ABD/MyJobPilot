"""Modèles du socle : référentiels, comptes, consentement et journal."""
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Centre(models.Model):
    nom = models.CharField("nom", max_length=150, unique=True)
    departement = models.CharField("département", max_length=100)

    class Meta:
        ordering = ["nom"]
        verbose_name = "centre"
        verbose_name_plural = "centres"

    def __str__(self):
        return f"{self.nom} — {self.departement}"


class Formation(models.Model):
    centre = models.ForeignKey(Centre, on_delete=models.PROTECT, related_name="formations", verbose_name="centre")
    nom = models.CharField("nom", max_length=150)

    class Meta:
        ordering = ["centre__nom", "nom"]
        verbose_name = "formation"
        verbose_name_plural = "formations"
        constraints = [
            models.UniqueConstraint(fields=["centre", "nom"], name="unique_formation_par_centre"),
        ]

    def __str__(self):
        return f"{self.nom} — {self.centre.nom}"


class ConsentementRGPD(models.Model):
    """Consentement RGPD recueilli auprès de l'utilisateur (v8.1 §3, §11)."""

    utilisateur = models.OneToOneField(
        "comptes.Utilisateur",
        on_delete=models.CASCADE,
        related_name="consentement",
        verbose_name="utilisateur",
    )
    version_politique = models.CharField("version de la politique", max_length=20, default="1.0")
    date_consentement = models.DateTimeField("date du consentement", auto_now_add=True)
    ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    user_agent = models.TextField("user-agent", blank=True)

    class Meta:
        verbose_name = "consentement RGPD"
        verbose_name_plural = "consentements RGPD"
        ordering = ["-date_consentement"]

    def __str__(self):
        return f"Consentement de {self.utilisateur.username} ({self.version_politique})"


class GestionnaireUtilisateur(UserManager):
    """Configure les comptes superutilisateurs comme administrateurs MyJobPilot."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_valide", True)
        extra_fields.setdefault("date_validation", timezone.now())
        return super().create_superuser(username, email, password, **extra_fields)


class Utilisateur(AbstractUser):
    class Role(models.TextChoices):
        ELEVE = "eleve", "Élève"
        SUPERVISEUR = "superviseur", "Superviseur"
        ADMIN = "admin", "Administrateur"

    role = models.CharField("rôle", max_length=20, choices=Role.choices, default=Role.ELEVE)
    centre = models.ForeignKey(
        Centre,
        on_delete=models.PROTECT,
        related_name="utilisateurs",
        verbose_name="centre",
        null=True,
        blank=True,
    )
    formation = models.ForeignKey(
        Formation,
        on_delete=models.PROTECT,
        related_name="eleves",
        verbose_name="formation",
        null=True,
        blank=True,
    )
    is_valide = models.BooleanField("compte validé", default=False)
    date_validation = models.DateTimeField("date de validation", null=True, blank=True)
    valide_par = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="validations_effectuees",
        verbose_name="validé par",
        null=True,
        blank=True,
    )
    motif_refus = models.TextField("motif du refus", blank=True)
    objects = GestionnaireUtilisateur()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    @property
    def departement(self):
        """Retourne le département du centre associé, ou None."""
        return self.centre.departement if self.centre_id else None

    @property
    def a_consenti_rgpd(self):
        """Indique si un consentement RGPD est enregistré."""
        return hasattr(self, "consentement")

    def clean(self):
        """Vérifie les rattachements obligatoires selon le rôle."""
        super().clean()
        if self.role in {self.Role.ELEVE, self.Role.SUPERVISEUR} and not self.centre_id:
            raise ValidationError({"centre": "Un centre est obligatoire pour ce rôle."})
        if self.role == self.Role.ELEVE and not self.formation_id:
            raise ValidationError({"formation": "Une formation est obligatoire pour un élève."})
        if self.formation_id and self.centre_id and self.formation.centre_id != self.centre_id:
            raise ValidationError({"formation": "La formation doit appartenir au centre sélectionné."})


class JournalAction(models.Model):
    class Action(models.TextChoices):
        LOGIN = "login", "Connexion"
        LOGOUT = "logout", "Déconnexion"
        LOGIN_FAILED = "login_failed", "Échec de connexion"
        INSCRIPTION_SOUMISE = "inscription_soumise", "Inscription soumise"
        COMPTE_VALIDE = "compte_valide", "Compte validé"
        COMPTE_REFUSE = "compte_refuse", "Compte refusé"
        COMPTE_DESACTIVE = "compte_desactive", "Compte désactivé"
        SESSION_INVALIDE = "session_invalidee", "Session invalidée"
        CHANGEMENT_STATUT = "changement_statut", "Changement de statut"
        SCOPE_CREE = "scope_cree", "Scope superviseur créé"
        ACCES_SCOPE_REFUSE = "acces_scope_refuse", "Accès hors périmètre refusé"
        ACTION_STAFF_ELEVE = "action_staff_eleve", "Action staff sur un élève"
        CHANGEMENT_CENTRE = "changement_centre", "Changement de centre"
        DOCUMENT_UPLOAD = "document_upload", "Document téléversé"
        DOCUMENT_DOWNLOAD = "document_download", "Document téléchargé"
        DOCUMENT_SUPPRIME = "document_supprime", "Document supprimé"
        COMMENTAIRE_CREE = "commentaire_cree", "Commentaire créé"
        EXPORT_RGPD = "export_rgpd", "Export RGPD"
        PURGE_RGPD = "purge_rgpd", "Purge RGPD"
        CONSENTEMENT_MODIFIE = "consentement_modifie", "Consentement modifié"
        DEMANDE_RGPD_MAJ = "demande_rgpd_maj", "Demande RGPD mise à jour"
        EXPORT_CSV = "export_csv", "Export CSV"
        IMPORT_CSV = "import_csv", "Import CSV"
        TACHE_CREE = "tache_cree", "Tâche créée"
        TACHE_TERMINEE = "tache_terminee", "Tâche terminée"
        TACHE_SUPPRIMEE = "tache_supprimee", "Tâche supprimée"

    utilisateur = models.ForeignKey(
        "comptes.Utilisateur",
        on_delete=models.SET_NULL,
        related_name="actions_journalisees",
        verbose_name="utilisateur",
        null=True,
        blank=True,
    )
    action = models.CharField("action", max_length=40, choices=Action.choices)
    cible_type = models.CharField("type de cible", max_length=100, blank=True)
    cible_id = models.CharField("identifiant de cible", max_length=100, blank=True)
    details = models.JSONField("détails", default=dict, blank=True)
    ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    user_agent = models.TextField("user-agent", blank=True)
    date = models.DateTimeField("date", auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "action journalisée"
        verbose_name_plural = "journal des actions"

    def __str__(self):
        return f"{self.get_action_display()} — {self.date:%Y-%m-%d %H:%M}"


class ScopeSuperviseur(models.Model):
    """Périmètre actif ou révoqué d'un superviseur sur un centre."""

    superviseur = models.ForeignKey(
        "comptes.Utilisateur",
        related_name="scopes",
        on_delete=models.CASCADE,
    )
    centre = models.ForeignKey(
        Centre,
        related_name="scopes_superviseurs",
        on_delete=models.CASCADE,
    )
    is_active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_desactivation = models.DateTimeField(null=True, blank=True)
    cree_par = models.ForeignKey(
        "comptes.Utilisateur",
        related_name="scopes_crees",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "scope superviseur"
        verbose_name_plural = "scopes superviseurs"
        ordering = ["superviseur__username", "centre__nom"]
        unique_together = [("superviseur", "centre")]
        indexes = [
            models.Index(fields=["superviseur", "is_active"]),
            models.Index(fields=["centre", "is_active"]),
        ]

    def __str__(self):
        return f"{self.superviseur.username} → {self.centre.nom}"

    @classmethod
    def creer(cls, superviseur, centre, auteur=None):
        """Crée un scope unique et journalise sa création une seule fois."""
        scope, created = cls.objects.get_or_create(
            superviseur=superviseur,
            centre=centre,
            defaults={"cree_par": auteur, "is_active": True},
        )
        if created:
            JournalAction.objects.create(
                utilisateur=auteur,
                action=JournalAction.Action.SCOPE_CREE,
                cible_type="ScopeSuperviseur",
                cible_id=str(scope.pk),
                details={
                    "superviseur_id": superviseur.pk,
                    "centre_id": centre.pk,
                },
            )
        return scope, created

    def desactiver(self, auteur=None):
        """Désactive le scope et journalise sa révocation une seule fois."""
        if not self.is_active:
            return
        self.is_active = False
        self.date_desactivation = timezone.now()
        self.save(update_fields=["is_active", "date_desactivation"])
        JournalAction.objects.create(
            utilisateur=auteur,
            action=JournalAction.Action.ACCES_SCOPE_REFUSE,
            cible_type="ScopeSuperviseur",
            cible_id=str(self.pk),
            details={
                "superviseur_id": self.superviseur_id,
                "centre_id": self.centre_id,
                "action": "desactivation",
            },
        )


class TypeNotification(models.TextChoices):
    COMPTE_VALIDE = "compte_valide", "Compte validé"
    COMPTE_REFUSE = "compte_refuse", "Compte refusé"
    STATUT_CHANGE = "statut_change", "Statut de prospection modifié"
    COMMENTAIRE = "commentaire", "Nouveau commentaire"
    DOCUMENT = "document", "Nouveau document"
    AJOUT_PROSPECTION = "ajout_prospection", "Nouvelle prospection"


class Notification(models.Model):
    destinataire = models.ForeignKey(
        "comptes.Utilisateur",
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="destinataire",
    )
    type = models.CharField(
        "type",
        max_length=30,
        choices=TypeNotification.choices,
    )
    message = models.CharField("message", max_length=255)
    lien = models.CharField("lien", max_length=255, blank=True)
    lu = models.BooleanField("lu", default=False)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]
        indexes = [
            models.Index(fields=["destinataire", "lu", "-date_creation"]),
        ]
        verbose_name = "notification"
        verbose_name_plural = "notifications"

    def __str__(self):
        return f"{self.destinataire.username} — {self.message[:60]}"
