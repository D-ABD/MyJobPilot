"""Vues personnelles et staff de gestion des documents."""
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from comptes.models import JournalAction, Utilisateur
from comptes.scope_utils import superviser_eleve
from comptes.utils import log_action

from .forms import DocumentUploadForm, MO_OCTETS
from .models import Document


def _autoriser_document(request, document):
    role = request.user.role
    if role == Utilisateur.Role.ADMIN:
        return
    if role == Utilisateur.Role.ELEVE and document.eleve_id == request.user.pk:
        return
    if role == Utilisateur.Role.SUPERVISEUR and superviser_eleve(
        request.user, document.eleve
    ):
        return
    raise PermissionDenied


@login_required
def document_list(request):
    """Liste les documents de l'élève connecté ou tous ceux de l'admin."""
    role = request.user.role
    if role == Utilisateur.Role.ELEVE:
        documents = Document.objects.listing().filter(eleve=request.user)
        quota_total = settings.DOCUMENT_QUOTA_BYTES
        quota_utilise = sum(document.taille for document in documents)
        context = {
            "documents": documents,
            "quota_total_mo": quota_total / MO_OCTETS,
            "quota_utilise_mo": quota_utilise / MO_OCTETS,
            "quota_pourcentage": min(100, int(quota_utilise * 100 / quota_total)),
        }
    elif role == Utilisateur.Role.ADMIN:
        context = {"documents": Document.objects.listing(), "quota_total_mo": None}
    else:
        raise PermissionDenied
    return render(request, "documents/document_list.html", context)


@login_required
def document_upload(request):
    """Enregistre un document pour l'élève connecté et journalise l'envoi."""
    if request.user.role != Utilisateur.Role.ELEVE:
        raise PermissionDenied
    form = DocumentUploadForm(
        request.POST or None,
        request.FILES or None,
        eleve=request.user,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            document = form.save()
            log_action(
                JournalAction.Action.DOCUMENT_UPLOAD,
                utilisateur=request.user,
                cible=document,
                details={"document_id": document.pk, "nom": document.nom},
                request=request,
            )
        messages.success(request, "Le document a été ajouté.")
        return redirect("documents:list")
    return render(request, "documents/document_upload.html", {"form": form})


@login_required
def document_download(request, pk):
    """Télécharge un document après contrôle du propriétaire ou du scope."""
    document = get_object_or_404(
        Document.objects.select_related("eleve").only(
            "id",
            "eleve_id",
            "eleve__role",
            "eleve__centre_id",
            "nom",
            "content_type",
            "contenu",
        ),
        pk=pk,
    )
    _autoriser_document(request, document)
    log_action(
        JournalAction.Action.DOCUMENT_DOWNLOAD,
        utilisateur=request.user,
        cible=document,
        details={"document_id": document.pk, "nom": document.nom},
        request=request,
    )
    return FileResponse(
        BytesIO(document.contenu),
        as_attachment=True,
        filename=document.nom,
        content_type=document.content_type,
    )


@login_required
def document_delete(request, pk):
    """Supprime un document du propriétaire ou à la demande de l'admin."""
    document = get_object_or_404(Document.objects.select_related("eleve"), pk=pk)
    est_proprietaire = (
        request.user.role == Utilisateur.Role.ELEVE
        and document.eleve_id == request.user.pk
    )
    if request.user.role != Utilisateur.Role.ADMIN and not est_proprietaire:
        raise PermissionDenied

    if request.method == "POST":
        nom = document.nom
        document_id = document.pk
        with transaction.atomic():
            log_action(
                JournalAction.Action.DOCUMENT_SUPPRIME,
                utilisateur=request.user,
                cible=document,
                details={"document_id": document_id, "nom": nom},
                request=request,
            )
            document.delete()
        messages.success(request, "Le document a été supprimé.")
        return redirect("documents:list")
    return render(
        request,
        "documents/document_confirm_delete.html",
        {"document": document},
    )


@login_required
def staff_documents_eleve(request, pk):
    """Consultation en lecture seule des documents d'un élève autorisé."""
    if request.user.role not in {
        Utilisateur.Role.ADMIN,
        Utilisateur.Role.SUPERVISEUR,
    }:
        raise PermissionDenied
    eleve = get_object_or_404(
        Utilisateur,
        pk=pk,
        role=Utilisateur.Role.ELEVE,
    )
    if (
        request.user.role == Utilisateur.Role.SUPERVISEUR
        and not superviser_eleve(request.user, eleve)
    ):
        raise PermissionDenied
    documents = Document.objects.listing().filter(eleve=eleve)
    return render(
        request,
        "documents/staff_documents_eleve.html",
        {"eleve": eleve, "documents": documents},
    )
