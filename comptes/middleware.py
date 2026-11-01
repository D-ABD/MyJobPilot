"""Redirige les élèves en attente de validation."""
import logging

from django.shortcuts import redirect

logger = logging.getLogger("comptes")


class ValidationCompteMiddleware:
    """Bloque les vues applicatives pour les élèves non validés."""

    EXEMPT_PREFIXES = (
        "/comptes/en-attente/",
        "/comptes/deconnexion/",
        "/comptes/connexion/",
        "/comptes/inscription/",
        "/admin/",
        "/static/",
        "/favicon.ico",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user
            and user.is_authenticated
            and getattr(user, "role", None) == "eleve"
            and not user.is_valide
            and not request.path.startswith(self.EXEMPT_PREFIXES)
        ):
            return redirect("/comptes/en-attente/")
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Enregistre le chemin et l'identifiant lors d'une erreur serveur."""
        user = getattr(request, "user", None)
        user_id = getattr(user, "pk", None) if user and user.is_authenticated else None
        logger.error(
            "Erreur serveur request.path=%s user.id=%s",
            request.path,
            user_id,
            exc_info=(type(exception), exception, exception.__traceback__),
        )
        return None
