"""Modèles de documents personnels des élèves."""
from django.conf import settings
from django.db import models


class TypeDocument(models.TextChoices):
    CV = "cv", "CV"
    LETTRE = "lettre", "Lettre de motivation"
    DIPLOME = "diplome", "Diplôme"
    AUTRE = "autre", "Autre"


class DocumentManager(models.Manager):
    """Manager qui évite de charger les données binaires dans les listes."""

    def listing(self):
        """Retourne les documents sans le champ contenu."""
        return self.get_queryset().defer("contenu")


class Document(models.Model):
    eleve = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="élève",
    )
    nom = models.CharField("nom", max_length=200)
    type = models.CharField(
        "type",
        max_length=30,
        choices=TypeDocument.choices,
        default=TypeDocument.AUTRE,
    )
    contenu = models.BinaryField("contenu")
    taille = models.PositiveIntegerField("taille en octets")
    content_type = models.CharField("type MIME", max_length=100)
    date_upload = models.DateTimeField("date d'envoi", auto_now_add=True)

    objects = DocumentManager()

    class Meta:
        ordering = ["-date_upload"]
        indexes = [models.Index(fields=["eleve", "-date_upload"])]
        verbose_name = "document"
        verbose_name_plural = "documents"

    def __str__(self):
        return f"{self.nom} — {self.eleve.username}"
