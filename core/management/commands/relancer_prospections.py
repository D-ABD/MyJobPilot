"""Envoie les rappels automatiques pour les relances échues."""
import logging
import os
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from comptes.emails import envoyer_email_relance
from comptes.models import JournalAction
from entreprises.models import Prospection, Statut

logger = logging.getLogger("comptes")


def _env_bool(name, default):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    """Envoie un rappel email pour chaque prospection échue à relancer.

    Le délai vient de RELANCES_AUTO_JOURS (défaut 7) et l'envoi de
    RELANCES_AUTO_EMAIL ; --dry-run simule sans envoyer ni modifier les données.
    Un succès date l'envoi et l'inscrit au journal, sous verrou transactionnel.
    """
    help = "Envoie un email pour chaque relance échue depuis le délai configuré."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les emails prévus sans envoyer ni modifier de données.",
        )

    def handle(self, *args, **options):
        try:
            delai_jours = max(0, int(os.getenv("RELANCES_AUTO_JOURS", "7")))
        except ValueError as exc:
            raise CommandError("RELANCES_AUTO_JOURS doit être un entier.") from exc

        dry_run = options["dry_run"]
        email_active = _env_bool("RELANCES_AUTO_EMAIL", "True")
        date_limite = timezone.localdate() - timedelta(days=delai_jours)
        queryset = Prospection.objects.filter(
            statut=Statut.A_RELANCER,
            date_relance__lte=date_limite,
            date_derniere_relance_email__isnull=True,
        ).select_related("eleve", "entreprise").order_by("date_relance", "pk")

        if dry_run:
            elements = list(queryset)
            for prospection in elements:
                self.stdout.write(
                    f"Simulation : {prospection.eleve.username} — "
                    f"{prospection.entreprise.nom} (date prévue : {prospection.date_relance})"
                )
            self.stdout.write(f"{len(elements)} email(s) seraient envoyés.")
            return

        if not email_active:
            self.stdout.write("Envoi désactivé par RELANCES_AUTO_EMAIL.")
            return

        envoyes = 0
        for candidate in queryset:
            # La vérification sous verrou évite un second envoi concurrent pour la même ligne.
            with transaction.atomic():
                try:
                    prospection = (
                        Prospection.objects.select_for_update()
                        .select_related("eleve", "entreprise")
                        .get(
                            pk=candidate.pk,
                            statut=Statut.A_RELANCER,
                            date_relance__lte=date_limite,
                            date_derniere_relance_email__isnull=True,
                        )
                    )
                except Prospection.DoesNotExist:
                    continue

                try:
                    resultat = envoyer_email_relance(prospection)
                except Exception:
                    logger.exception(
                        "Échec de l'envoi de l'email de relance pour la prospection %s",
                        prospection.pk,
                    )
                    continue

                if not resultat:
                    continue
                prospection.date_derniere_relance_email = timezone.now()
                prospection.save(update_fields=["date_derniere_relance_email", "date_modification"])
                JournalAction.objects.create(
                    utilisateur=prospection.eleve,
                    action=JournalAction.Action.RELANCE_EMAIL_ENVOYE,
                    cible_type="Prospection",
                    cible_id=str(prospection.pk),
                    details={
                        "prospection_id": prospection.pk,
                        "eleve_id": prospection.eleve_id,
                    },
                )
                envoyes += 1

        self.stdout.write(f"{envoyes} email(s) de relance envoyé(s).")
