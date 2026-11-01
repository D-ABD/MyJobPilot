"""Formulaires des actions staff sur les élèves."""
from django import forms

from comptes.models import Centre


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
