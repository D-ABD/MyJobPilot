from django import forms
from django.contrib.auth import get_user_model

from comptes.models import Centre, ScopeSuperviseur

Utilisateur = get_user_model()


class SuperviseurCreateForm(forms.Form):
    username = forms.CharField(max_length=150, label="Identifiant")
    email = forms.EmailField(label="Adresse e-mail")
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    centre = forms.ModelChoiceField(queryset=Centre.objects.all(), label="Centre")

    def clean_username(self):
        username = self.cleaned_data["username"]
        if Utilisateur.objects.filter(username=username).exists():
            raise forms.ValidationError("Cet identifiant existe déjà.")
        return username

    def save(self, auteur):
        user = Utilisateur.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            role=Utilisateur.Role.SUPERVISEUR,
            centre=self.cleaned_data["centre"],
            is_active=True,
            is_valide=True,
        )
        ScopeSuperviseur.creer(user, self.cleaned_data["centre"], auteur=auteur)
        return user


class ScopeCreateForm(forms.Form):
    centre = forms.ModelChoiceField(queryset=Centre.objects.all(), label="Centre")

    def __init__(self, *args, superviseur, **kwargs):
        super().__init__(*args, **kwargs)
        self.superviseur = superviseur
        centres_deja_lies = ScopeSuperviseur.objects.filter(
            superviseur=superviseur,
        ).values_list("centre_id", flat=True)
        self.fields["centre"].queryset = Centre.objects.exclude(pk__in=centres_deja_lies)
