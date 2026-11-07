"""Référentiel partagé des entreprises et prospections individuelles."""
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Statut(models.TextChoices):
    A_CONTACTER = "a_contacter", "À contacter"
    A_RELANCER = "a_relancer", "À relancer"
    CANDIDATURE_ENVOYEE = "candidature_envoyee", "Candidature envoyée"
    EN_ATTENTE = "en_attente", "En attente"
    ENTRETIEN_PROGRAMME = "entretien_programme", "Entretien programmé"
    REFUS = "refus", "Refus"
    ACCEPTE = "accepte", "Accepté"


class TypeContrat(models.TextChoices):
    STAGE = "stage", "Stage"
    ALTERNANCE = "alternance", "Alternance"


class Entreprise(models.Model):
    nom = models.CharField("nom", max_length=200)
    secteur = models.CharField("secteur", max_length=100, blank=True)
    site_web = models.URLField("site web", blank=True)
    adresse = models.TextField("adresse", blank=True)
    ville = models.CharField("ville", max_length=100, blank=True)
    code_postal = models.CharField("code postal", max_length=20, blank=True)
    contact_nom = models.CharField("nom du contact", max_length=100, blank=True)
    contact_email = models.EmailField("courriel du contact", blank=True)
    contact_telephone = models.CharField("téléphone du contact", max_length=30, blank=True)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)

    class Meta:
        verbose_name = "entreprise"
        verbose_name_plural = "entreprises"
        constraints = [
            models.UniqueConstraint(Lower("nom"), name="unique_entreprise_nom_ci"),
        ]

    def __str__(self):
        return self.nom


class Prospection(models.Model):
    eleve = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="prospections",
        verbose_name="élève",
    )
    entreprise = models.ForeignKey(
        Entreprise,
        on_delete=models.CASCADE,
        related_name="prospections",
        verbose_name="entreprise",
    )
    statut = models.CharField(
        "statut",
        max_length=30,
        choices=Statut.choices,
        default=Statut.A_CONTACTER,
    )
    type_contrat = models.CharField(
        "type de contrat", max_length=20, choices=TypeContrat.choices,
        default=TypeContrat.ALTERNANCE,
    )
    date_relance = models.DateField("date de relance", null=True, blank=True)
    date_derniere_relance_email = models.DateTimeField(
        "date du dernier email de relance", null=True, blank=True,
    )
    date_candidature = models.DateField("date de candidature", null=True, blank=True)
    date_mise_en_attente = models.DateField("date de mise en attente", null=True, blank=True)
    date_entretien = models.DateTimeField("date d'entretien", null=True, blank=True)
    date_refus = models.DateField("date de refus", null=True, blank=True)
    date_acceptation = models.DateField("date d'acceptation", null=True, blank=True)
    notes = models.TextField("notes", blank=True)
    source = models.CharField("source", max_length=100, blank=True)
    date_creation = models.DateTimeField("date de création", auto_now_add=True)
    date_modification = models.DateTimeField("date de modification", auto_now=True)

    class Meta:
        ordering = ["-date_modification"]
        verbose_name = "prospection"
        verbose_name_plural = "prospections"
        unique_together = [("eleve", "entreprise")]
        indexes = [
            models.Index(fields=["eleve", "statut"]),
            models.Index(fields=["eleve", "-date_modification"]),
        ]

    def __str__(self):
        return f"{self.eleve.username} → {self.entreprise.nom}"


class HistoriqueStatut(models.Model):
    prospection = models.ForeignKey(
        Prospection,
        on_delete=models.CASCADE,
        related_name="historique",
        verbose_name="prospection",
    )
    ancien_statut = models.CharField("ancien statut", max_length=30, choices=Statut.choices, blank=True)
    nouveau_statut = models.CharField("nouveau statut", max_length=30, choices=Statut.choices)
    date_changement = models.DateTimeField("date du changement", auto_now_add=True)
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="changements_statut",
        verbose_name="auteur",
        null=True,
    )
    commentaire = models.TextField("commentaire", blank=True)
    date_associee = models.DateField(
        "date associée",
        null=True,
        blank=True,
        help_text="Date associée au nouveau statut (relance, entretien, etc.).",
    )

    class Meta:
        ordering = ["-date_changement"]
        verbose_name = "historique de statut"
        verbose_name_plural = "historiques de statuts"

    def __str__(self):
        return f"{self.prospection.entreprise.nom} : {self.ancien_statut} → {self.nouveau_statut}"


class Commentaire(models.Model):
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="commentaires",
        verbose_name="auteur",
    )
    prospection = models.ForeignKey(
        Prospection,
        on_delete=models.CASCADE,
        related_name="commentaires",
        verbose_name="prospection",
    )
    contenu = models.TextField("contenu")
    date = models.DateTimeField("date", auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["prospection", "-date"]),
        ]
        verbose_name = "commentaire"
        verbose_name_plural = "commentaires"

    def __str__(self):
        return f"Commentaire de {self.auteur.username} — {self.prospection}"
