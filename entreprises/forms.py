"""Formulaires du référentiel, des prospections et de leurs statuts."""
from django import forms

from .models import Commentaire, Entreprise, Prospection, Statut


class ProspectionForm(forms.Form):
    entreprise_id = forms.ModelChoiceField(
        label="Entreprise sélectionnée",
        queryset=Entreprise.objects.all(),
        required=False,
        widget=forms.HiddenInput(),
    )
    entreprise_nom = forms.CharField(
        label="Rechercher une entreprise",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "role": "combobox",
                "aria-autocomplete": "list",
                "aria-expanded": "false",
            }
        ),
    )
    statut = forms.ChoiceField(
        label="Statut",
        choices=Statut.choices,
        initial=Statut.A_CONTACTER,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )
    source = forms.CharField(label="Source", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    date_relance = forms.DateField(
        label="Date de relance", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    date_candidature = forms.DateField(
        label="Date de candidature", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    date_mise_en_attente = forms.DateField(
        label="Date de mise en attente", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    date_entretien = forms.DateField(
        label="Date d'entretien", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    date_refus = forms.DateField(
        label="Date de refus", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    date_acceptation = forms.DateField(
        label="Date d'acceptation", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    def __init__(self, *args, prospection=None, **kwargs):
        self.prospection = prospection
        initial = kwargs.setdefault("initial", {})
        if prospection is not None:
            initial.setdefault("entreprise_id", prospection.entreprise_id)
            initial.setdefault("entreprise_nom", prospection.entreprise.nom)
            for champ in (
                "statut", "notes", "source", "date_relance", "date_candidature",
                "date_mise_en_attente", "date_refus", "date_acceptation",
            ):
                initial.setdefault(champ, getattr(prospection, champ))
            initial.setdefault(
                "date_entretien",
                prospection.date_entretien.date() if prospection.date_entretien else None,
            )
        super().__init__(*args, **kwargs)
        if prospection is not None:
            self.fields["entreprise_id"].disabled = True
            self.fields["entreprise_nom"].disabled = True
        for champ in self.fields.values():
            if not isinstance(champ.widget, forms.HiddenInput):
                champ.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        donnees = super().clean()
        if not donnees.get("entreprise_id") and not donnees.get("entreprise_nom", "").strip():
            self.add_error("entreprise_nom", "Sélectionnez une entreprise ou renseignez son nom.")

        statut = donnees.get("statut")
        champ_date_requise = {
            Statut.A_RELANCER: "date_relance",
            Statut.ENTRETIEN_PROGRAMME: "date_entretien",
        }.get(statut)
        if champ_date_requise and not donnees.get(champ_date_requise):
            self.add_error(champ_date_requise, "Cette date est obligatoire pour le statut sélectionné.")

        entreprise = donnees.get("entreprise_id")
        nom_saisi = donnees.get("entreprise_nom", "").strip()
        if entreprise and nom_saisi and entreprise.nom.casefold() != nom_saisi.casefold():
            self.add_error("entreprise_nom", "Le nom saisi ne correspond pas à l'entreprise sélectionnée.")
        if entreprise and self.prospection is not None:
            doublon = Prospection.objects.filter(eleve=self.prospection.eleve, entreprise=entreprise).exclude(
                pk=self.prospection.pk
            )
            if doublon.exists():
                self.add_error("entreprise_nom", "Vous avez déjà une prospection pour cette entreprise.")
        return donnees


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



class CommentaireForm(forms.ModelForm):
    class Meta:
        model = Commentaire
        fields = ("contenu",)
        widgets = {
            "contenu": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }

    def clean_contenu(self):
        contenu = self.cleaned_data["contenu"].strip()
        if not contenu:
            raise forms.ValidationError("Le commentaire ne peut pas être vide.")
        return contenu
