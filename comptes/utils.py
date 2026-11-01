"""Utilitaires de journalisation et de sécurité des sessions."""
from django.contrib.sessions.models import Session
from django.utils import timezone

from .models import JournalAction


def invalidate_user_sessions(user):
    """Supprime les sessions actives du compte et retourne leur nombre."""
    if user is None or not getattr(user, "pk", None):
        return 0

    deleted = 0
    active_sessions = Session.objects.filter(expire_date__gte=timezone.now()).iterator()
    for session in active_sessions:
        try:
            data = session.get_decoded()
        except (ValueError, TypeError):
            continue
        if data.get("_auth_user_id") == str(user.pk):
            session.delete()
            deleted += 1
            log_action(
                JournalAction.Action.SESSION_INVALIDE,
                utilisateur=user,
                cible=session,
                details={"session_key": session.session_key},
            )
    return deleted


def get_client_ip(request):
    """Retourne l'adresse du client, en privilégiant X-Forwarded-For."""
    if request is None:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        candidate = forwarded_for.split(",", 1)[0].strip()
        return candidate or None
    return request.META.get("REMOTE_ADDR") or None


def log_action(action, utilisateur=None, cible=None, details=None, request=None):
    """Crée une ligne typée dans JournalAction et retourne l'objet créé."""
    cible_type = ""
    cible_id = ""
    if cible is not None:
        cible_type = cible._meta.label
        cible_id = str(cible.pk)
    return JournalAction.objects.create(
        utilisateur=utilisateur,
        action=action,
        cible_type=cible_type,
        cible_id=cible_id,
        details=details or {},
        ip=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )
