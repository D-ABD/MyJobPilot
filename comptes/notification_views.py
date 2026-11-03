"""Vues de consultation et de mise à jour des notifications."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(
        destinataire=request.user
    ).order_by("lu", "-date_creation")
    return render(
        request,
        "comptes/notifications.html",
        {"notifications": notifications},
    )


@login_required
def notification_unread_count(request):
    count = Notification.objects.filter(
        destinataire=request.user,
        lu=False,
    ).count()
    return JsonResponse({"count": count})


@login_required
@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(
        Notification,
        pk=pk,
        destinataire=request.user,
    )
    if not notification.lu:
        notification.lu = True
        notification.save(update_fields=["lu"])
    return redirect("comptes:notifications")


@login_required
@require_POST
def notification_mark_all_read(request):
    Notification.objects.filter(
        destinataire=request.user,
        lu=False,
    ).update(lu=True)
    return redirect("comptes:notifications")
