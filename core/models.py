"""Modèles transverses de l'application."""
from django.conf import settings
from django.db import models


class Tache(models.Model):
    class Statut(models.TextChoices):
        A_FAIRE = "a_faire", "À faire"
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"

    titre = models.CharField("titre", max_length=200)
    description = models.TextField("description", blank=True)
    date_echeance = models.DateField("date d'échéance", null=True, blank=True)
    statut = models.CharField(
        "statut", max_length=20, choices=Statut.choices, default=Statut.A_FAIRE,
    )
    createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="taches_creees",
        on_delete=models.CASCADE,
    )
    assigne_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="taches_assignees",
        on_delete=models.CASCADE,
    )
    prospection = models.ForeignKey(
        "entreprises.Prospection",
        null=True,
        blank=True,
        related_name="taches",
        on_delete=models.SET_NULL,
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["statut", "date_echeance", "-date_creation"]
        indexes = [
            models.Index(fields=["assigne_a", "statut"]),
            models.Index(fields=["assigne_a", "date_echeance"]),
        ]
        verbose_name = "tâche"
        verbose_name_plural = "tâches"

    def __str__(self):
        return self.titre
