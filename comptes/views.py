"""Vues publiques, authentification et workflow d'attente."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from .forms import ConnexionForm, InscriptionForm
from .models import JournalAction, Utilisateur
from .utils import log_action


def accueil(request):
    return render(request, "accueil.html")


def inscription(request):
    if request.method == "POST":
        form = InscriptionForm(request.POST, request=request)
        if form.is_valid():
            utilisateur = form.save()
            log_action(
                JournalAction.Action.INSCRIPTION_SOUMISE,
                utilisateur=utilisateur,
                cible=utilisateur,
                request=request,
            )
            return redirect("comptes:connexion")
    else:
        form = InscriptionForm(request=request)
    return render(request, "comptes/inscription.html", {"form": form})


class ConnexionView(LoginView):
    template_name = "comptes/connexion.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True


class DeconnexionView(LogoutView):
    next_page = "comptes:connexion"


@login_required
def redirection_apres_login(request):
    utilisateur = request.user
    if utilisateur.role == Utilisateur.Role.ADMIN:
        return redirect("/admin/")
    if utilisateur.role == Utilisateur.Role.SUPERVISEUR:
        return redirect("/admin/")
    if not utilisateur.is_valide:
        return redirect("comptes:en_attente")
    return redirect("entreprises:dashboard")


@login_required
def en_attente(request):
    return render(request, "comptes/en_attente.html")
