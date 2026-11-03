from django.conf import settings
from django.db import models


class TypeDemande(models.TextChoices):
    ACCES = "acces", "Accès"
    RECTIFICATION = "rectification", "Rectification"
    EFFACEMENT = "effacement", "Effacement"
    PORTABILITE = "portabilite", "Portabilité"
    OPPOSITION = "opposition", "Opposition"


class StatutDemande(models.TextChoices):
    RECUE = "recue", "Reçue"
    EN_COURS = "en_cours", "En cours"
    TRAITEE = "traitee", "Traitée"
    REFUSEE = "refusee", "Refusée"


class DemandeRGPD(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="demandes_rgpd",
        on_delete=models.CASCADE, verbose_name="utilisateur",
    )
    type = models.CharField("type", max_length=20, choices=TypeDemande.choices)
    statut = models.CharField(
        "statut", max_length=20, choices=StatutDemande.choices,
        default=StatutDemande.RECUE,
    )
    description = models.TextField("description", blank=True)
    date_demande = models.DateTimeField("date de la demande", auto_now_add=True)
    date_traitement = models.DateTimeField("date de traitement", null=True, blank=True)
    motif_refus = models.TextField("motif du refus", blank=True)
    traitee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="demandes_traitees",
        null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name="traitée par",
    )

    class Meta:
        ordering = ["-date_demande"]
        indexes = [
            models.Index(fields=["utilisateur", "-date_demande"]),
            models.Index(fields=["statut", "-date_demande"]),
        ]
        verbose_name = "demande RGPD"
        verbose_name_plural = "demandes RGPD"

    def __str__(self):
        return f"{self.get_type_display()} — {self.utilisateur.username}"
