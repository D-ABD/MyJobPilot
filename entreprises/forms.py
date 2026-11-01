"""Formulaires de prospection et de changement de statut."""
from django import forms

from .models import Entreprise, Statut


class EntrepriseForm(forms.ModelForm):
    class Meta:
        model = Entreprise
        fields = (
            "nom",
            "secteur",
            "site_web",
            "adresse",
            "ville",
            "code_postal",
            "contact_nom",
            "contact_email",
            "contact_telephone",
            "source",
            "notes",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.widget.attrs.setdefault("class", "form-control")


class ChangementStatutForm(forms.Form):
    nouveau_statut = forms.ChoiceField(
        label="Nouveau statut",
        choices=Statut.choices,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    commentaire = forms.CharField(
        label="Commentaire",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        required=False,
    )
    date_associee = forms.DateField(
        label="Date associée",
        required=False,
        help_text="Date de relance ou d'entretien selon le statut choisi.",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def clean(self):
        donnees = super().clean()
        statut = donnees.get("nouveau_statut")
        date_associee = donnees.get("date_associee")
        if statut in {Statut.A_RELANCER, Statut.ENTRETIEN_PROGRAMME} and not date_associee:
            self.add_error("date_associee", "Cette date est obligatoire pour le statut sélectionné.")
        return donnees
