"""Création et suppression des commentaires de prospection."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from comptes.models import JournalAction, Notification, ScopeSuperviseur, TypeNotification, Utilisateur
from comptes.notifications import creer_notification
from comptes.scope_utils import superviser_eleve
from comptes.utils import log_action

from .forms import CommentaireForm
from .models import Commentaire, Prospection


def _autoriser_commentaire(request, prospection):
    role = request.user.role
    if role == Utilisateur.Role.ADMIN:
        return
    if role == Utilisateur.Role.ELEVE and prospection.eleve_id == request.user.pk:
        return
    if role == Utilisateur.Role.SUPERVISEUR and superviser_eleve(
        request.user, prospection.eleve
    ):
        return
    raise PermissionDenied


def _notifier_commentaire(auteur, prospection):
    eleve = prospection.eleve
    lien_eleve = reverse("entreprises:detail", args=[prospection.pk])
    if auteur.role == Utilisateur.Role.ELEVE:
        scope_ids = ScopeSuperviseur.objects.filter(
            centre_id=eleve.centre_id,
            is_active=True,
        ).values_list("superviseur_id", flat=True)
        superviseurs = Utilisateur.objects.filter(
            pk__in=scope_ids,
            is_active=True,
        )
        if superviseurs.exists():
            message = (
                f"Nouveau commentaire de {auteur.username} sur la prospection "
                f"de {eleve.username}."
            )
            for superviseur in superviseurs:
                creer_notification(
                    superviseur,
                    TypeNotification.COMMENTAIRE,
                    message,
                    reverse("staff:detail_eleve", args=[eleve.pk]),
                )
        else:
            admin = Utilisateur.objects.filter(
                role=Utilisateur.Role.ADMIN,
                is_active=True,
            ).first()
            if admin is not None:
                creer_notification(
                    admin,
                    TypeNotification.COMMENTAIRE,
                    f"Nouveau commentaire de {auteur.username} sur la prospection de {eleve.username}.",
                    reverse("staff:detail_eleve", args=[eleve.pk]),
                )
    elif auteur.role in {
        Utilisateur.Role.SUPERVISEUR,
        Utilisateur.Role.ADMIN,
    } and eleve.is_active:
        creer_notification(
            eleve,
            TypeNotification.COMMENTAIRE,
            f"Nouveau commentaire sur votre prospection chez {prospection.entreprise.nom}.",
            lien_eleve,
        )


def _url_retour_commentaire(request, prospection):
    if request.user.role == Utilisateur.Role.ELEVE:
        return reverse("entreprises:detail", args=[prospection.pk])
    return reverse("staff:detail_eleve", args=[prospection.eleve_id])


@login_required
@require_POST
def commentaire_ajouter(request, prospection_pk):
    prospection = get_object_or_404(
        Prospection.objects.select_related("eleve", "entreprise"),
        pk=prospection_pk,
    )
    _autoriser_commentaire(request, prospection)
    form = CommentaireForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Le commentaire ne peut pas être vide.")
        return redirect(_url_retour_commentaire(request, prospection))

    with transaction.atomic():
        commentaire = form.save(commit=False)
        commentaire.auteur = request.user
        commentaire.prospection = prospection
        commentaire.save()
        log_action(
            JournalAction.Action.COMMENTAIRE_CREE,
            utilisateur=request.user,
            cible=commentaire,
            details={"prospection_id": prospection.pk},
            request=request,
        )
        _notifier_commentaire(request.user, prospection)
    messages.success(request, "Le commentaire a été ajouté.")
    return redirect(_url_retour_commentaire(request, prospection))


@login_required
@require_POST
def commentaire_supprimer(request, pk):
    commentaire = get_object_or_404(
        Commentaire.objects.select_related("auteur", "prospection__eleve"),
        pk=pk,
    )
    if (
        commentaire.auteur_id != request.user.pk
        and request.user.role != Utilisateur.Role.ADMIN
    ):
        raise PermissionDenied
    cible = commentaire.prospection
    commentaire.delete()
    messages.success(request, "Le commentaire a été supprimé.")
    return redirect(_url_retour_commentaire(request, cible))
