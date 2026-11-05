"""Formulaires des actions staff sur les élèves."""
from django import forms

from comptes.models import Centre
from entreprises.forms import ProspectionForm
from entreprises.models import TypeContrat


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
