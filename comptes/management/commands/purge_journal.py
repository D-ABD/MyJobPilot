import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from comptes.models import JournalAction

logger = logging.getLogger("comptes")


class Command(BaseCommand):
    """Supprime les entrées du journal antérieures à la durée de rétention.

    La durée vient de RETENTION_JOURNAL_JOURS ; --dry-run compte les entrées
    concernées sans les supprimer.
    """
    help = "Supprime les entrées du journal d'action arrivées à échéance."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Compte sans supprimer.")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.RETENTION_JOURNAL_JOURS)
        qs = JournalAction.objects.filter(date__lt=cutoff)
        count = qs.count()
        if options["dry_run"]:
            self.stdout.write(f"{count} entrée(s) seraient supprimées.")
            logger.info("Simulation purge_journal : %s entrée(s) à supprimer.", count)
            return
        qs.delete()
        self.stdout.write(f"{count} entrée(s) supprimées.")
        logger.info("Purge du journal : %s entrée(s) supprimées.", count)
