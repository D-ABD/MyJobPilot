from django import forms

from .models import DemandeRGPD, StatutDemande


class DemandeRGPDForm(forms.ModelForm):
    class Meta:
        model = DemandeRGPD
        fields = ("type", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class TraitementDemandeRGPDForm(forms.ModelForm):
    class Meta:
        model = DemandeRGPD
        fields = ("statut", "motif_refus")
        widgets = {"motif_refus": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("statut") == StatutDemande.REFUSEE and not cleaned.get("motif_refus", "").strip():
            self.add_error("motif_refus", "Un motif est requis pour refuser la demande.")
        return cleaned
