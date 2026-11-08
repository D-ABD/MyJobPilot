"""Formulaires des tâches, avec choix limités au périmètre de l'auteur."""
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from comptes.scope_utils import centres_du_superviseur
from entreprises.models import Prospection
from .models import Tache

Utilisateur = get_user_model()


class TacheForm(forms.ModelForm):
    assigne_a = forms.ModelChoiceField(
        queryset=Utilisateur.objects.none(), label="Assigner à", required=True,
    )
    prospection = forms.ModelChoiceField(
        queryset=Prospection.objects.none(), label="Prospection liée", required=False,
        empty_label="Aucune prospection",
    )

    class Meta:
        model = Tache
        fields = ("titre", "description", "date_echeance", "statut", "prospection", "assigne_a")
        widgets = {
            "date_echeance": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        role = user.role
        if role == Utilisateur.Role.ELEVE:
            self.fields["assigne_a"].queryset = Utilisateur.objects.filter(pk=user.pk)
            self.fields["prospection"].queryset = Prospection.objects.filter(eleve=user).select_related("entreprise")
        elif role == Utilisateur.Role.SUPERVISEUR:
            centres = centres_du_superviseur(user)
            self.fields["assigne_a"].queryset = Utilisateur.objects.filter(
                Q(pk=user.pk)
                | Q(role=Utilisateur.Role.ELEVE, centre_id__in=centres)
            ).order_by("username")
            self.fields["prospection"].queryset = Prospection.objects.filter(
                Q(eleve=user)
                | Q(eleve__role=Utilisateur.Role.ELEVE, eleve__centre_id__in=centres)
            ).select_related("entreprise", "eleve")
        elif role == Utilisateur.Role.ADMIN:
            self.fields["assigne_a"].queryset = Utilisateur.objects.all().order_by("username")
            self.fields["prospection"].queryset = Prospection.objects.select_related("entreprise", "eleve")


class OffresAlternanceForm(forms.Form):
    mot_cle = forms.CharField(
        label="Métier ou mot-clé",
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. développeur web ou M1805"}),
    )
    ville = forms.CharField(
        label="Code postal de la ville",
        max_length=5,
        widget=forms.TextInput(attrs={"class": "form-control", "inputmode": "numeric", "placeholder": "Ex. 75001"}),
        help_text="La recherche géographique LBA utilise un code postal français à 5 chiffres.",
    )
    rayon = forms.IntegerField(
        label="Rayon (km)",
        min_value=0,
        max_value=200,
        initial=30,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 200}),
    )

    def clean_ville(self):
        ville = self.cleaned_data["ville"].strip()
        if not ville.isdigit() or len(ville) != 5:
            raise forms.ValidationError("Saisissez un code postal français à 5 chiffres.")
        return ville
