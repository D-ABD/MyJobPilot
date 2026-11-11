from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from comptes.models import JournalAction, Utilisateur
from comptes.utils import invalidate_user_sessions, log_action


class Command(BaseCommand):
    """Purge les comptes désactivés ou élèves non validés trop anciens.

    Les durées de rétention viennent des réglages dédiés ; --dry-run affiche
    les comptes concernés sans invalider leurs sessions ni les supprimer.
    L'exécution journalise ensuite la purge de chaque compte.
    """
    help = "Purge les comptes anciens désactivés ou non validés."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Affiche les comptes concernés sans les supprimer.")

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff_inactive = now - timedelta(days=settings.RETENTION_COMPTE_DESACTIVE_JOURS)
        cutoff_pending = now - timedelta(days=settings.RETENTION_COMPTE_NON_VALIDE_JOURS)
        inactive_qs = Utilisateur.objects.filter(is_active=False).filter(
            last_login__lt=cutoff_inactive,
        ) | Utilisateur.objects.filter(
            is_active=False, last_login__isnull=True, date_joined__lt=cutoff_inactive,
        )
        rows = []
        seen = set()
        for user in inactive_qs.distinct():
            rows.append((user, "desactive", user.last_login or user.date_joined))
            seen.add(user.pk)
        pending = Utilisateur.objects.filter(
            role=Utilisateur.Role.ELEVE, is_valide=False, date_joined__lt=cutoff_pending,
        ).exclude(pk__in=seen)
        rows.extend((user, "non_valide", user.date_joined) for user in pending)
        dry_run = options["dry_run"]
        for user, reason, date_reference in rows:
            self.stdout.write(f"{user.username} — {reason} — {date_reference.isoformat()}")
            if dry_run:
                continue
            user_id = user.pk
            invalidate_user_sessions(user)
            log_action(
                JournalAction.Action.PURGE_RGPD, utilisateur=user,
                details={"user_id": user_id, "raison": reason},
            )
            user.delete()
        label = "seraient purgés" if dry_run else "purgés"
        self.stdout.write(self.style.SUCCESS(f"{len(rows)} compte(s) {label}."))
