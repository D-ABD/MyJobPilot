"""Vues de consultation et de mise à jour des notifications."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(
        destinataire=request.user
    ).order_by("lu", "-date_creation")
    page_obj = Paginator(notifications, 20).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    def url_page(numero):
        query = params.copy()
        query["page"] = numero
        return f"?{query.urlencode()}"

    pagination = {
        "page_links": [{
            "number": numero,
            "url": url_page(numero),
            "current": numero == page_obj.number,
        } for numero in page_obj.paginator.page_range],
        "previous_url": url_page(page_obj.previous_page_number()) if page_obj.has_previous() else None,
        "next_url": url_page(page_obj.next_page_number()) if page_obj.has_next() else None,
    }
    return render(
        request,
        "comptes/notifications.html",
        {"notifications": page_obj.object_list, "page_obj": page_obj, "pagination": pagination},
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
    if notification.lien and url_has_allowed_host_and_scheme(
        notification.lien,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(notification.lien)
    return redirect("comptes:notifications")


@login_required
@require_POST
def notification_mark_all_read(request):
    Notification.objects.filter(
        destinataire=request.user,
        lu=False,
    ).update(lu=True)
    return redirect("comptes:notifications")
