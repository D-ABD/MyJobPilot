"""Formulaires d'inscription et de connexion."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import ConsentementRGPD, Utilisateur
from .utils import get_client_ip


class InscriptionForm(UserCreationForm):
    consentement_rgpd = forms.BooleanField(
        label="J'accepte la politique de confidentialité",
        required=True,
        help_text=(
            "Vous pouvez consulter la politique de confidentialité à tout moment. "
            "Ce consentement est requis pour créer un compte."
        ),
    )

    class Meta:
        model = Utilisateur
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "centre",
            "formation",
            "password1",
            "password2",
            "consentement_rgpd",
        )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._request = request
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["consentement_rgpd"].widget.attrs["class"] = "form-check-input"

    def clean(self):
        cleaned_data = super().clean()
        centre = cleaned_data.get("centre")
        formation = cleaned_data.get("formation")
        if centre and formation and formation.centre_id != centre.pk:
            self.add_error("formation", "Choisissez une formation rattachée au centre sélectionné.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = Utilisateur.Role.ELEVE
        user.is_valide = False
        if commit:
            user.full_clean()
            user.save()
            self.save_m2m()
            ConsentementRGPD.objects.create(
                utilisateur=user,
                version_politique="1.0",
                ip=get_client_ip(self._request) if self._request else None,
                user_agent=self._request.META.get("HTTP_USER_AGENT", "") if self._request else "",
            )
        return user


class ConnexionForm(AuthenticationForm):
    """Formulaire de connexion avec des libellés français."""

    username = forms.CharField(
        label="Nom d'utilisateur",
        widget=forms.TextInput(attrs={"autofocus": True, "class": "form-control", "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )
