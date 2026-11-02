"""Formulaires d'envoi de documents avec limites de taille et de quota."""
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum

from .models import Document, TypeDocument


MO_OCTETS = 1024 * 1024


def _mo(octets):
    return f"{octets / MO_OCTETS:.2f}"


class DocumentUploadForm(forms.Form):
    nom = forms.CharField(label="Nom du document", max_length=200)
    type = forms.ChoiceField(
        label="Type de document",
        choices=TypeDocument.choices,
        initial=TypeDocument.AUTRE,
    )
    contenu = forms.FileField(label="Fichier")

    def __init__(self, *args, eleve, **kwargs):
        super().__init__(*args, **kwargs)
        self.eleve = eleve

    def clean_contenu(self):
        fichier = self.cleaned_data["contenu"]
        if fichier.size > settings.DOCUMENT_MAX_SIZE_BYTES:
            raise ValidationError(
                "Le fichier dépasse la taille maximale autorisée de 5 Mo."
            )
        return fichier

    def clean(self):
        cleaned_data = super().clean()
        fichier = cleaned_data.get("contenu")
        if fichier is None or self.eleve is None:
            return cleaned_data

        quota = settings.DOCUMENT_QUOTA_BYTES
        deja_utilise = (
            Document.objects.filter(eleve=self.eleve).aggregate(total=Sum("taille"))["total"]
            or 0
        )
        total_apres_envoi = deja_utilise + fichier.size
        if total_apres_envoi > quota:
            restant = max(0, quota - deja_utilise)
            raise ValidationError(
                "Quota dépassé : "
                f"{_mo(total_apres_envoi)} Mo / {quota // MO_OCTETS} Mo, "
                f"reste {_mo(restant)} Mo."
            )
        return cleaned_data

    def save(self, commit=True):
        if not self.is_valid():
            raise ValueError("Le formulaire doit être valide avant l'enregistrement.")
        fichier = self.cleaned_data["contenu"]
        contenu = fichier.read()
        document = Document(
            eleve=self.eleve,
            nom=self.cleaned_data["nom"],
            type=self.cleaned_data["type"],
            contenu=contenu,
            taille=len(contenu),
            content_type=fichier.content_type or "application/octet-stream",
        )
        if commit:
            document.save()
        return document
