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

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from comptes.models import Formation


class AdminEleveCentreForm(forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ("centre", "formation")

    def clean(self):
        cleaned = super().clean()
        centre = cleaned.get("centre")
        formation = cleaned.get("formation")
        if centre and formation and formation.centre_id != centre.pk:
            self.add_error("formation", "La formation doit appartenir au centre choisi.")
        return cleaned


class AdminEleveFormationForm(forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ("formation",)

    def __init__(self, *args, instance, **kwargs):
        super().__init__(*args, instance=instance, **kwargs)
        self.fields["formation"].queryset = Formation.objects.filter(centre=instance.centre)


class RefusCompteForm(forms.Form):
    motif_refus = forms.CharField(
        label="Motif du refus", required=True,
        widget=forms.Textarea(attrs={"rows": 4}),
    )


class AdminSuperviseurUpdateForm(forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ("username", "email", "first_name", "last_name")


class MotDePasseSuperviseurForm(forms.Form):
    nouveau_mot_de_passe = forms.CharField(
        label="Nouveau mot de passe", widget=forms.PasswordInput,
    )
    confirmation = forms.CharField(
        label="Confirmer le mot de passe", widget=forms.PasswordInput,
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("nouveau_mot_de_passe")
        confirmation = cleaned.get("confirmation")
        if password and confirmation and password != confirmation:
            self.add_error("confirmation", "Les mots de passe ne correspondent pas.")
        if password and password == confirmation:
            try:
                validate_password(password, self.user)
            except ValidationError as exc:
                self.add_error("nouveau_mot_de_passe", exc)
        return cleaned
