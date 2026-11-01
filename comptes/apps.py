"""Configuration de l'application comptes."""
from django.apps import AppConfig


class ComptesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "comptes"

    def ready(self):
        """Enregistre les signaux d'authentification."""
        from . import signals  # noqa: F401
