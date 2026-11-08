"""Formulaires des actions staff sur les élèves."""
from django import forms
from django.core.exceptions import ValidationError

from comptes.models import Centre, Utilisateur
from comptes.scope_utils import centres_du_superviseur
from entreprises.forms import ProspectionForm
from entreprises.models import TypeContrat
from core.models import Objectif


class ChangementCentreFormStaff(forms.Form):
    centre = forms.ModelChoiceField(
        label="Nouveau centre",
        queryset=Centre.objects.all(),
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, centres=None, **kwargs):
        super().__init__(*args, **kwargs)
        if centres is not None:
            self.fields["centre"].queryset = centres


class AjoutProspectionStaffForm(ProspectionForm):
    """Formulaire de prospection prérempli dans la fiche staff de l'élève."""

    type_contrat = forms.ChoiceField(
        choices=TypeContrat.choices,
        widget=forms.RadioSelect,
        required=True,
        initial=None,
        label="Type de contrat",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["entreprise_nom"].label = "Entreprise pour cet élève"
        self.fields["entreprise_nom"].help_text = "Sélectionnez une entreprise ou créez son référentiel."


class ObjectifForm(forms.ModelForm):
    class Meta:
        model = Objectif
        fields = ("eleve", "type", "valeur", "periode_debut", "periode_fin")
        widgets = {
            "periode_debut": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "periode_fin": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "eleve": forms.Select(attrs={"class": "form-select"}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "valeur": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }

    def __init__(self, *args, utilisateur, instance=None, **kwargs):
        super().__init__(*args, instance=instance, **kwargs)
        eleves = Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE)
        if utilisateur.role == Utilisateur.Role.SUPERVISEUR:
            eleves = eleves.filter(centre_id__in=centres_du_superviseur(utilisateur))
        self.fields["eleve"].queryset = eleves.order_by("username")
        self.fields["eleve"].label = "Élève"
        self.fields["type"].label = "Type d’objectif"
        self.fields["valeur"].label = "Valeur cible"
        self.fields["periode_debut"].label = "Début de la période"
        self.fields["periode_fin"].label = "Fin de la période"

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get("periode_debut")
        fin = cleaned.get("periode_fin")
        if debut and fin and fin <= debut:
            self.add_error("periode_fin", "La date de fin doit être postérieure à la date de début.")
        eleve = cleaned.get("eleve")
        type_objectif = cleaned.get("type")
        if eleve and debut and fin and type_objectif:
            doublon = Objectif.objects.filter(
                eleve=eleve,
                type=type_objectif,
                periode_debut=debut,
                periode_fin=fin,
            )
            if self.instance.pk:
                doublon = doublon.exclude(pk=self.instance.pk)
            if doublon.exists():
                raise ValidationError("Un objectif de ce type existe déjà pour cet élève et cette période.")
        return cleaned
