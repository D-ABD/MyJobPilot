"""Crée de manière idempotente les comptes de démonstration."""
import getpass
import os
import sys

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from comptes.models import Centre, Formation, Utilisateur


class Command(BaseCommand):
    """Prépare de manière idempotente les quatre comptes de démonstration.

    Le mot de passe vient de DEMO_PASSWORD ou d'une saisie interactive ; il
    n'est jamais affiché par la commande.
    """
    help = "Crée les comptes de démonstration MyJobPilot."

    def handle(self, *args, **options):
        centre_paris = Centre.objects.get(nom="Centre Paris")
        formation_sio = Formation.objects.get(centre=centre_paris, nom="BTS SIO")

        comptes = [
            {
                "username": "admin_demo",
                "defaults": {
                    "email": "admin_demo@example.com",
                    "first_name": "Admin",
                    "last_name": "Démo",
                    "role": Utilisateur.Role.ADMIN,
                    "is_staff": True,
                    "is_superuser": True,
                    "is_valide": True,
                    "date_validation": timezone.now(),
                },
                "superuser": True,
            },
            {
                "username": "superviseur_demo",
                "defaults": {
                    "email": "superviseur_demo@example.com",
                    "first_name": "Superviseur",
                    "last_name": "Démo",
                    "role": Utilisateur.Role.SUPERVISEUR,
                    "centre": centre_paris,
                    "is_staff": True,
                    "is_valide": True,
                },
                "superuser": False,
            },
            {
                "username": "eleve_demo",
                "defaults": {
                    "email": "eleve_demo@example.com",
                    "first_name": "Élève",
                    "last_name": "Démo",
                    "role": Utilisateur.Role.ELEVE,
                    "centre": centre_paris,
                    "formation": formation_sio,
                    "is_valide": True,
                },
                "superuser": False,
            },
            {
                "username": "eleve_attente_demo",
                "defaults": {
                    "email": "eleve_attente_demo@example.com",
                    "first_name": "Élève en attente",
                    "last_name": "Démo",
                    "role": Utilisateur.Role.ELEVE,
                    "centre": centre_paris,
                    "formation": formation_sio,
                    "is_valide": False,
                },
                "superuser": False,
            },
        ]

        comptes_manquants = [
            config["username"]
            for config in comptes
            if not Utilisateur.objects.filter(username=config["username"]).exists()
        ]
        mot_de_passe = os.getenv("DEMO_PASSWORD", "")
        if comptes_manquants and not mot_de_passe:
            if not sys.stdin.isatty():
                raise CommandError(
                    "Définissez DEMO_PASSWORD dans votre fichier .env pour créer les comptes de démonstration."
                )
            premier_saisie = getpass.getpass("Mot de passe des comptes de démonstration : ")
            confirmation = getpass.getpass("Confirmez le mot de passe : ")
            if not premier_saisie or premier_saisie != confirmation:
                raise CommandError("Les mots de passe sont vides ou ne correspondent pas.")
            mot_de_passe = premier_saisie

        for config in comptes:
            utilisateur, created = Utilisateur.objects.get_or_create(
                username=config["username"],
                defaults=config["defaults"],
            )
            if created:
                utilisateur.set_password(mot_de_passe)
                utilisateur.save(update_fields=("password",))

        self.stdout.write(
            self.style.SUCCESS(
                "Comptes de démonstration prêts : "
                "admin_demo, superviseur_demo, eleve_demo, eleve_attente_demo. "
                "Le mot de passe est fourni localement et n'est jamais affiché."
            )
        )
