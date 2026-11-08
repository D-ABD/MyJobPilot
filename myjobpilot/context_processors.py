"""Données communes de navigation."""
from comptes.models import Notification


def notifications_non_lues(request):
    """Ajoute uniquement le compteur SQL des notifications non lues."""
    if not request.user.is_authenticated:
        return {"notifications_non_lues": 0}
    count = Notification.objects.filter(
        destinataire=request.user,
        lu=False,
    ).count()
    return {"notifications_non_lues": count}
